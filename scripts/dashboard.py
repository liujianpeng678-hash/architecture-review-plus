#!/usr/bin/env python3
"""Build and optionally open the report dashboard and free module-map projection.

The dashboard never mutates project source files. Its optional module-map link is
generated from the unchanged ``architecture-review`` template and the current
``modules.json`` state.
"""

import argparse
import html
import importlib.util
import json
import os
from pathlib import Path
import webbrowser

from render import load_standard, normalize_architecture
from repair_bridge import DEFAULT_BRIDGE_ORIGIN, ensure_bridge


LENS_RISK_HINTS = {
    "split": "如果不处理，新增功能可能继续堆到不合适的地方，改动范围会扩大。",
    "connect": "如果不处理，一处接口变化可能影响更多地方并形成回归。",
    "change": "如果不处理，内容更新可能越来越依赖手工改代码。",
    "protect": "如果不处理，问题可能无法及时发现、定位或恢复。",
}

PLAN_DEFS = (
    ("short-term", "短期方案", 1, "先压住最高风险，恢复关键路径，降低近期发布和回归风险。"),
    ("long-term", "长期维护方案", 5, "整理重复职责和公共边界，让后续需求可以持续演进。"),
    ("perfect", "完美方案", 25, "完成全量治理、证据补齐和回归保护，追求长期最低维护成本。"),
)

STATUS_ZH = {"good": "良好", "warning": "警告", "risk": "风险", "unknown": "未知"}
SEVERITY_ZH = {"HIGH": "高风险", "MED": "中风险", "LOW": "低风险", "UNKNOWN": "待确认"}

FINDING_ZH = {
    "Stale writer locks remain fail-closed and require explicit operator cleanup; cleanup failures now emit a diagnostic instead of being silently swallowed.":
        "陈旧的写入锁会安全地阻止并发写入，但仍需要操作员显式清理；清理失败现在会输出诊断信息，不再被静默吞掉。",
    "The CLI still coordinates publish and verify phases in a large orchestration file, but snapshot and impact analysis responsibilities now live in dedicated modules and child-process failures are fail-closed.":
        "命令行仍在一个较大的编排文件中协调发布和校验阶段；快照与影响分析已拆到独立模块，但子进程失败仍会安全阻断流程。",
    "Unversioned states without an injected standard use the bundled standard as an explicit bootstrap fallback; invalid project overrides fail closed.":
        "没有注入审计标准的未版本化状态会显式使用内置标准启动；无效的项目覆盖标准会安全失败。",
}


def finding_text_zh(finding):
    """Prefer an explicit translation and never leak an English-only finding into zh UI."""
    text = finding.get("textZh") or FINDING_ZH.get(finding.get("text"))
    if text:
        return text
    original = str(finding.get("text") or "").strip()
    if not original:
        return "审计发现未提供具体说明，请在下一轮独立审计中补充证据。"
    return "该模块存在待处理的审计问题；请结合审计位置和标签安排修复。"


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _free_map_skill_dir():
    """Locate the explicit free read-only renderer without modifying it."""
    configured = os.environ.get("ARCHITECTURE_REVIEW_MAP_SKILL_DIR")
    if configured:
        candidate = Path(configured).resolve()
        if (candidate / "scripts" / "render.py").is_file() and (candidate / "assets" / "template.html").is_file():
            return candidate
    # Use the explicit free read-only package as the shared map renderer.
    return Path(__file__).resolve().parents[2] / "architecture-review-report-only"


