import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
from dashboard import (build_dashboard, build_free_module_map, build_progress_dashboard,
                       enhance_dashboard_page, enhance_progress_dashboard,
                       finding_text_zh, issue_data, plan_data)
from agent_adapters import available_adapters
from repair_bridge import (BridgeState, DEFAULT_BRIDGE_ORIGIN, REQUEST_VERSION,
                           build_codex_command, ensure_bridge, module_progress,
                           progress_from_log, validate_request)


def run_script(name, *args, cwd):
    return subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, name), *args],
        cwd=cwd, capture_output=True, text=True, encoding="utf-8",
    )


def write_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


class ReportOnlyTests(unittest.TestCase):
    def test_dashboard_translates_audit_findings_to_chinese(self):
        finding = {
            "text": "Stale writer locks remain fail-closed and require explicit operator cleanup; cleanup failures now emit a diagnostic instead of being silently swallowed."
        }
        translated = finding_text_zh(finding)
        self.assertIn("陈旧的写入锁", translated)
        self.assertNotIn("Stale writer locks", translated)

    def make_state(self, project):
        codemap = os.path.join(project, ".codemap")
        state_path = os.path.join(codemap, "modules.json")
        os.makedirs(os.path.join(project, "src"), exist_ok=True)
        with open(os.path.join(project, "project.godot"), "w", encoding="utf-8") as handle:
            handle.write("[application]\nconfig/name=\"Report Only Test\"\n")
        with open(os.path.join(project, "src", "main.py"), "w", encoding="utf-8") as handle:
            handle.write("print('ok')\n")
        dimensions = [
            {"id": item, "status": "good", "score": 90,
             "summary": "evidence-backed", "evidence": [], "relatedModules": ["main"]}
            for item in (
                "responsibility", "boundary", "contract", "dependency",
                "data_logic", "composition_state", "evolution", "safeguards",
            )
        ]
        lenses = [
            {"id": item, "summary": "evidence-backed"}
            for item in ("split", "connect", "change", "protect")
        ]
        write_json(state_path, {
            "meta": {"project": "Report Only Test", "lang": "en",
                     "mdPath": ".codemap/codemap.md"},
            "bands": [{"id": "core", "t": "Core"}],
            "spine": ["main"],
            "architectureDimensions": dimensions,
            "architectureLenses": lenses,
            "modules": [{
                "id": "main", "label": "Main", "band": "core",
                "path": "src/main.py", "paths": ["src/main.py"],
                "desc": "entry point", "coupling": "low", "deps": [],
            }],
        })
        scanned = run_script("scan.py", "--root", project, "--state", state_path, "--write",
                             cwd=ROOT)
        self.assertEqual(scanned.returncode, 0, scanned.stderr)
        with open(state_path, encoding="utf-8") as handle:
            state = json.load(handle)
        module = state["modules"][0]
        module.update({"score": 90, "grade": "A", "tags": ["clean"],
                       "findings": [], "auditedHash": module["contentHash"]})
        write_json(state_path, state)
        return state_path

    def test_render_only_writes_markdown_and_has_no_map_language(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            report = os.path.join(project, ".codemap", "codemap.md")
            result = run_script("render.py", "--state", state_path, "--out-md", report,
                                cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.isfile(report))
            self.assertFalse(os.path.exists(os.path.join(project, ".codemap", "codemap.html")))
            with open(report, encoding="utf-8") as handle:
                text = handle.read().lower()
            self.assertNotIn("interactive view", text)
            self.assertNotIn("dependency graph", text)

    def test_render_rejects_removed_html_arguments(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            result = run_script("render.py", "--state", state_path,
                                "--template", "missing.html",
                                "--out-html", os.path.join(project, "out.html"),
                                "--out-md", os.path.join(project, "out.md"),
                                cwd=ROOT)
            self.assertNotEqual(result.returncode, 0)

    def test_publish_verify_and_rollback_have_no_html_artifact(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            published = run_script(
                "version.py", "publish", "--root", project,
                "--mode", "full", "--expected-baseline", "none",
                "--gate", "focused-tests:pass", cwd=ROOT,
            )
            self.assertEqual(published.returncode, 0, published.stderr)
            base = os.path.join(project, ".codemap", "versions", "audit-v0001")
            self.assertTrue(os.path.isfile(os.path.join(base, "codemap.md")))
            self.assertFalse(os.path.exists(os.path.join(base, "codemap.html")))
            with open(os.path.join(base, "manifest.json"), encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertNotIn("codemap.html", manifest["artifacts"])
            verified = run_script("version.py", "verify", "--root", project, cwd=ROOT)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            payload = json.loads(verified.stdout)
            self.assertTrue(payload["integrityValid"])
            self.assertTrue(payload["semanticValid"])

    def test_dashboard_is_beginner_summary_and_exports_planning_request(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            dashboard = os.path.join(project, ".codemap", "audit-dashboard.html")
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            Path(dashboard).write_text(build_dashboard(state, project), encoding="utf-8")
            with open(dashboard, encoding="utf-8") as handle:
                page = handle.read()
            for label in ("目前最大的三个问题", "短期方案", "长期维护方案", "完美方案"):
                self.assertIn(label, page)
            self.assertNotIn("可能引起的三个问题", page)
            for credits in ('"credits": 1', '"credits": 5', '"credits": 25'):
                self.assertIn(credits, page)
            self.assertIn("选择方案", page)
            self.assertIn("开始规划并修复", page)
            self.assertIn("architecture-review-repair/v1", page)
            self.assertIn("project-blueprint-planner", page)
            self.assertIn("plan-execution-orchestrator", page)
            self.assertIn("已有审查结论", page)
            self.assertNotIn("重新审查", page)
            self.assertNotIn("复审", page)
            self.assertIn("projectRoot", page)
            self.assertRegex(page, r"127\.0\.0\.1:\d+/repair-requests")
            self.assertIn("预计修改代码行数", page)
            self.assertIn("架构分数", page)
            self.assertIn("architectureScore", page)
            self.assertIn('"moduleMapUrl": "codemap.html"', page)
            self.assertNotIn(".codemap/codemap.html", page)
            self.assertNotIn("分 · 连 · 变 · 保", page)
            self.assertNotIn("LoC", page)
            self.assertNotIn("dependency graph", page.lower())

    def test_plan_data_uses_code_lines_for_repair_scope(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            plans = plan_data(state, project)
            self.assertEqual([plan["credits"] for plan in plans], [1, 5, 25])
            self.assertTrue(all("codeLines" in plan for plan in plans))
            self.assertTrue(all("loc" not in plan for plan in plans))
            self.assertTrue(all(plan["satisfied"] for plan in plans))

    def test_progress_dashboard_can_minimize_to_and_restore_from_dot(self):
        page = enhance_progress_dashboard(build_progress_dashboard("http://127.0.0.1:8767/repair-requests"))
        self.assertIn('id="progressToggle"', page)
        self.assertIn("architecture-progress-window", page)
        self.assertIn("window.close", page)
        self.assertNotIn("window.resizeTo", page)
        self.assertIn('id="flowZoomIn"', page)
        self.assertIn('id="flowExpand"', page)
        self.assertIn("模块执行图", page)

    def test_dashboard_cancel_stops_active_bridge_request(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            page = enhance_dashboard_page(build_dashboard(state, project))
            self.assertIn('method:"DELETE"', page)
            self.assertIn("architecture-review-active-request", page)
            self.assertIn("architecture-progress-window", page)
            self.assertIn("architectureProgressBubble", page)
            self.assertIn("pointerdown", page)
            self.assertIn("pointermove", page)
            self.assertIn("bubble.dataset.dragged", page)
            self.assertIn("正在停止", page)

    def test_bridge_cancel_marks_job_and_terminates_process(self):
        with tempfile.TemporaryDirectory() as project:
            queue = Path(project) / ".codemap" / "repair-requests"
            queue.mkdir(parents=True)
            request_id = "20260902-000000-deadbeef"
            status = {"requestId": request_id, "status": "running"}
            write_json(queue / (request_id + ".status.json"), status)
            process = mock.Mock(pid=1234)
            process.poll.return_value = None
            bridge = BridgeState(project, queue)
            bridge.jobs[request_id] = status
            bridge.processes[request_id] = process
            with mock.patch("repair_bridge.subprocess.run") as run:
                cancelled = bridge.cancel_job(request_id)
            self.assertEqual(cancelled["status"], "cancelled")
            if os.name == "nt":
                run.assert_called_once()
            else:
                process.terminate.assert_called_once()

    def test_bridge_cancel_recovers_pid_after_bridge_restart(self):
        with tempfile.TemporaryDirectory() as project:
            queue = Path(project) / ".codemap" / "repair-requests"
            queue.mkdir(parents=True)
            request_id = "20260902-000001-feedface"
            write_json(queue / (request_id + ".status.json"),
                       {"requestId": request_id, "status": "running", "pid": 4321})
            bridge = BridgeState(project, queue)
            with mock.patch("repair_bridge.subprocess.run") as run:
                cancelled = bridge.cancel_job(request_id)
            self.assertEqual(cancelled["status"], "cancelled")
            if os.name == "nt":
                run.assert_called_once()

    def test_plan_satisfaction_uses_requested_score_and_severity_gates(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            module = state["modules"][0]
            module["score"] = 80
            module["grade"] = "B"
            module["findings"] = [{"sev": "LOW", "loc": "src/main.py:1", "text": "minor"}]
            plans = {plan["id"]: plan for plan in plan_data(state, project)}
            self.assertTrue(plans["short-term"]["satisfied"])
            self.assertTrue(plans["long-term"]["satisfied"])
            self.assertFalse(plans["perfect"]["satisfied"])

            module["score"] = 74
            module["findings"] = []
            plans = {plan["id"]: plan for plan in plan_data(state, project)}
            self.assertFalse(plans["short-term"]["satisfied"])
            self.assertFalse(plans["long-term"]["satisfied"])

            module["score"] = 79
            module["findings"] = [{"sev": "LOW", "loc": "src/main.py:1", "text": "minor"}]
            plans = {plan["id"]: plan for plan in plan_data(state, project)}
            self.assertTrue(plans["short-term"]["satisfied"])
            self.assertFalse(plans["long-term"]["satisfied"])

            module["score"] = 90
            module["findings"] = [{"sev": "MED", "loc": "src/main.py:1", "text": "medium"}]
            plans = {plan["id"]: plan for plan in plan_data(state, project)}
            self.assertTrue(plans["short-term"]["satisfied"])
            self.assertTrue(plans["long-term"]["satisfied"])
            self.assertFalse(plans["perfect"]["satisfied"])

            module["findings"] = [{"sev": "HIGH", "loc": "src/main.py:1", "text": "high"}]
            plans = {plan["id"]: plan for plan in plan_data(state, project)}
            self.assertFalse(plans["short-term"]["satisfied"])
            self.assertFalse(plans["long-term"]["satisfied"])
            self.assertFalse(plans["perfect"]["satisfied"])

    def test_dashboard_falls_back_to_independent_module_scores(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            for dimension in state["architectureDimensions"]:
                dimension.pop("score", None)
            self.assertEqual(issue_data(state)["architectureScore"], 90)

    def test_dashboard_prefers_complete_dimension_scores(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            for dimension in state["architectureDimensions"]:
                dimension["score"] = 70
            self.assertEqual(issue_data(state)["architectureScore"], 70)

    def test_bridge_configuration_rejects_non_localhost_endpoint(self):
        with tempfile.TemporaryDirectory() as project:
            with self.assertRaises(ValueError):
                ensure_bridge(project, requested_url="https://example.com")

    def test_bridge_configuration_starts_or_reuses_exact_project(self):
        with tempfile.TemporaryDirectory() as project:
            with mock.patch("repair_bridge._bridge_health", return_value=False), \
                    mock.patch("repair_bridge._port_available", return_value=True), \
                    mock.patch("repair_bridge.subprocess.Popen") as popen, \
                    mock.patch("repair_bridge.time.sleep"):
                origin = ensure_bridge(project, requested_url=DEFAULT_BRIDGE_ORIGIN)
            self.assertEqual(origin, DEFAULT_BRIDGE_ORIGIN)
            popen.assert_called_once()

    def test_repair_request_is_bound_to_target_project_and_workflow(self):
        with tempfile.TemporaryDirectory() as project:
            request = {
                "requestVersion": REQUEST_VERSION,
                "projectRoot": project,
                "project": "test",
                "selectedPlan": "short-term",
                "plannerSkill": "project-blueprint-planner",
                "executionSkill": "plan-execution-orchestrator",
                "workflow": ["plan", "repair", "accept", "reaudit"],
                "scope": {"moduleCount": 1, "fileCount": 1, "codeLines": 10,
                          "moduleIds": ["main"], "files": ["src/main.py"]},
                "acceptance": {"target": "gate", "stopOn": ["block"]},
            }
            self.assertEqual(validate_request(request, project), Path(project).resolve())
            request["projectRoot"] = os.path.join(project, "other")
            with self.assertRaises(ValueError):
                validate_request(request, project)
            request["projectRoot"] = project
            request["scope"]["files"] = ["../outside.py"]
            with self.assertRaises(ValueError):
                validate_request(request, project)
            request["scope"]["files"] = ["src/main.py"]
            request["selectedPlan"] = "unknown"
            with self.assertRaises(ValueError):
                validate_request(request, project)

    def test_codex_command_matches_current_unattended_cli(self):
        with tempfile.TemporaryDirectory() as project:
            request_path = os.path.join(project, "request.json")
            result_path = os.path.join(project, "result.json")
            command = build_codex_command(project, Path(request_path), Path(result_path))
            self.assertTrue(command[0].lower().endswith("codex.exe"))
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", command)
            self.assertNotIn("-a", command)
            self.assertNotIn("workspace-write", command)

    def test_repair_command_uses_existing_audit_without_reaudit(self):
        with tempfile.TemporaryDirectory() as project:
            request_path = os.path.join(project, "request.json")
            result_path = os.path.join(project, "result.json")
            command = build_codex_command(project, Path(request_path), Path(result_path))
            prompt = command[-1]
            self.assertIn("已有审查结果", prompt)
            self.assertIn("不要重新审查或重新评分", prompt)
            self.assertNotIn("重新运行 report-only 架构审查", prompt)

    def test_progress_reports_acceptance_without_review_stage(self):
        with tempfile.TemporaryDirectory() as project:
            log_path = os.path.join(project, "job.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("独立验收模块完成\n")
            progress = progress_from_log({
                "status": "running", "logPath": log_path,
                "receivedAt": "2026-09-02T00:00:00+08:00",
            })
            self.assertEqual(progress["stage"], "verifying")
            self.assertEqual(progress["label"], "验收中")

    def test_bridge_projects_log_activity_into_progress_stage(self):
        with tempfile.TemporaryDirectory() as project:
            log_path = os.path.join(project, "job.log")
            with open(log_path, "w", encoding="utf-8") as handle:
                handle.write("正在生成并校验 P0-P2 计划\n")
            progress = progress_from_log({
                "status": "running", "logPath": log_path,
                "receivedAt": "2026-09-02T00:00:00+08:00",
            })
            self.assertEqual(progress["stage"], "planning")
            self.assertEqual(progress["percent"], 40)
            self.assertGreaterEqual(progress["elapsedSeconds"], 0)

    def test_bridge_reports_current_and_upcoming_modules(self):
        status = {"scope": {"moduleIds": ["one", "two", "three"],
                             "moduleLabels": {"one": "第一模块", "two": "第二模块", "three": "第三模块"}}}
        progress = module_progress(status, "[MODULE_START] moduleId=two\n")
        self.assertEqual(progress["currentModule"]["label"], "第二模块")
        self.assertEqual([item["label"] for item in progress["upcomingModules"]], ["第三模块"])
        progress = module_progress(status, "[MODULE_START] moduleId=one\n[MODULE_DONE] moduleId=one\n")
        self.assertEqual(progress["currentModule"]["label"], "第二模块")

    def test_module_map_uses_the_original_free_architecture_review_view(self):
        with tempfile.TemporaryDirectory() as project:
            state_path = self.make_state(project)
            with open(state_path, encoding="utf-8") as handle:
                state = json.load(handle)
            page = build_free_module_map(state, state_path)
            self.assertIn('id="gradeFilter"', page)
            self.assertIn('id="tagFilter"', page)
            self.assertIn('id="detail"', page)
            self.assertIn("dependentsOf =", page)
            self.assertIn('id="report-only-free-map"', page)
            self.assertIn('id="reportOnlyDashboardLink"', page)
            self.assertIn('href="audit-dashboard.html"', page)
            self.assertIn('id="freePlanSection"', page)
            for label in ("短期方案", "长期维护方案", "完美方案", "开始规划并修复"):
                self.assertIn(label, page)
            self.assertIn("architecture-review-repair/v1", page)
            self.assertIn('method:"DELETE"', page)
            self.assertIn("architecture-review-active-request", page)
            self.assertIn(".lens-app,.lens-top,.lens-tabs,.lens-main{display:none!important}", page)
            self.assertIn(".app,.app.open{display:grid!important", page)
            self.assertIn("#homeBtn,#stdBtn,#reportBtn,#spineBtn,#versionBtn{display:none!important}", page)

    def test_agent_adapter_registry_covers_requested_agents(self):
        ids = {item["id"] for item in available_adapters(ROOT)}
        self.assertTrue({"codex", "claude-code", "workbuddy", "zcode", "doubao"}.issubset(ids))


if __name__ == "__main__":
    unittest.main()
