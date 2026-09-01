#!/usr/bin/env python3
"""Local bridge from the report-only dashboard to a Codex repair process.

The bridge is intentionally localhost-only. It accepts one validated repair
request, stores an immutable request record under ``.codemap/repair-requests``
and starts Codex in the audited project directory. It never accepts source code
or arbitrary shell commands from the browser.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse
import urllib.request

from agent_adapters import available_adapters, build_command, resolve_adapter


REQUEST_VERSION = "architecture-review-repair/v1"
MAX_BODY = 1024 * 1024
PLAN_IDS = {"short-term", "long-term", "perfect"}
DEFAULT_BRIDGE_ORIGIN = "http://127.0.0.1:8767"
PROGRESS_STAGES = (
    ("queued", "等待本机 AI 启动", "请求已进入本地队列。", 0),
    ("reading", "准备中", "正在读取项目和审查结果。", 20),
    ("planning", "规划中", "正在生成修复规划。", 40),
    ("repairing", "修复中", "正在按顺序处理模块。", 60),
    ("verifying", "验收中", "正在依据已有审查结论验收修复结果。", 80),
    ("completed", "已完成", "本机 AI 已完成规划、修复和验收。", 100),
)
CANCELLED_PROGRESS = ("cancelled", "已取消", "任务已停止，未继续执行后续修复。", 0)


def _bridge_health(url, root):
    """Return whether a localhost bridge is serving this exact project root."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url.rstrip("/") + "/health", timeout=1) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
        reported = payload.get("projectRoot")
        return (bool(reported)
                and os.path.realpath(str(reported)) == os.path.realpath(str(root))
                and payload.get("cancelSupported") is True)
    except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _free_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _port_available(port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False


def ensure_bridge(root, requested_url=None, log_path=None):
    """Reuse or start a localhost bridge and return its origin URL.

    The health check includes the project root, so a dashboard cannot silently
    submit a repair request to another project's bridge.
    """
    root = Path(root).resolve()
    parsed = urlparse(requested_url or DEFAULT_BRIDGE_ORIGIN)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("repair bridge must use http://127.0.0.1 or http://localhost")
    requested_port = parsed.port or 8767
    origin = "http://127.0.0.1:{}".format(requested_port)
    if _bridge_health(origin, root):
        return origin
    port = requested_port if _port_available(requested_port) else _free_local_port()
    origin = "http://127.0.0.1:{}".format(port)
    bridge_script = Path(__file__).resolve()
    if log_path is None:
        log_path = root / ".codemap" / "repair-bridge.log"
    log_path = Path(log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log = open(log_path, "a", encoding="utf-8")
        popen_kwargs = {
            "cwd": str(root), "stdout": log, "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True
        subprocess.Popen(
            [sys.executable, os.fspath(bridge_script),
             "--root", str(root), "--port", str(port)], **popen_kwargs,
        )
    except OSError:
        return origin
    finally:
        # The child owns the inherited stdout handle; release the parent handle
        # so temporary projects and normal shutdown can remove the log cleanly.
        try:
            log.close()
        except (UnboundLocalError, AttributeError):
            pass
    for _ in range(20):
        if _bridge_health(origin, root):
            break
        time.sleep(0.05)
    return origin


def now_iso():
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def json_read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def append_log(path, message):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def _elapsed_seconds(received_at):
    try:
        started = dt.datetime.fromisoformat(str(received_at))
        return max(0, int((dt.datetime.now(dt.timezone.utc).astimezone() - started).total_seconds()))
    except (TypeError, ValueError):
        return 0


def progress_from_log(status):
    """Project observable Codex log activity into coarse, truthful workflow stages."""
    state = status.get("status")
    if state == "completed":
        stage = PROGRESS_STAGES[-1]
        progress = {"stage": stage[0], "label": stage[1], "message": stage[2], "percent": stage[3],
                "stageNumber": len(PROGRESS_STAGES) - 1, "stageTotal": len(PROGRESS_STAGES) - 1,
                "elapsedSeconds": _elapsed_seconds(status.get("receivedAt"))}
        progress.update(module_progress(status, allow_current=True))
        return progress
    if state == "failed":
        progress = {"stage": "failed", "label": "执行失败", "message": status.get("error") or "本机 AI 进程未成功完成。",
                "percent": 0, "stageNumber": 0, "stageTotal": len(PROGRESS_STAGES) - 1,
                "elapsedSeconds": _elapsed_seconds(status.get("receivedAt"))}
        progress.update(module_progress(status, allow_current=False))
        return progress
    if state == "cancelled":
        progress = {"stage": CANCELLED_PROGRESS[0], "label": CANCELLED_PROGRESS[1],
                "message": CANCELLED_PROGRESS[2], "percent": CANCELLED_PROGRESS[3],
                "stageNumber": 0, "stageTotal": len(PROGRESS_STAGES) - 1,
                "elapsedSeconds": _elapsed_seconds(status.get("receivedAt"))}
        progress.update(module_progress(status, allow_current=False))
        return progress
    log_path = status.get("_internalLogPath") or status.get("logPath")
    text = ""
    if log_path:
        try:
            with open(log_path, "rb") as handle:
                handle.seek(0, os.SEEK_END)
                handle.seek(max(0, handle.tell() - 128 * 1024))
                text = handle.read().decode("utf-8", errors="replace")
        except OSError:
            pass
    lower = text.lower()
    stage = PROGRESS_STAGES[0] if state == "queued" else PROGRESS_STAGES[1]
    markers = (
        (PROGRESS_STAGES[1], ("读取请求", "读取项目", "审计证据", "reading")),
        (PROGRESS_STAGES[2], ("project-blueprint-planner", "p0-p2", "plan_ready", "架构门禁", "规划")),
        (PROGRESS_STAGES[3], ("plan-execution-orchestrator", "逐项施工", "开始修复", "施工")),
        (PROGRESS_STAGES[4], ("独立验收", "验收", "acceptance", "verify")),
    )
    positions = []
    for candidate, needles in markers:
        hits = [max(lower.rfind(needle.lower()), text.rfind(needle)) for needle in needles]
        positions.append((max(hits), candidate))
    latest_position, latest_stage = max(positions, key=lambda item: item[0])
    if latest_position >= 0:
        stage = latest_stage
    message = stage[2]
    if not text:
        message = "本机 AI 已启动，等待第一条执行日志。"
    progress = {"stage": stage[0], "label": stage[1], "message": message, "percent": stage[3],
            "stageNumber": PROGRESS_STAGES.index(stage), "stageTotal": len(PROGRESS_STAGES) - 1,
            "elapsedSeconds": _elapsed_seconds(status.get("receivedAt"))}
    progress.update(module_progress(status, text, allow_current=stage[0] in {"repairing", "verifying"}))
    return progress


def module_progress(status, log_text="", allow_current=True):
    """Extract the current and pending module queue from agent progress markers."""
    if not log_text:
        log_path = status.get("_internalLogPath") or status.get("logPath")
        if log_path:
            try:
                with open(log_path, "rb") as handle:
                    handle.seek(0, os.SEEK_END)
                    handle.seek(max(0, handle.tell() - 128 * 1024))
                    log_text = handle.read().decode("utf-8", errors="replace")
            except OSError:
                pass
    scope = status.get("scope") or {}
    ids = [item for item in scope.get("moduleIds", []) if isinstance(item, str) and item.strip()]
    labels = scope.get("moduleLabels") or {}
    if isinstance(labels, list):
        labels = {item.get("id"): item.get("label") for item in labels if isinstance(item, dict)}
    labels = labels if isinstance(labels, dict) else {}
    current_index = None
    completed = set()
    for match in re.finditer(r"\[(MODULE_START|MODULE_DONE)\]\s+moduleId=([^\s]+)", log_text or ""):
        module_id = match.group(2)
        if module_id not in ids:
            continue
        if match.group(1) == "MODULE_DONE":
            completed.add(module_id)
        else:
            current_index = ids.index(module_id)
    if current_index is None and allow_current:
        for index, module_id in enumerate(ids):
            if module_id in completed:
                continue
            current_index = index
            break
    if current_index is not None and current_index < len(ids) and ids[current_index] in completed:
        current_index = next((index for index in range(current_index + 1, len(ids))
                              if ids[index] not in completed), None)
    current_id = ids[current_index] if current_index is not None and current_index < len(ids) else None
    upcoming = ids[(current_index + 1) if current_index is not None else 0:]
    return {
        "currentModule": {"id": current_id, "label": labels.get(current_id, current_id)} if current_id else None,
        "completedModules": [{"id": item, "label": labels.get(item, item)} for item in ids if item in completed],
        "upcomingModules": [{"id": item, "label": labels.get(item, item)} for item in upcoming if item not in completed],
    }


def validate_request(value, root):
    if not isinstance(value, dict) or value.get("requestVersion") != REQUEST_VERSION:
        raise ValueError("只接受 architecture-review-repair/v1 请求")
    required = ("projectRoot", "project", "selectedPlan", "plannerSkill", "executionSkill", "workflow", "scope", "acceptance")
    missing = [key for key in required if not value.get(key)]
    if missing:
        raise ValueError("请求缺少字段：" + ", ".join(missing))
    request_root = Path(str(value["projectRoot"])).resolve()
    if request_root != Path(root).resolve():
        raise ValueError("请求项目与桥接服务绑定的项目不一致")
    if value["selectedPlan"] not in PLAN_IDS:
        raise ValueError("selectedPlan 不是受支持的修复方案")
    if value["plannerSkill"] != "project-blueprint-planner" or value["executionSkill"] != "plan-execution-orchestrator":
        raise ValueError("请求必须指定规划 Skill 和执行编排 Skill")
    if value.get("agentId") is not None and (not isinstance(value["agentId"], str) or not value["agentId"].strip()):
        raise ValueError("agentId 必须是非空字符串")
    if not isinstance(value["workflow"], list) or not value["workflow"]:
        raise ValueError("workflow 必须是非空列表")
    if any(not isinstance(step, str) or not step.strip() or len(step) > 500 for step in value["workflow"]):
        raise ValueError("workflow 项必须是非空短文本")
    scope = value["scope"]
    for key in ("moduleCount", "fileCount", "codeLines", "moduleIds", "files"):
        if key not in scope:
            raise ValueError("scope 缺少字段：" + key)
    for key in ("moduleCount", "fileCount", "codeLines"):
        if isinstance(scope[key], bool) or not isinstance(scope[key], int) or scope[key] < 0:
            raise ValueError("scope.{} 必须是非负整数".format(key))
    if not isinstance(scope["moduleIds"], list) or any(
        not isinstance(item, str) or not item.strip() or len(item) > 200 for item in scope["moduleIds"]
    ):
        raise ValueError("scope.moduleIds 必须是字符串列表")
    if not isinstance(scope["files"], list) or len(scope["files"]) > 10000:
        raise ValueError("scope.files 必须是文件路径列表")
    root_path = Path(root).resolve()
    for item in scope["files"]:
        if not isinstance(item, str) or not item.strip() or len(item) > 500:
            raise ValueError("scope.files 包含无效路径")
        candidate = (root_path / item).resolve()
        try:
            candidate.relative_to(root_path)
        except ValueError:
            raise ValueError("scope.files 不能越出目标项目目录")
    if not isinstance(value["acceptance"].get("stopOn"), list) or not value["acceptance"]["stopOn"]:
        raise ValueError("acceptance.stopOn 必须是非空列表")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in value["acceptance"]["stopOn"]):
        raise ValueError("acceptance.stopOn 项必须是非空短文本")
    return request_root


def enrich_request(value):
    """Add internal workflow routing only inside the localhost bridge."""
    request = dict(value)
    request.setdefault("plannerSkill", "project-blueprint-planner")
    request.setdefault("executionSkill", "plan-execution-orchestrator")
    request.setdefault("workflow", ["读取已有审查结果并生成计划", "逐项修复", "依据已有审查结论独立验收"])
    request.setdefault("acceptance", {"target": "达到所选方案门槛", "stopOn": ["真实阻塞", "无法安全回滚"]})
    return request


def codex_executable():
    # Prefer the native executable. npm's .CMD shim can inherit a console
    # control event and terminate the unattended child on Windows.
    return shutil.which("codex.exe") or shutil.which("codex.cmd") or shutil.which("codex")


def build_codex_command(root, request_path, result_path):
    adapter = resolve_adapter(root, "codex")
    return build_command(adapter, root, request_path, result_path)


class BridgeState:
    def __init__(self, root, queue_dir):
        self.root = Path(root).resolve()
        self.queue_dir = Path(queue_dir).resolve()
        self.lock = threading.Lock()
        self.jobs = {}
        self.processes = {}

    def create_job(self, request):
        request_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        request_path = self.queue_dir / (request_id + ".json")
        internal_request_path = self.queue_dir / ("." + request_id + ".task.json")
        result_path = self.queue_dir / (request_id + ".result.json")
        status_path = self.queue_dir / (request_id + ".status.json")
        log_path = self.queue_dir / (request_id + ".log")
        internal_log_path = self.queue_dir / ("." + request_id + ".internal.log")
        record = dict(request)
        record["requestId"] = request_id
        record["receivedAt"] = now_iso()
        record["projectRoot"] = str(self.root)
        json_write(internal_request_path, record)
        module_labels = {}
        try:
            state = json_read(self.root / ".codemap" / "modules.json")
            module_labels = {
                item.get("id"): item.get("label", item.get("id"))
                for item in state.get("modules", [])
                if isinstance(item, dict) and item.get("id") in record["scope"].get("moduleIds", [])
            }
        except (OSError, ValueError, TypeError, KeyError):
            pass
        public_record = {
            "requestId": request_id, "requestVersion": record["requestVersion"],
            "project": record["project"], "selectedPlan": record["selectedPlan"],
            "agentId": record.get("agentId") or "codex", "receivedAt": record["receivedAt"],
            "scope": {"moduleCount": record["scope"]["moduleCount"], "fileCount": record["scope"]["fileCount"], "codeLines": record["scope"]["codeLines"],
                      "moduleIds": list(record["scope"].get("moduleIds", [])), "moduleLabels": module_labels},
        }
        json_write(request_path, public_record)
        status = {"requestId": request_id, "status": "queued", "receivedAt": record["receivedAt"], "requestPath": str(request_path), "logPath": str(log_path), "_internalRequestPath": str(internal_request_path), "_internalLogPath": str(internal_log_path), "agentId": public_record["agentId"], "project": public_record["project"], "selectedPlan": public_record["selectedPlan"], "scope": public_record["scope"]}
        append_log(log_path, "任务已创建，等待本机执行助手启动。")
        json_write(status_path, status)
        with self.lock:
            self.jobs[request_id] = status
        try:
            adapter = resolve_adapter(self.root, request.get("agentId"))
            status["agentLabel"] = adapter.label
            command = build_command(adapter, self.root, internal_request_path, result_path)
            log_handle = open(internal_log_path, "a", encoding="utf-8")
            # Keep the unattended task observable. On Windows a dedicated
            # console shows Codex's planning/repair progress instead of an
            # empty command window; other platforms retain quiet background
            # behavior.
            popen_kwargs = {
                "cwd": str(self.root),
                "stdin": subprocess.DEVNULL,
                "stdout": log_handle,
                "stderr": subprocess.STDOUT,
            }
            if os.name == "nt":
                # Keep console-control events from the bridge host out of the
                # unattended Codex child process.
                popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(command, **popen_kwargs)
            log_handle.close()
        except (OSError, FileNotFoundError) as exc:
            try:
                log_handle.close()
            except (UnboundLocalError, AttributeError):
                pass
            status.update({"status": "failed", "error": str(exc), "finishedAt": now_iso()})
            Path(log_path).write_text("任务启动失败：{}\n".format(str(exc)), encoding="utf-8")
            json_write(status_path, status)
            return status
        status.update({"status": "running", "pid": process.pid, "resultPath": str(result_path)})
        json_write(status_path, status)
        with self.lock:
            self.processes[request_id] = process
        thread = threading.Thread(target=self._watch, args=(request_id, process, status_path, log_path), daemon=True)
        thread.start()
        return status

    def _watch(self, request_id, process, status_path, log_path):
        exit_code = process.wait()
        with self.lock:
            status = dict(self.jobs.get(request_id, {}))
            self.processes.pop(request_id, None)
        if status.get("status") == "cancelled":
            status.update({"exitCode": exit_code, "finishedAt": status.get("finishedAt") or now_iso()})
            append_log(log_path, "任务已确认停止。")
        else:
            status.update({"status": "completed" if exit_code == 0 else "failed", "exitCode": exit_code, "finishedAt": now_iso()})
            append_log(log_path, "任务已完成。" if exit_code == 0 else "任务执行失败，退出码：{}。".format(exit_code))
        json_write(status_path, status)
        with self.lock:
            self.jobs[request_id] = status

    def cancel_job(self, request_id):
        status_path = self.queue_dir / (request_id + ".status.json")
        if not status_path.is_file():
            return None
        with self.lock:
            status = dict(self.jobs.get(request_id) or json_read(status_path))
            if status.get("status") in {"completed", "failed", "cancelled"}:
                return status
            status.update({"status": "cancelled", "cancelRequestedAt": now_iso(), "finishedAt": now_iso()})
            self.jobs[request_id] = status
            process = self.processes.get(request_id)
            process_pid = process.pid if process is not None else status.get("pid")
        json_write(status_path, status)
        append_log(self.queue_dir / (request_id + ".log"), "收到取消请求，正在停止本机 AI。")
        process_running = process is not None and process.poll() is None
        if process_running or (process is None and isinstance(process_pid, int) and process_pid > 0):
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process_pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
                    )
                else:
                    process.terminate()
            except OSError:
                pass
        return status

    def get_job(self, request_id):
        path = self.queue_dir / (request_id + ".status.json")
        if not path.is_file():
            return None
        status = json_read(path)
        status["progress"] = progress_from_log(status)
        status["updatedAt"] = now_iso()
        status.pop("requestPath", None)
        status.pop("logPath", None)
        status.pop("_internalRequestPath", None)
        status.pop("_internalLogPath", None)
        return status


class Handler(BaseHTTPRequestHandler):
    server_version = "ArchitectureRepairBridge/1"

    def _send(self, code, value):
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        origin = self.headers.get("Origin")
        if origin == "null":
            self.send_header("Access-Control-Allow-Origin", "null")
        elif origin:
            parsed_origin = urlparse(origin)
            if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {"127.0.0.1", "localhost"}:
                self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        parsed = urlparse(self.path)
        prefix = "/repair-requests/"
        if parsed.path.startswith(prefix):
            request_id = unquote(parsed.path[len(prefix):]).strip()
            status = self.server.bridge.get_job(request_id)
            if status is None:
                self._send(404, {"error": "找不到请求"})
            else:
                self._send(200, status)
            return
        if parsed.path == "/health":
            self._send(200, {"status": "ok", "projectRoot": str(self.server.bridge.root),
                             "apiVersion": 2, "cancelSupported": True})
            return
        if parsed.path == "/agents":
            self._send(200, {"agents": available_adapters(self.server.bridge.root)})
            return
        self._send(404, {"error": "未知路径"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        prefix = "/repair-requests/"
        if not parsed.path.startswith(prefix):
            self._send(404, {"error": "未知路径"})
            return
        request_id = unquote(parsed.path[len(prefix):]).strip()
        status = self.server.bridge.cancel_job(request_id)
        if status is None:
            self._send(404, {"error": "找不到请求"})
        else:
            self._send(200, status)

    def do_POST(self):
        if urlparse(self.path).path != "/repair-requests":
            self._send(404, {"error": "未知路径"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY:
                raise ValueError("请求大小无效")
            request = enrich_request(json.loads(self.rfile.read(length).decode("utf-8")))
            validate_request(request, self.server.bridge.root)
            status = self.server.bridge.create_job(request)
            self._send(202 if status["status"] in {"queued", "running"} else 503, status)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})

    def log_message(self, fmt, *args):
        return


def main():
    parser = argparse.ArgumentParser(description="本地架构修复请求桥接服务")
    parser.add_argument("--root", required=True, help="允许修复的目标项目根目录")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--queue-dir", help="请求队列目录，默认 <root>/.codemap/repair-requests")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    queue_dir = Path(args.queue_dir).resolve() if args.queue_dir else root / ".codemap" / "repair-requests"
    bridge = BridgeState(root, queue_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.bridge = bridge
    print("repair bridge listening on http://127.0.0.1:{}/ (project={})".format(args.port, root), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