def _free_map_plan_panel(plans, root, bridge_url, progress_url):
    """Return the dashboard-equivalent repair-plan panel for the module map."""
    payload = json.dumps({
        "project": Path(root).name,
        "projectRoot": str(Path(root).resolve()),
        "bridgeUrl": bridge_url,
        "progressUrl": progress_url,
        "plans": plans,
    }, ensure_ascii=False).replace("</", "<\\/")
    return """
<section class="free-plan-section" id="freePlanSection">
  <div class="free-plan-inner">
    <div class="free-plan-heading"><h2>选择修复方案</h2><p>选择方案后即可开始执行。</p></div>
    <div id="freePlans" class="free-plan-grid"></div>
    <section id="freeSelection" class="free-selection" hidden></section>
  </div>
</section>
<style id="report-only-free-plan">
  .free-plan-section{background:#f4f6f8;color:#17202a;border-top:1px solid #d9dee3}
  .free-plan-inner{max-width:1120px;margin:0 auto;padding:28px 20px 56px}
  .free-plan-heading h2{font-size:22px;margin:0 0 7px}.free-plan-heading p{color:#68737d;font-size:14px;margin:0}
  .free-plan-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:18px}
  .free-plan-card,.free-selection{background:#fff;border:1px solid #d9dee3;border-radius:8px;padding:18px}
  .free-plan-card{display:flex;flex-direction:column;gap:12px;min-height:142px}
  .free-plan-card.selected{border-color:#1c6b52;box-shadow:0 0 0 2px #c6e5d8}
  .free-plan-card.satisfied{background:#eef0f2;border-color:#c8cdd2;color:#7a828b}
  .free-plan-card.satisfied .free-plan-credits{color:#7a828b}.free-plan-status{font-size:13px;font-weight:650;color:#7a828b}
  .free-plan-card h3{font-size:19px;margin:0}.free-plan-credits{font-size:28px;font-weight:700;color:#1c6b52}
  .free-plan-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
  .free-plan-section button{border:0;border-radius:6px;padding:10px 13px;background:#1c6b52;color:#fff;cursor:pointer;font-weight:600}
  .free-plan-section button.secondary{background:#e8edf0;color:#17202a}
  .free-plan-section button:disabled{opacity:.65;cursor:wait}
  .free-selection{margin-top:18px}.free-selection h2{font-size:19px;margin:0 0 12px}
  .free-plan-metrics{display:flex;gap:18px;flex-wrap:wrap}.free-plan-metric b{display:block;font-size:21px}.free-plan-metric span{color:#68737d;font-size:12px}
  .free-plan-note{color:#68737d;font-size:13px;margin:12px 0}.free-plan-workflow{margin:0 0 12px;padding:12px;background:#eef6f2;border:1px solid #bfdccc;border-radius:6px;line-height:1.5}
  .free-plan-workflow.error{background:#fff2f0;border-color:#e0aaa3;color:#8b3027}
  .free-map-dashboard-link{color:#2f63d9;font-size:12px;font-weight:650;text-decoration:none;white-space:nowrap}
  .free-map-dashboard-link:hover{text-decoration:underline}
  @media(max-width:800px){.free-plan-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
  @media(max-width:520px){.free-plan-inner{padding:22px 12px 40px}.free-plan-grid{grid-template-columns:1fr}}
</style>
<script>
const FREE_PLAN_DATA=__FREE_PLAN_DATA__;
const freeEsc=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;", "'":"&#39;"}[c]));
const freePlansRoot=document.querySelector("#freePlans");
const freeSelection=document.querySelector("#freeSelection");
 function freeShowProgressBubble(href){let bubble=document.querySelector("#architectureProgressBubble");if(!bubble){bubble=document.createElement("button");bubble.id="architectureProgressBubble";bubble.type="button";bubble.title="打开修复进度";bubble.setAttribute("aria-label","打开修复进度");bubble.style.cssText="position:fixed;right:18px;bottom:18px;width:56px;height:56px;border:2px solid #1c6b52;border-radius:50%;background:#fff;box-shadow:0 6px 20px rgba(23,32,42,.26);cursor:grab;touch-action:none;z-index:1000";bubble.innerHTML="<span style=\\\"display:block;width:13px;height:13px;margin:auto;border-radius:50%;background:#1c6b52\\\"></span>";document.body.appendChild(bubble);let drag=null;bubble.addEventListener("pointerdown",event=>{drag={x:event.clientX,y:event.clientY,left:bubble.offsetLeft,top:bubble.offsetTop,moved:false};bubble.dataset.dragged="";bubble.setPointerCapture?.(event.pointerId);bubble.style.cursor="grabbing"});bubble.addEventListener("pointermove",event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)>4||Math.abs(dy)>4)drag.moved=true;bubble.style.left=Math.max(0,Math.min(window.innerWidth-bubble.offsetWidth,drag.left+dx))+"px";bubble.style.top=Math.max(0,Math.min(window.innerHeight-bubble.offsetHeight,drag.top+dy))+"px";bubble.style.right="auto";bubble.style.bottom="auto"});const endDrag=event=>{if(!drag)return;bubble.dataset.dragged=drag.moved?"true":"";drag=null;bubble.style.cursor="grab";if(event.pointerId!==undefined)bubble.releasePointerCapture?.(event.pointerId)};bubble.addEventListener("pointerup",endDrag);bubble.addEventListener("pointercancel",endDrag);bubble.addEventListener("click",event=>{if(bubble.dataset.dragged==="true"){event.preventDefault();bubble.dataset.dragged="";return}const popup=window.open(bubble.dataset.href,"architecture-repair-progress","width=760,height=680");if(popup){bubble.remove();popup.focus?.()}})}bubble.dataset.href=href||""}window.addEventListener("message",event=>{if(event.data?.type!=="architecture-progress-window"||!event.source)return;if(event.data.minimized)freeShowProgressBubble(event.data.href);else document.querySelector("#architectureProgressBubble")?.remove()});
function freeDownloadJson(value,name){const safe={...value};delete safe.plannerSkill;delete safe.executionSkill;delete safe.workflow;delete safe.acceptance;const blob=new Blob([JSON.stringify(safe,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();URL.revokeObjectURL(a.href)}
function freeSelectPlan(plan){
  if(!plan || plan.satisfied)return;
  document.querySelectorAll(".free-plan-card").forEach(card=>card.classList.toggle("selected",card.dataset.id===plan.id));
  freeSelection.hidden=false;
  freeSelection.innerHTML="<h2>已选择："+freeEsc(plan.name)+"</h2><div class='free-plan-metrics'><div class='free-plan-metric'><b>"+plan.moduleCount+"</b><span>模块数量</span></div><div class='free-plan-metric'><b>"+plan.fileCount+"</b><span>文件数量</span></div><div class='free-plan-metric'><b>"+Number(plan.codeLines).toLocaleString()+"</b><span>预计修改代码行数</span></div></div><p class='free-plan-note'>资源消耗为短期方案的 "+plan.credits+" 倍。</p><div class='free-plan-actions'><button id='freeStart'>开始规划并修复</button><button class='secondary' id='freeExport'>导出请求</button><button class='secondary' id='freeClear'>取消选择</button></div>";
  const request={requestVersion:"architecture-review-repair/v1",project:FREE_PLAN_DATA.project,projectRoot:FREE_PLAN_DATA.projectRoot,selectedPlan:plan.id,plannerSkill:"project-blueprint-planner",executionSkill:"plan-execution-orchestrator",workflow:["读取当前已完成的审查结果并生成计划","按依赖顺序逐项修复","按已有审查结论独立验收每项修复","未达标继续下一项；失败则回滚并重新规划"],scope:{moduleCount:plan.moduleCount,fileCount:plan.fileCount,codeLines:plan.codeLines,moduleIds:plan.moduleIds,files:plan.files},acceptance:{target:"达到所选方案门槛",stopOn:["真实阻塞","规划门禁失败","独立验收失败且无法安全回滚"]}};
  const showStatus=(message,ok)=>{freeSelection.querySelector(".free-plan-workflow")?.remove();freeSelection.querySelector(".free-plan-actions").insertAdjacentHTML("beforebegin","<p class='free-plan-workflow "+(ok?"":"error")+"'>"+freeEsc(message)+"</p>")};
   document.querySelector("#freeStart").onclick=async()=>{const button=document.querySelector("#freeStart");button.disabled=true;button.textContent="正在提交…";const popup=window.open("about:blank","architecture-repair-progress","width=760,height=680");try{const response=await fetch(FREE_PLAN_DATA.bridgeUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(request)});const result=await response.json();if(!response.ok)throw new Error(result.error||"本机 AI 未接受请求");localStorage.setItem("architecture-review-active-request",result.requestId);showStatus("请求已发送给本机 AI。它将读取已有审查结果，先规划，再逐项修复和验收。请求编号："+result.requestId,true);button.textContent="已发送";if(popup&&!popup.closed)popup.location.href=new URL(FREE_PLAN_DATA.progressUrl,location.href).href+"?requestId="+encodeURIComponent(result.requestId)}catch(error){if(popup&&!popup.closed)popup.close();showStatus("未能连接本机 AI："+error.message+"。可以先导出请求文件。",false);button.disabled=false;button.textContent="重试提交"}};
  document.querySelector("#freeExport").onclick=()=>freeDownloadJson(request,plan.id+"-repair-request.json");
   document.querySelector("#freeClear").onclick=async()=>{const button=document.querySelector("#freeClear"),id=localStorage.getItem("architecture-review-active-request");if(!id){freeSelection.hidden=true;document.querySelectorAll(".free-plan-card").forEach(card=>card.classList.remove("selected"));return}button.disabled=true;button.textContent="正在停止…";try{const response=await fetch(FREE_PLAN_DATA.bridgeUrl+"/"+encodeURIComponent(id),{method:"DELETE"});const value=await response.json();if(!response.ok)throw new Error(value.error||"本机 AI 未停止");localStorage.removeItem("architecture-review-active-request");freeSelection.hidden=true;document.querySelectorAll(".free-plan-card").forEach(card=>card.classList.remove("selected"))}catch(error){button.disabled=false;button.textContent="取消选择";showStatus("未能停止本机 AI："+error.message,false)}};
}
FREE_PLAN_DATA.plans.forEach(plan=>{const done=!!plan.satisfied;const status=done?"<span class='free-plan-status'>已满足</span>":"";const action=done?"<button type='button' disabled aria-disabled='true'>已满足</button>":"<button type='button' data-free-select='"+freeEsc(plan.id)+"'>选择方案</button>";freePlansRoot.insertAdjacentHTML("beforeend","<article class='free-plan-card"+(done?" satisfied":"")+"' data-id='"+freeEsc(plan.id)+"'><h3>"+freeEsc(plan.name)+"</h3><div class='free-plan-credits'>"+plan.credits+" 倍</div>"+status+"<div class='free-plan-actions'>"+action+"</div></article>")});
document.querySelectorAll("[data-free-select]").forEach(button=>button.onclick=()=>freeSelectPlan(FREE_PLAN_DATA.plans.find(plan=>plan.id===button.dataset.freeSelect)));
</script>
""".replace("__FREE_PLAN_DATA__", payload)


def build_free_module_map(state, state_path):
    """Render the free-copy module-map experience using the read-only renderer.

    Keeping the template and renderer owned by the original skill preserves its
    search, grade/tag filters, module details, and dependency highlighting. The
    report-only copy only supplies the current state and never edits that library.
    """
    skill_dir = _free_map_skill_dir()
    renderer_path = skill_dir / "scripts" / "render.py"
    template_path = skill_dir / "assets" / "template.html"
    if not renderer_path.is_file() or not template_path.is_file():
        raise FileNotFoundError(
            "free module-map renderer is unavailable: {}".format(skill_dir)
        )
    spec = importlib.util.spec_from_file_location(
        "architecture_review_free_renderer", str(renderer_path)
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load test-edition module-map renderer")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    template = template_path.read_text(encoding="utf-8")
    standard = renderer.load_standard(state_path)
    page = renderer.render_html(state, template, standard)
    # The free copy opens the module map directly. Keep the
    # professional map interactions, but remove the lens/evidence shell and
    # controls that lead back to it from the visible surface.
    root = Path(state_path).resolve().parent.parent
    bridge_url = os.environ.get("ARCHITECTURE_REPAIR_BRIDGE_URL", DEFAULT_BRIDGE_ORIGIN + "/repair-requests")
    progress_url = os.environ.get("ARCHITECTURE_REPAIR_PROGRESS_URL", "repair-progress.html")
    plan_panel = _free_map_plan_panel(plan_data(state, root), root, bridge_url, progress_url)
    page = page.replace(
        '<div class="spacer"></div>',
        '<div class="spacer"></div><a id="reportOnlyDashboardLink" class="free-map-dashboard-link" href="audit-dashboard.html">返回仪表盘</a>',
        1,
    )
    projection_css = """
<style id="report-only-free-map">
  /* The free copy opens directly on the module map. Keep the map interactions,
     while removing the four-lens audit shell and its eight-dimension links. */
  .lens-app,.lens-top,.lens-tabs,.lens-main{display:none!important}
  .app,.app.open{display:grid!important;position:relative;min-height:100vh;height:100vh;z-index:30;background:var(--bg)}
  #homeBtn,#stdBtn,#reportBtn,#spineBtn,#versionBtn{display:none!important}
</style>
"""
    page = page.replace("</head>", projection_css + "</head>", 1)
    return page.replace("</body>", plan_panel + "</body>", 1)


def module_files(module, root):
    root_path = Path(root).resolve()
    found = set()
    patterns = module.get("paths") or []
    if isinstance(patterns, str):
        patterns = [patterns]
    for pattern in patterns:
        try:
            candidates = root_path.glob(str(pattern))
        except (ValueError, OSError):
            candidates = ()
        for candidate in candidates:
            if candidate.is_file():
                found.add(candidate.resolve())
    if module.get("path"):
        candidate = (root_path / str(module["path"])).resolve()
        if candidate.is_file():
            found.add(candidate)
    return found


def module_stats(module, root):
    counts = {severity: 0 for severity in ("HIGH", "MED", "LOW")}
    for finding in module.get("findings") or []:
        if finding.get("sev") in counts:
            counts[finding["sev"]] += 1
    root_path = Path(root).resolve()
    files = module_files(module, root)
    return {
        "files": sorted(str(path.relative_to(root_path)).replace("\\", "/") for path in files),
        "fileCount": len(files),
        "loc": module.get("loc") or 0,
        "findingCounts": counts,
    }


def is_short_priority(module):
    score = module.get("score")
    findings = module.get("findings") or []
    severities = {finding.get("sev") for finding in findings}
    # Keep the short-term plan actionable when the audit has confirmed
    # medium-risk findings but no HIGH findings or sub-75 scores.
    return score is None or score < 75 or "HIGH" in severities or bool(findings and score < 85)


def is_long_priority(module):
    score = module.get("score")
    return is_short_priority(module) or bool(module.get("findings")) or score is None or score < 85


def plan_satisfied(plan_id, modules):
    """Return whether the current audit already meets a plan's score/severity gate."""
    if not modules:
        return False
    main_modules = [module for module in modules if module.get("coupling") in {"core", "high"}]
    if not main_modules:
        main_modules = list(modules)

    def meets(module, minimum, blocked):
        severities = {finding.get("sev") for finding in module.get("findings") or []}
        return (isinstance(module.get("score"), (int, float))
                and module.get("score") >= minimum
                and not severities.intersection(blocked))

    if plan_id == "short-term":
        return all(meets(module, 75, {"HIGH"}) for module in main_modules)
    if plan_id == "long-term":
        return all(meets(module, 80, {"HIGH"}) for module in modules)
    return all(meets(module, 90, {"HIGH", "MED"}) for module in modules)


def plan_data(state, root):
    modules = state.get("modules") or []
    stats = {module.get("id"): module_stats(module, root) for module in modules}
    groups = (
        [module for module in modules if is_short_priority(module)],
        [module for module in modules if is_long_priority(module)],
        list(modules),
    )
    plans = []
    for (plan_id, name, credits, effect), selected in zip(PLAN_DEFS, groups):
        selected_stats = [stats[module.get("id")] for module in selected]
        files = sorted({path for item in selected_stats for path in item["files"]})
        counts = {
            severity: sum(item["findingCounts"][severity] for item in selected_stats)
            for severity in ("HIGH", "MED", "LOW")
        }
        plans.append({
            "id": plan_id, "name": name, "credits": credits, "effect": effect,
            "satisfied": plan_satisfied(plan_id, modules),
            "selection": (
                "优先处理最高风险模块。" if plan_id == "short-term" else
                "覆盖问题模块及其直接消费者。" if plan_id == "long-term" else
                "覆盖所有正式模块和未闭合问题。"
            ),
            "moduleCount": len(selected), "moduleIds": sorted(module.get("id") for module in selected),
            "moduleLabels": {module.get("id"): module.get("label", module.get("id")) for module in selected},
            "fileCount": len(files), "files": files,
            "codeLines": sum(item["loc"] for item in selected_stats),
            "findingCounts": counts,
        })
    return plans


def issue_data(state):
    lenses, dimensions, version, delta = normalize_architecture(state)
    modules = state.get("modules") or []
    labels = {module.get("id"): module.get("label", module.get("id")) for module in modules}
    result = []
    for lens in lenses:
        issues = []
        for issue in lens.get("issues") or []:
            issues.append({
                "dimension": issue.get("labelZh") or issue.get("label"),
                "status": issue.get("status"),
                "statusLabel": STATUS_ZH.get(issue.get("status"), issue.get("status")),
                "summary": issue.get("summary"),
                "recommendation": issue.get("recommendation"),
                "relatedModules": [labels[mid] for mid in issue.get("relatedModules") or [] if mid in labels],
            })
        if not issues and lens.get("status") in {"warning", "risk", "unknown"}:
            issues.append({"dimension": lens.get("labelZh") or lens.get("label"),
                           "status": lens.get("status"),
                           "statusLabel": STATUS_ZH.get(lens.get("status"), lens.get("status")),
                           "summary": lens.get("summary"),
                           "recommendation": "", "relatedModules": []})
        result.append({
            "id": lens["id"], "label": lens["labelZh"],
            "question": lens["questionZh"],
            "status": lens["status"], "statusLabel": STATUS_ZH.get(lens["status"], lens["status"]),
            "score": lens["score"], "summary": lens["summary"],
            "issues": issues, "nextRisk": LENS_RISK_HINTS[lens["id"]],
        })
    module_issues = []
    for module in modules:
        findings = module.get("findings") or []
        for finding in findings:
            module_issues.append({
                "label": module.get("label") or module.get("id"),
                "severity": finding.get("sev") or "LOW",
                "severityLabel": SEVERITY_ZH.get(finding.get("sev") or "LOW", "待确认"),
                "location": finding.get("loc") or "审计记录",
                "summary": finding_text_zh(finding),
                "score": module.get("score"),
            })
        if module.get("score") is None and not findings:
            module_issues.append({
                "label": module.get("label") or module.get("id"),
                "severity": "UNKNOWN",
                "severityLabel": "待确认",
                "location": "评分记录",
                "summary": "该模块尚未完成独立评分。",
                "score": None,
            })
    severity_rank = {"HIGH": 0, "MED": 1, "LOW": 2, "UNKNOWN": 3}
    module_issues.sort(key=lambda item: (severity_rank.get(item["severity"], 4), item["score"] is not None, item["score"] or 0))
    top_issues = module_issues[:3]
    potential_issues = []
    for lens in result:
        if lens["status"] in {"risk", "warning", "unknown"}:
            potential_issues.append({
                "title": "潜在影响 {}".format(len(potential_issues) + 1),
                "summary": lens["nextRisk"],
                "status": lens["statusLabel"],
            })
    if len(potential_issues) < 3:
        for lens in result:
            if lens["status"] == "good":
                potential_issues.append({
                    "title": "潜在影响 {}".format(len(potential_issues) + 1),
                    "summary": "如果后续变更绕过现有边界，这一方面可能出现新的回归。",
                    "status": "关注",
                })
            if len(potential_issues) >= 3:
                break
    # Prefer a complete dimension audit. Older retained audits may have
    # independent module scores but no dimension-level score fields yet; in
    # that case the module average is the honest project-level fallback.
    dimension_scores = [item.get("score") for item in dimensions
                        if isinstance(item.get("score"), (int, float))]
    if dimensions and len(dimension_scores) == len(dimensions):
        architecture_score = round(sum(dimension_scores) / len(dimension_scores))
    else:
        module_scores = [module.get("score") for module in modules
                         if isinstance(module.get("score"), (int, float))]
        architecture_score = round(sum(module_scores) / len(module_scores)) if module_scores else None
    return {"topIssues": top_issues[:3], "potentialIssues": potential_issues[:3],
            "version": version.get("version"), "auditDelta": delta,
            "architectureScore": architecture_score}


def build_module_map(state, root):
    """Build a standalone, beginner-readable dependency map with pan/zoom."""
    modules = state.get("modules") or []
    bands = state.get("bands") or []
    band_order = [item.get("id") for item in bands if isinstance(item, dict) and item.get("id")]
    for module in modules:
        if module.get("band") not in band_order:
            band_order.append(module.get("band") or "other")
    nodes = []
    positions = {}
    for band_index, band_id in enumerate(band_order):
        selected = [item for item in modules if (item.get("band") or "other") == band_id]
        for index, module in enumerate(selected):
            node = {
                "id": module.get("id"), "label": module.get("label") or module.get("id"),
                "band": band_id, "score": module.get("score"), "grade": module.get("grade"),
                "loc": module.get("loc") or 0, "desc": module.get("desc") or "",
                "coupling": module.get("coupling") or "", "x": 180 + index * 230,
                "y": 90 + band_index * 150,
            }
            nodes.append(node)
            positions[node["id"]] = (node["x"], node["y"])
    edges = []
    for module in modules:
        target = positions.get(module.get("id"))
        if not target:
            continue
        for dep in module.get("deps") or []:
            source = positions.get(dep)
            if source:
                edges.append({"from": dep, "to": module.get("id")})
    payload = json.dumps({"project": (state.get("meta") or {}).get("project") or Path(root).name,
                          "nodes": nodes, "edges": edges, "bandLabels": {
                              item.get("id"): item.get("t") or item.get("label") or item.get("id")
                              for item in bands if isinstance(item, dict) and item.get("id")
                          }}, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(str((state.get("meta") or {}).get("project") or Path(root).name))
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>模块图 - %s</title><style>
body{margin:0;background:#f4f6f8;color:#17202a;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}.shell{padding:18px;max-width:1500px;margin:auto}header{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:12px}h1{font-size:24px;margin:0}.muted{color:#68737d;font-size:13px}.toolbar{display:flex;gap:7px;flex-wrap:wrap}.toolbar button{border:1px solid #cbd4da;background:#fff;color:#17202a;border-radius:5px;padding:8px 11px;cursor:pointer;font-weight:600}.toolbar button:hover{border-color:#1c6b52;color:#1c6b52}.layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:12px}.map-panel,.detail{background:#fff;border:1px solid #d9dee3;border-radius:8px}.map-panel{overflow:hidden;min-height:620px;position:relative}.map-panel svg{width:100%%;height:620px;display:block;background:#fbfcfd;cursor:grab}.map-panel svg.dragging{cursor:grabbing}.edge{stroke:#9aa8b2;stroke-width:2;marker-end:url(#arrow);opacity:.7}.node{cursor:pointer}.node rect{fill:#fff;stroke:#b6c1c8;stroke-width:2;rx:7}.node text{pointer-events:none}.node .label{font-size:13px;font-weight:700;fill:#17202a}.node .meta{font-size:11px;fill:#68737d}.node.good rect{stroke:#4d9a73}.node.warn rect{stroke:#d59a36}.node.risk rect{stroke:#c65345}.node.selected rect{stroke:#1c6b52;stroke-width:4}.detail{padding:16px;height:max-content}.detail h2{font-size:18px;margin:0 0 8px}.detail dl{display:grid;grid-template-columns:80px 1fr;gap:7px;font-size:13px}.detail dt{color:#68737d}.detail dd{margin:0;overflow-wrap:anywhere}.search{width:180px;padding:8px;border:1px solid #cbd4da;border-radius:5px}@media(max-width:850px){.layout{grid-template-columns:1fr}.detail{order:-1}.map-panel,.map-panel svg{min-height:500px;height:500px}}@media(max-width:520px){.shell{padding:12px}.toolbar{width:100%%}.search{flex:1;min-width:140px}}
</style></head><body><main class="shell"><header><div><h1>模块图</h1><p class="muted">%s · 可展开、缩小、拖拽查看依赖关系</p></div><div class="toolbar"><input id="search" class="search" placeholder="搜索模块"><button id="zoomIn" type="button" title="放大模块图">放大</button><button id="zoomOut" type="button" title="缩小模块图">缩小</button><button id="reset" type="button" title="恢复默认视图">重置视图</button></div></header><section class="layout"><div class="map-panel"><svg id="map" viewBox="0 0 1200 900" role="img" aria-label="模块依赖图"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#9aa8b2"></path></marker></defs><g id="scene"></g></svg></div><aside class="detail"><h2>选择一个模块</h2><p class="muted">点击节点查看职责、分数和代码行数。</p></aside></section></main><script>
const DATA=%s;const svg=document.querySelector("#map"),scene=document.querySelector("#scene"),detail=document.querySelector(".detail");let scale=1,panX=0,panY=0,drag=null;const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const nodeById=new Map(DATA.nodes.map(n=>[n.id,n]));function cls(n){return n.score==null?"risk":n.score<75?"risk":n.score<85?"warn":"good"}function render(){scene.innerHTML="";DATA.edges.forEach(e=>{const a=nodeById.get(e.from),b=nodeById.get(e.to);if(!a||!b)return;const line=document.createElementNS("http://www.w3.org/2000/svg","line");line.setAttribute("class","edge");line.setAttribute("x1",a.x);line.setAttribute("y1",a.y+28);line.setAttribute("x2",b.x);line.setAttribute("y2",b.y-28);scene.appendChild(line)});DATA.nodes.forEach(n=>{const g=document.createElementNS("http://www.w3.org/2000/svg","g");g.dataset.id=n.id;g.setAttribute("class","node "+cls(n));g.setAttribute("transform",`translate(${n.x-95},${n.y-28})`);g.innerHTML=`<rect width="190" height="56"></rect><text class="label" x="10" y="21">${esc(n.label)}</text><text class="meta" x="10" y="41">分数 ${n.score==null?"待评分":esc(n.score)+" · "+esc(n.grade||"")} · ${Number(n.loc||0).toLocaleString()} 行</text>`;g.onclick=()=>select(n.id);scene.appendChild(g)});applyTransform()}function select(id){const n=nodeById.get(id);if(!n)return;document.querySelectorAll(".node").forEach(x=>x.classList.toggle("selected",x.dataset.id===id));detail.innerHTML=`<h2>${esc(n.label)}</h2><dl><dt>模块 ID</dt><dd>${esc(n.id)}</dd><dt>职责</dt><dd>${esc(n.desc||"未提供")}</dd><dt>架构分数</dt><dd>${n.score==null?"待评分":esc(n.score)+" / 100"}</dd><dt>代码行数</dt><dd>${Number(n.loc||0).toLocaleString()} 行</dd><dt>耦合级别</dt><dd>${esc(n.coupling||"未提供")}</dd><dt>所属层</dt><dd>${esc(DATA.bandLabels[n.band]||n.band||"未分层")}</dd></dl>`}function applyTransform(){scene.setAttribute("transform",`translate(${panX} ${panY}) scale(${scale})`)}function zoom(next){scale=Math.max(.35,Math.min(2.8,next));applyTransform()}document.querySelector("#zoomIn").onclick=()=>zoom(scale*1.2);document.querySelector("#zoomOut").onclick=()=>zoom(scale/1.2);document.querySelector("#reset").onclick=()=>{scale=1;panX=0;panY=0;applyTransform()};document.querySelector("#search").oninput=e=>{const q=e.target.value.trim().toLowerCase();document.querySelectorAll(".node").forEach(x=>x.style.opacity=!q||String(x.dataset.id).toLowerCase().includes(q)||x.textContent.toLowerCase().includes(q)?"1":".2")};svg.onwheel=e=>{e.preventDefault();zoom(scale*(e.deltaY<0?1.1:.9))};svg.onpointerdown=e=>{drag={x:e.clientX,y:e.clientY,px:panX,py:panY};svg.classList.add("dragging")};svg.onpointermove=e=>{if(!drag)return;panX=drag.px+e.clientX-drag.x;panY=drag.py+e.clientY-drag.y;applyTransform()};svg.onpointerup=svg.onpointercancel=()=>{drag=null;svg.classList.remove("dragging")};render();
</script></body></html>""" % (title, title, payload)


def build_progress_dashboard(bridge_url):
    data = json.dumps(bridge_url, ensure_ascii=False)
    return """<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>修复进度</title><style>body{margin:0;background:#f4f6f8;color:#17202a;font-family:system-ui,-apple-system,\"Segoe UI\",sans-serif}.shell{max-width:760px;margin:0 auto;padding:28px 20px}.panel{background:#fff;border:1px solid #d9dee3;border-radius:8px;padding:20px}h1{font-size:25px;margin:0 0 8px}.muted{color:#68737d;font-size:14px}.progress-head{display:flex;justify-content:space-between;gap:12px;margin-top:20px}.progress-head span{color:#1c6b52;font-weight:700}progress{display:block;width:100%%;height:12px;margin:10px 0 12px;accent-color:#1c6b52}.detail{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}.detail b{display:block;font-size:21px}.detail span{font-size:12px;color:#68737d}.state{font-size:18px;font-weight:700}.error{color:#8b3027}@media(max-width:520px){.shell{padding:16px 12px}.detail{grid-template-columns:1fr 1fr}}</style></head><body><main class=\"shell\"><section class=\"panel\"><h1>修复执行进度</h1><p id=\"project\" class=\"muted\">正在连接本机执行助手…</p><p id=\"state\" class=\"state\">等待请求</p><div class=\"progress-head\"><strong id=\"label\">等待开始</strong><span id=\"stage\">阶段 0/5</span></div><progress id=\"bar\" max=\"100\" value=\"0\"></progress><p id=\"message\" class=\"muted\">等待执行状态。</p><p id=\"elapsed\" class=\"muted\">已运行 0 秒</p><div class=\"detail\"><div><b id=\"plan\">-</b><span>修复方案</span></div><div><b id=\"modules\">-</b><span>模块数量</span></div><div><b id=\"files\">-</b><span>文件数量</span></div></div></section></main><script>const BRIDGE=%s;const id=new URLSearchParams(location.search).get(\"requestId\");const text=(v)=>String(v??\"\");let done=false;async function poll(){if(!id)return;try{const response=await fetch(BRIDGE+\"/\"+encodeURIComponent(id));const value=await response.json();const p=value.progress||{};document.querySelector(\"#project\").textContent=value.project||\"本地项目\";document.querySelector(\"#state\").textContent=value.status===\"failed\"?\"执行失败\":value.status===\"completed\"?\"已完成\":p.label||\"执行中\";document.querySelector(\"#state\").classList.toggle(\"error\",value.status===\"failed\");document.querySelector(\"#label\").textContent=p.label||\"等待状态\";document.querySelector(\"#stage\").textContent=\"阶段 \"+(p.stageNumber||0)+\"/\"+(p.stageTotal||5);document.querySelector(\"#bar\").value=Number(p.percent)||0;document.querySelector(\"#message\").textContent=p.message||\"等待下一条日志。\";document.querySelector(\"#elapsed\").textContent=\"已运行 \"+(p.elapsedSeconds||0)+\" 秒\";document.querySelector(\"#plan\").textContent=value.selectedPlan||\"-\";document.querySelector(\"#modules\").textContent=value.scope?.moduleCount??\"-\";document.querySelector(\"#files\").textContent=value.scope?.fileCount??\"-\";if((value.status===\"completed\"||value.status===\"failed\")&&!done){done=true;clearInterval(timer);if(value.status===\"completed\"&&window.opener&&!window.opener.closed)setTimeout(()=>window.opener.location.reload(),800)}}catch(error){document.querySelector(\"#message\").textContent=\"暂时无法读取进度，正在重试。\"}}poll();const timer=setInterval(poll,1000);</script></body></html>""" % data


def build_progress_dashboard(bridge_url):
    """Build the live progress view with current and upcoming modules."""
    data = json.dumps(bridge_url, ensure_ascii=False)
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>修复进度</title><style>
body{margin:0;background:#f4f6f8;color:#17202a;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}.shell{max-width:820px;margin:0 auto;padding:24px 18px}.panel{background:#fff;border:1px solid #d9dee3;border-radius:8px;padding:20px}h1{font-size:25px;margin:0 0 8px}.muted{color:#68737d;font-size:14px}.progress-head{display:flex;justify-content:space-between;gap:12px;margin-top:20px}.progress-head span{color:#1c6b52;font-weight:700}progress{display:block;width:100%%;height:12px;margin:10px 0 12px;accent-color:#1c6b52}.detail{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:20px}.detail b{display:block;font-size:21px}.detail span{font-size:12px;color:#68737d}.modules{margin-top:20px;border-top:1px solid #e1e6e9;padding-top:16px}.modules h2{font-size:15px;margin:0 0 8px}.module-list{margin:0;padding-left:20px;color:#3d4a52;font-size:13px;line-height:1.7}.module-flow-tools{display:flex;align-items:center;gap:6px;margin:0 0 8px}.module-flow-tools button{min-width:34px;height:30px;padding:0 8px;border:1px solid #cbd4da;border-radius:5px;background:#fff;color:#25333b;font-weight:700;cursor:pointer}.module-flow-tools button:hover{background:#eef6f2;border-color:#1c6b52}.module-flow-tools .flow-zoom-label{min-width:48px;text-align:center;font-size:12px;color:#68737d}.module-flow-viewport{max-height:280px;min-height:140px;overflow:auto;resize:vertical;border:1px solid #d9e0e4;border-radius:6px;background:#fbfcfd;touch-action:none;cursor:grab}.module-flow-viewport.expanded{max-height:calc(100vh - 280px);min-height:360px}.module-flow-viewport.dragging{cursor:grabbing}.module-flow{display:flex;gap:8px;align-items:flex-start;width:max-content;min-width:100%%;padding:10px;transform-origin:top left;will-change:transform}.module-chip{flex:0 0 150px;min-width:150px;border:1px solid #cbd4da;border-radius:6px;padding:9px;background:#f8fafb;font-size:12px}.module-chip.current{border-color:#1c6b52;background:#eef6f2}.module-chip.done{border-color:#8fbea6;color:#4d745e}.module-chip small{display:block;color:#68737d;margin-top:4px}.current{color:#1c6b52;font-weight:700}.state{font-size:18px;font-weight:700}.error{color:#8b3027}@media(max-width:520px){.shell{padding:14px 10px}.detail{grid-template-columns:1fr 1fr}.module-flow-viewport.expanded{max-height:calc(100vh - 250px);min-height:300px}}
</style></head>
<body><main class="shell"><section class="panel"><h1>修复执行进度</h1><p id="project" class="muted">正在连接本机执行助手…</p><p id="state" class="state">等待请求</p><div class="progress-head"><strong id="label">等待开始</strong><span id="stage">阶段 0/5</span></div><progress id="bar" max="100" value="0"></progress><p id="message" class="muted">等待执行状态。</p><p id="elapsed" class="muted">已运行 0 秒</p><div class="detail"><div><b id="plan">-</b><span>修复方案</span></div><div><b id="modules">-</b><span>模块数量</span></div><div><b id="files">-</b><span>文件数量</span></div></div><div class="modules"><div class="module-flow-tools" role="toolbar" aria-label="模块执行图控制"><button id="flowZoomOut" type="button" title="缩小模块图" aria-label="缩小模块图">−</button><button id="flowZoomReset" type="button" title="恢复模块图大小" aria-label="恢复模块图大小">100%%</button><button id="flowZoomIn" type="button" title="放大模块图" aria-label="放大模块图">＋</button><button id="flowFit" type="button" title="让全部模块适应窗口" aria-label="让全部模块适应窗口">适应</button><button id="flowExpand" type="button" title="展开模块图" aria-label="展开模块图">展开</button></div><div id="moduleFlowViewport" class="module-flow-viewport"><div id="moduleFlow" class="module-flow"></div></div><h2>当前修复模块</h2><p id="currentModule" class="current">等待本机 AI 开始处理模块。</p><h2>后续待修复模块</h2><ol id="upcomingModules" class="module-list"><li>等待规划结果。</li></ol></div></section></main>
<script>const BRIDGE=%s;const id=new URLSearchParams(location.search).get("requestId");let done=false;const escapeText=value=>String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));const label=m=>m?.label||m?.id||"未命名模块";const flowViewport=document.querySelector("#moduleFlowViewport"),flowCanvas=document.querySelector("#moduleFlow"),flowZoomLabel=document.querySelector("#flowZoomReset");let flowScale=1,flowDrag=null;function updateFlowZoom(){if(!flowCanvas)return;flowCanvas.style.transform="scale("+flowScale+")";if(flowZoomLabel)flowZoomLabel.textContent=Math.round(flowScale*100)+"%%"}function setFlowScale(next){flowScale=Math.max(.35,Math.min(2.8,next));updateFlowZoom()}function fitFlow(){if(!flowViewport||!flowCanvas||!flowCanvas.scrollWidth)return;setFlowScale(Math.max(.35,Math.min(1,(flowViewport.clientWidth-20)/flowCanvas.scrollWidth)));flowViewport.scrollLeft=0;flowViewport.scrollTop=0}function renderFlow(p,value){const root=document.querySelector("#moduleFlow"),doneIds=new Set((p.completedModules||[]).map(m=>m.id)),current=p.currentModule?.id;const all=[...(p.completedModules||[]),...(p.currentModule?[p.currentModule]:[]),...(p.upcomingModules||[])];root.innerHTML=all.length?all.map(m=>"<div class='module-chip "+(m.id===current?"current ":"")+(doneIds.has(m.id)?"done":"")+'">'+escapeText(label(m))+"<small>"+(doneIds.has(m.id)?"已完成":m.id===current?"正在修复":"待处理")+"</small></div>").join(""):"<span class='muted'>等待规划结果。</span>"}if(flowViewport){flowViewport.addEventListener("wheel",event=>{if(!event.ctrlKey&&!event.altKey)return;event.preventDefault();setFlowScale(flowScale*(event.deltaY<0?1.1:.9))},{passive:false});flowViewport.addEventListener("pointerdown",event=>{if(event.button!==0)return;flowDrag={x:event.clientX,y:event.clientY,left:flowViewport.scrollLeft,top:flowViewport.scrollTop};flowViewport.classList.add("dragging");flowViewport.setPointerCapture?.(event.pointerId)});flowViewport.addEventListener("pointermove",event=>{if(!flowDrag)return;flowViewport.scrollLeft=flowDrag.left-(event.clientX-flowDrag.x);flowViewport.scrollTop=flowDrag.top-(event.clientY-flowDrag.y)});const stopFlowDrag=event=>{if(!flowDrag)return;flowDrag=null;flowViewport.classList.remove("dragging");if(event.pointerId!==undefined)flowViewport.releasePointerCapture?.(event.pointerId)};flowViewport.addEventListener("pointerup",stopFlowDrag);flowViewport.addEventListener("pointercancel",stopFlowDrag)}document.querySelector("#flowZoomOut")?.addEventListener("click",()=>setFlowScale(flowScale/1.2));document.querySelector("#flowZoomIn")?.addEventListener("click",()=>setFlowScale(flowScale*1.2));document.querySelector("#flowZoomReset")?.addEventListener("click",()=>{setFlowScale(1);flowViewport?.scrollTo(0,0)});document.querySelector("#flowFit")?.addEventListener("click",fitFlow);document.querySelector("#flowExpand")?.addEventListener("click",event=>{const expanded=flowViewport?.classList.toggle("expanded");event.currentTarget.textContent=expanded?"收起":"展开";event.currentTarget.setAttribute("aria-label",expanded?"收起模块图":"展开模块图");event.currentTarget.setAttribute("title",expanded?"收起模块图":"展开模块图")});updateFlowZoom();async function poll(){if(!id)return;try{const response=await fetch(BRIDGE+"/"+encodeURIComponent(id));const value=await response.json();const p=value.progress||{};document.querySelector("#project").textContent=value.project||"本地项目";document.querySelector("#state").textContent=value.status==="failed"?"执行失败":value.status==="completed"?"已完成":p.label||"执行中";document.querySelector("#state").classList.toggle("error",value.status==="failed");document.querySelector("#label").textContent=p.label||"等待状态";document.querySelector("#stage").textContent="阶段 "+(p.stageNumber||0)+"/"+(p.stageTotal||5);document.querySelector("#bar").value=Number(p.percent)||0;document.querySelector("#message").textContent=p.message||"等待下一条日志。";document.querySelector("#elapsed").textContent="已运行 "+(p.elapsedSeconds||0)+" 秒";document.querySelector("#plan").textContent=value.selectedPlan||"-";document.querySelector("#modules").textContent=value.scope?.moduleCount??"-";document.querySelector("#files").textContent=value.scope?.fileCount??"-";const current=p.currentModule;document.querySelector("#currentModule").textContent=current?label(current):value.status==="completed"?"全部模块已完成":"等待本机 AI 回报当前模块";const upcoming=p.upcomingModules||[];document.querySelector("#upcomingModules").innerHTML=upcoming.length?upcoming.map(m=>"<li>"+escapeText(label(m))+"</li>").join(""):"<li>没有后续模块。</li>";renderFlow(p,value);if((value.status==="completed"||value.status==="failed")&&!done){done=true;clearInterval(timer);if(value.status==="completed"&&window.opener&&!window.opener.closed)setTimeout(()=>window.opener.location.reload(),800)}}catch(error){document.querySelector("#message").textContent="暂时无法读取进度，正在重试。"}}poll();const timer=setInterval(poll,1000);</script></body></html>""" % data


def enhance_progress_dashboard(page):
    """Let the parent page replace this popup with its draggable progress orb."""
    page = page.replace(
        "</style></head>",
        "<style>.window-toggle{position:absolute;top:14px;right:14px;width:32px;height:32px;padding:0;border:1px solid #cbd4da;border-radius:5px;background:#fff;color:#25333b;font-size:18px;line-height:1;cursor:pointer}.window-toggle:hover{background:#eef6f2;border-color:#1c6b52}</style></head>",
        1,
    )
    page = page.replace(
        '<section class="panel"><h1>',
        '<section class="panel"><button id="progressToggle" class="window-toggle" type="button" title="缩小为圆点" aria-label="缩小为圆点">−</button><h1>',
        1,
    )
    page = page.replace(
        '<div class="modules"><div class="module-flow-tools"',
        '<div class="modules"><h2>模块执行图</h2><div class="module-flow-tools"',
        1,
    )
    behavior = "<script>const progressToggle=document.querySelector('#progressToggle');progressToggle?.addEventListener('click',()=>{try{if(window.opener&&!window.opener.closed){window.opener.postMessage({type:'architecture-progress-window',minimized:true,href:window.location.href},'*');window.setTimeout(()=>window.close(),0)}}catch(error){}});</script>"
    return page.replace("</script></body></html>", "</script>" + behavior + "</body></html>", 1)


def build_dashboard(state, root):
    meta = state.get("meta") or {}
    bridge_url = os.environ.get("ARCHITECTURE_REPAIR_BRIDGE_URL", "http://127.0.0.1:8767/repair-requests")
    payload = {
        "project": meta.get("project") or Path(root).name,
        "projectRoot": str(Path(root).resolve()),
        "bridgeUrl": bridge_url,
        "progressUrl": os.environ.get("ARCHITECTURE_REPAIR_PROGRESS_URL", "repair-progress.html"),
        # The HTTP server serves the .codemap directory as its document root,
        # so the sibling map is addressed as codemap.html rather than nesting
        # .codemap a second time.
        "moduleMapUrl": os.environ.get(
            "ARCHITECTURE_REVIEW_MODULE_MAP_URL", "codemap.html"
        ),
        "issues": issue_data(state),
        "plans": plan_data(state, root),
    }
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(str(payload["project"]))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>架构审计仪表盘 - %s</title>
<style>
:root{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#17202a;background:#f4f6f8}
body{margin:0}.shell{max-width:1120px;margin:0 auto;padding:28px 20px 56px}
header{background:#17202a;color:#fff;padding:24px;border-radius:8px}h1,h2,h3,p{margin:0}
h1{font-size:28px}.muted{color:#68737d;font-size:14px}header .muted{color:#c8d0d6;margin-top:7px}
.grid{display:grid;gap:14px}.issues{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:18px}
.plans{grid-template-columns:repeat(3,minmax(0,1fr));margin-top:18px}.panel{background:#fff;border:1px solid #d9dee3;border-radius:8px;padding:18px}
.issue-card{min-height:150px}.issue-card h3{font-size:17px}.issue-card p{margin-top:8px;line-height:1.5}.severity{font-size:12px;color:#a33b2e;font-weight:700}.score-summary{display:flex;align-items:baseline;justify-content:space-between}.score-summary strong{font-size:36px;color:#1c6b52}.map-link{margin-left:auto;color:#1c6b52;font-weight:700;text-decoration:none}.map-link:hover{text-decoration:underline}
.section{margin-top:30px}.section h2{font-size:22px;margin-bottom:10px}.plan{display:flex;flex-direction:column;gap:11px}
.plan h3{font-size:19px}.plan.selected{border-color:#1c6b52;box-shadow:0 0 0 2px #c6e5d8}.plan .credits{font-size:28px;font-weight:700;color:#1c6b52}
.plan.satisfied{background:#eef0f2;border-color:#c8cdd2;color:#7a828b}.plan.satisfied .credits{color:#7a828b}.plan-status{font-size:13px;font-weight:650;color:#7a828b}
.metrics{display:flex;gap:14px;flex-wrap:wrap}.metric b{display:block;font-size:21px}.metric span{color:#68737d;font-size:12px}
.progress-box{margin:14px 0;padding:13px;background:#f7faf8;border:1px solid #d6e7dc;border-radius:6px}.progress-head{display:flex;justify-content:space-between;gap:12px}.progress-head span{color:#1c6b52;font-weight:700}progress{display:block;width:100%%;height:10px;margin:10px 0 7px;accent-color:#1c6b52}.progress-box p{margin:0;color:#68737d;font-size:13px}
button{border:0;border-radius:6px;padding:10px 13px;background:#1c6b52;color:#fff;cursor:pointer;font-weight:600}
button.secondary{background:#e8edf0;color:#17202a}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}
.empty{color:#68737d}.workflow{background:#eef6f2;border-color:#bfdccc;padding:12px;border:1px solid #bfdccc;border-radius:6px;line-height:1.5}.workflow.error{background:#fff2f0;border-color:#e0aaa3;color:#8b3027}
@media(max-width:800px){.issues,.plans{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.issues,.plans{grid-template-columns:1fr}.shell{padding:16px 12px 40px}h1{font-size:24px}}
</style></head><body><main class="shell">
<header><h1>架构审计仪表盘</h1><p class="muted">%s</p></header>
<section class="section panel score-summary"><span class="muted">架构分数</span><strong id="architectureScore">-</strong><a class="map-link" href="%s" target="_blank" rel="noopener">打开模块图</a></section>
<section class="section"><h2>目前最大的三个问题</h2><div id="topIssues" class="grid issues"></div></section>
<section class="section"><h2>选择修复方案</h2><p class="muted">选择方案后即可开始执行。</p><div id="plans" class="grid plans"></div></section>
<section id="selection" class="section panel" hidden></section></main>
<script>
const DATA=%s;
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function renderIssueList(target, items, emptyText){const root=document.querySelector(target);root.innerHTML=items.length?items.map(i=>"<article class='panel issue-card'><span class='severity'>"+esc(i.severityLabel||i.status||"关注")+"</span><h3>"+esc(i.label||i.title)+"</h3><p>"+esc(i.summary)+"</p>"+(i.location?"<p class='muted'>位置："+esc(i.location)+"</p>":"")+"</article>").join(""):"<p class='empty'>"+emptyText+"</p>"}
renderIssueList("#topIssues", DATA.issues.topIssues, "当前没有已确认的问题。");
document.querySelector("#architectureScore").textContent=DATA.issues.architectureScore==null?"待评分":DATA.issues.architectureScore+" / 100";
const selection=document.querySelector("#selection");
function downloadJson(value,name){const safe={...value};delete safe.plannerSkill;delete safe.executionSkill;delete safe.workflow;delete safe.acceptance;const blob=new Blob([JSON.stringify(safe,null,2)],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();URL.revokeObjectURL(a.href)}
function selectPlan(plan){if(!plan||plan.satisfied)return;document.querySelectorAll(".plan").forEach(c=>c.classList.toggle("selected",c.dataset.id===plan.id));selection.hidden=false;selection.innerHTML="<h2>已选择："+esc(plan.name)+"</h2><div class='metrics'><div class='metric'><b>"+plan.moduleCount+"</b><span>模块数量</span></div><div class='metric'><b>"+plan.fileCount+"</b><span>文件数量</span></div><div class='metric'><b>"+plan.codeLines.toLocaleString()+"</b><span>预计修改代码行数</span></div></div><p class='muted' style='margin-top:12px'>资源消耗为短期方案的 "+plan.credits+" 倍。</p><div class='actions'><button id='start'>开始规划并修复</button><button class='secondary' id='export'>导出请求</button><button class='secondary' id='clear'>取消选择</button></div>";localStorage.setItem("architecture-review-selected-plan",JSON.stringify(plan));const request={requestVersion:"architecture-review-repair/v1",project:DATA.project,projectRoot:DATA.projectRoot,selectedPlan:plan.id,plannerSkill:"project-blueprint-planner",executionSkill:"plan-execution-orchestrator",workflow:["读取当前已完成的审查结果并生成计划","按依赖顺序逐项修复","按已有审查结论独立验收每项修复","未达标继续下一项；失败则回滚并重新规划"],scope:{moduleCount:plan.moduleCount,fileCount:plan.fileCount,codeLines:plan.codeLines,moduleIds:plan.moduleIds,files:plan.files},acceptance:{target:"达到所选方案门槛",stopOn:["真实阻塞","规划门禁失败","独立验收失败且无法安全回滚"]}};const showStatus=(message,ok)=>{selection.querySelector(".workflow")?.remove();selection.querySelector(".actions").insertAdjacentHTML("beforebegin","<p class='workflow "+(ok?"":"error")+"'>"+esc(message)+"</p>")};document.querySelector("#start").onclick=async()=>{const button=document.querySelector("#start");button.disabled=true;button.textContent="正在提交…";try{const response=await fetch(DATA.bridgeUrl,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(request)});const result=await response.json();if(!response.ok)throw new Error(result.error||"本机 AI 未接受请求");showStatus("请求已发送给本机 AI。它将读取已有审查结果，先规划，再逐项修复和验收。请求编号："+result.requestId,true);button.textContent="已发送"}catch(error){showStatus("未能连接本机 AI："+error.message+"。可以先导出请求文件。",false);button.disabled=false;button.textContent="重试提交"}};document.querySelector("#export").onclick=()=>downloadJson(request,plan.id+"-repair-request.json");document.querySelector("#clear").onclick=()=>{localStorage.removeItem("architecture-review-selected-plan");selection.hidden=true;document.querySelectorAll(".plan").forEach(c=>c.classList.remove("selected"))}}
const planRoot=document.querySelector("#plans");
DATA.plans.forEach(p=>{const done=!!p.satisfied;const status=done?"<span class='plan-status'>已满足</span>":"";const action=done?"<button type='button' disabled aria-disabled='true'>已满足</button>":"<button type='button' data-select='"+esc(p.id)+"'>选择方案</button>";planRoot.insertAdjacentHTML("beforeend","<article class='panel plan"+(done?" satisfied":"")+"' data-id='"+esc(p.id)+"'><h3>"+esc(p.name)+"</h3><div class='credits'>"+p.credits+" 倍</div>"+status+"<div class='actions'>"+action+"</div></article>")});
document.querySelectorAll("[data-select]").forEach(b=>b.onclick=()=>selectPlan(DATA.plans.find(p=>p.id===b.dataset.select)));
document.addEventListener("click", event=>{if(event.target?.id!=="start")return;window.setTimeout(async()=>{const text=document.querySelector("#selection")?.innerText||"";const match=text.match(/请求编号：([A-Za-z0-9-]+)/);if(!match)return;const id=match[1];try{const response=await fetch(DATA.bridgeUrl+"/"+encodeURIComponent(id));const status=await response.json();if(status.status==="running"){const note=document.querySelector("#selection .workflow");if(note)note.textContent="本机 AI 正在执行规划和修复。请求编号："+id}else if(status.status==="completed"){const note=document.querySelector("#selection .workflow");if(note)note.textContent="本机 AI 已完成规划、修复和验收。请求编号："+id}else if(status.status==="failed"){const note=document.querySelector("#selection .workflow");if(note){note.classList.add("error");note.textContent="本机 AI 执行失败，请查看日志。请求编号："+id}}}catch(error){/* status polling is best-effort */}},1800)},true);
 document.addEventListener("click", event=>{if(event.target?.id!=="start")return;window.setTimeout(()=>{const text=document.querySelector("#selection")?.innerText||"";const match=text.match(/请求编号：([A-Za-z0-9-]+)/);if(!match)return;const id=match[1];const poll=async()=>{try{const response=await fetch(DATA.bridgeUrl+"/"+encodeURIComponent(id));const status=await response.json();const note=document.querySelector("#selection .workflow");if(!note)return;if(status.status==="queued")note.textContent="请求已排队，等待本机 AI 启动。请求编号："+id;else if(status.status==="running")note.textContent="本机 AI 正在执行规划和修复。请求编号："+id;else if(status.status==="completed"){note.textContent="本机 AI 已完成规划、修复和验收。请求编号："+id;clearInterval(timer)}else if(status.status==="failed"){note.classList.add("error");note.textContent="本机 AI 执行失败，请查看桥接日志。请求编号："+id;clearInterval(timer)}}catch(error){}};poll();const timer=setInterval(poll,2000)},200)},true);
 document.addEventListener("click", event=>{if(event.target?.id!=="start")return;window.setTimeout(()=>{const root=document.querySelector("#selection");if(!root)return;if(!root.querySelector(".progress-box"))root.querySelector(".actions")?.insertAdjacentHTML("beforebegin","<div class='progress-box'><div class='progress-head'><strong class='progress-label'>正在读取状态</strong><span class='progress-percent'>0%%</span></div><progress class='progress-bar' max='100' value='0'></progress><p class='progress-message'>等待本机 AI 返回进度。</p><p class='progress-elapsed'>已运行 0 秒</p></div>");const match=(root.innerText||"").match(/请求编号：([A-Za-z0-9-]+)/);if(!match)return;const id=match[1];const timer=setInterval(async()=>{try{const response=await fetch(DATA.bridgeUrl+"/"+encodeURIComponent(id));const status=await response.json();const progress=status.progress||{};const box=root.querySelector(".progress-box");if(!box)return;box.querySelector(".progress-label").textContent=progress.label||"等待状态";box.querySelector(".progress-percent").textContent=progress.stageTotal?"阶段 "+(progress.stageNumber||0)+"/"+progress.stageTotal:"";box.querySelector(".progress-bar").value=Number(progress.percent)||0;box.querySelector(".progress-message").textContent=progress.message||"等待下一条日志。";box.querySelector(".progress-elapsed").textContent="已运行 "+(progress.elapsedSeconds||0)+" 秒";if(status.status==="completed"||status.status==="failed")clearInterval(timer)}catch(error){}} ,1000)},350)},true);
 document.addEventListener("click", event=>{if(event.target?.id!=="start")return;const popup=window.open("about:blank","architecture-repair-progress","width=760,height=680");let attempts=0;const timer=setInterval(()=>{const text=document.querySelector("#selection")?.innerText||"";const match=text.match(/请求编号：([A-Za-z0-9-]+)/);if(match){clearInterval(timer);if(popup&&!popup.closed)popup.location.href=new URL(DATA.progressUrl,location.href).href+"?requestId="+encodeURIComponent(match[1])}else if(++attempts>30){clearInterval(timer)}},250)},true);
 </script></body></html>""" % (title, title, payload["moduleMapUrl"], data)


def enhance_dashboard_page(page):
    """Bind the dashboard cancel action to the localhost bridge job."""
    page = page.replace(
        "</style></head>",
        "<style>#architectureProgressBubble{position:fixed;right:18px;bottom:18px;width:56px;height:56px;padding:0;border:2px solid #1c6b52;border-radius:50%;background:#fff;box-shadow:0 6px 20px rgba(23,32,42,.26);cursor:grab;touch-action:none;user-select:none;z-index:1000}#architectureProgressBubble::after{content:\"\";display:block;width:13px;height:13px;margin:auto;border-radius:50%;background:#1c6b52}</style></head>",
        1,
    )
    behavior = """<script>(function(){
const activeKey="architecture-review-active-request";
function findRequestId(){const text=document.querySelector("#selection")?.innerText||"";const match=text.match(/请求编号：([A-Za-z0-9-]+)/);return match&&match[1]}
function rememberRequest(attempt){const id=findRequestId();if(id){localStorage.setItem(activeKey,id);return}if(attempt<40)window.setTimeout(()=>rememberRequest(attempt+1),250)}
function showProgressBubble(href){let bubble=document.querySelector("#architectureProgressBubble");if(!bubble){bubble=document.createElement("button");bubble.id="architectureProgressBubble";bubble.type="button";bubble.title="打开修复进度";bubble.setAttribute("aria-label","打开修复进度");document.body.appendChild(bubble);let drag=null;bubble.addEventListener("pointerdown",event=>{drag={x:event.clientX,y:event.clientY,left:bubble.offsetLeft,top:bubble.offsetTop,moved:false};bubble.dataset.dragged="";bubble.setPointerCapture?.(event.pointerId);bubble.style.cursor="grabbing"});bubble.addEventListener("pointermove",event=>{if(!drag)return;const dx=event.clientX-drag.x,dy=event.clientY-drag.y;if(Math.abs(dx)>4||Math.abs(dy)>4)drag.moved=true;bubble.style.left=Math.max(0,Math.min(window.innerWidth-bubble.offsetWidth,drag.left+dx))+"px";bubble.style.top=Math.max(0,Math.min(window.innerHeight-bubble.offsetHeight,drag.top+dy))+"px";bubble.style.right="auto";bubble.style.bottom="auto"});const endDrag=event=>{if(!drag)return;bubble.dataset.dragged=drag.moved?"true":"";drag=null;bubble.style.cursor="grab";if(event.pointerId!==undefined)bubble.releasePointerCapture?.(event.pointerId)};bubble.addEventListener("pointerup",endDrag);bubble.addEventListener("pointercancel",endDrag);bubble.addEventListener("click",event=>{if(bubble.dataset.dragged==="true"){event.preventDefault();bubble.dataset.dragged="";return}const popup=window.open(bubble.dataset.href,"architecture-repair-progress","width=760,height=680");if(popup){bubble.remove();popup.focus?.()}})}bubble.dataset.href=href||""}
document.addEventListener("click",event=>{const target=event.target;if(target?.id==="start"){window.setTimeout(()=>rememberRequest(0),250);return}if(target?.id!=="clear")return;event.preventDefault();event.stopPropagation();const id=localStorage.getItem(activeKey);const finish=()=>{localStorage.removeItem(activeKey);localStorage.removeItem("architecture-review-selected-plan");document.querySelector("#selection").hidden=true;document.querySelectorAll(".plan").forEach(card=>card.classList.remove("selected"))};if(!id){finish();return}target.disabled=true;target.textContent="正在停止…";fetch(DATA.bridgeUrl+"/"+encodeURIComponent(id),{method:"DELETE"}).then(response=>response.json().then(value=>{if(!response.ok)throw new Error(value.error||"本机 AI 未停止");finish()})).catch(error=>{target.disabled=false;target.textContent="取消选择";const selection=document.querySelector("#selection");const note=selection.querySelector(".workflow");if(note){note.classList.add("error");note.textContent="未能停止本机 AI："+error.message}})},true);
window.addEventListener("message",event=>{if(event.data?.type!=="architecture-progress-window"||!event.source)return;if(event.data.minimized)showProgressBubble(event.data.href);else document.querySelector("#architectureProgressBubble")?.remove()});
})();</script>"""
    return page.replace("</script></body></html>", "</script>" + behavior + "</body></html>", 1)


def main():
    parser = argparse.ArgumentParser(description="build/open the report-only audit dashboard")
    parser.add_argument("--state", required=True)
    parser.add_argument("--root", help="project root for resolving module files")
    parser.add_argument("--out-html", required=True)
    parser.add_argument("--bridge-url", help="本机修复桥接服务 URL")
    parser.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
    args = parser.parse_args()
    root = os.path.abspath(args.root or os.path.dirname(os.path.dirname(args.state)))
    output = os.path.abspath(args.out_html)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    bridge_origin = ensure_bridge(
        root,
        requested_url=(args.bridge_url or os.environ.get("ARCHITECTURE_REPAIR_BRIDGE_URL") or DEFAULT_BRIDGE_ORIGIN),
        log_path=os.path.join(root, ".codemap", "repair-bridge.log"),
    )
    os.environ["ARCHITECTURE_REPAIR_BRIDGE_URL"] = bridge_origin + "/repair-requests"
    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(enhance_dashboard_page(build_dashboard(read_json(args.state), root)))
    # Keep the live map beside modules.json so the dashboard link always points
    # at the current state, while retained audit versions remain report-only.
    map_output = os.path.join(os.path.dirname(os.path.abspath(args.state)), "codemap.html")
    with open(map_output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(build_free_module_map(read_json(args.state), args.state))
    progress_output = os.path.join(os.path.dirname(output), "repair-progress.html")
    progress_page = enhance_progress_dashboard(
        build_progress_dashboard(os.environ["ARCHITECTURE_REPAIR_BRIDGE_URL"])
    )
    with open(progress_output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(progress_page)
    if args.open:
        webbrowser.open(Path(output).as_uri())
    print("dashboard written -> {}".format(output))


if __name__ == "__main__":
    main()
