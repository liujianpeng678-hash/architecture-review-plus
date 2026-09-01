"""Agent launch adapters for the local architecture-repair bridge.

The repair protocol stays agent-neutral. Built-in profiles only advertise a
local executable when it is discoverable; profiles that need a desktop/API
integration can be enabled through ``.codemap/agent-adapters.json`` without
changing the dashboard protocol.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
import shutil


@dataclass(frozen=True)
class AgentAdapter:
    id: str
    label: str
    candidates: tuple[str, ...]
    mode: str = "configured"
    executable_override: str | None = None
    args: tuple[str, ...] = ()
    prompt_flag: str | None = None

    def executable(self) -> str | None:
        if self.executable_override:
            return self.executable_override
        for candidate in self.candidates:
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return None

    def available(self) -> bool:
        return self.executable() is not None and self.mode != "configured"


BUILT_INS = (
    AgentAdapter("codex", "Codex", ("codex.exe", "codex.cmd", "codex"), mode="codex"),
    AgentAdapter("claude-code", "Claude Code", ("claude.exe", "claude"), mode="claude"),
    AgentAdapter("workbuddy", "WorkBuddy", ("workbuddy.exe", "workbuddy")),
    AgentAdapter("zcode", "ZCode", ("zcode.exe", "zcode")),
    AgentAdapter("doubao", "豆包", ("doubao.exe", "doubao")),
)


def _configured_profiles(root: str | os.PathLike[str]) -> dict[str, AgentAdapter]:
    path = Path(root).resolve() / ".codemap" / "agent-adapters.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    result: dict[str, AgentAdapter] = {}
    for item in payload.get("agents", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("id", "")).strip().lower()
        label = str(item.get("label", agent_id)).strip()
        command = item.get("command")
        if not agent_id or not label or not command:
            continue
        if isinstance(command, list):
            parts = [str(value) for value in command if str(value).strip()]
        else:
            parts = shlex.split(str(command), posix=os.name != "nt")
        if not parts:
            continue
        args = item.get("args", [])
        if not isinstance(args, list):
            args = []
        result[agent_id] = AgentAdapter(
            agent_id, label, (parts[0],), mode=str(item.get("mode", "generic")),
            executable_override=parts[0], args=tuple(parts[1:] + [str(value) for value in args]),
            prompt_flag=str(item.get("promptFlag")) if item.get("promptFlag") else None,
        )
    return result


def available_adapters(root: str | os.PathLike[str]) -> list[dict[str, object]]:
    profiles = {adapter.id: adapter for adapter in BUILT_INS}
    profiles.update(_configured_profiles(root))
    result = []
    for adapter in profiles.values():
        executable = adapter.executable()
        configured = adapter.id in _configured_profiles(root)
        result.append({
            "id": adapter.id,
            "label": adapter.label,
            "available": bool(executable and (adapter.mode != "configured" or configured)),
            "configured": configured,
            "executable": bool(executable),
        })
    return result


def resolve_adapter(root: str | os.PathLike[str], requested: str | None = None) -> AgentAdapter:
    profiles = {adapter.id: adapter for adapter in BUILT_INS}
    profiles.update(_configured_profiles(root))
    requested_id = (requested or os.environ.get("ARCHITECTURE_REVIEW_AGENT") or "codex").strip().lower()
    adapter = profiles.get(requested_id)
    if adapter is None:
        raise ValueError("未注册的执行助手：" + requested_id)
    if not adapter.executable():
        raise FileNotFoundError("找不到执行助手：" + adapter.label)
    if adapter.mode == "configured" and adapter.id not in _configured_profiles(root):
        raise ValueError("执行助手尚未配置本地启动方式：" + adapter.label)
    return adapter


def build_command(adapter: AgentAdapter, root: str | os.PathLike[str], request_path: Path, result_path: Path) -> list[str]:
    executable = adapter.executable()
    if not executable:
        raise FileNotFoundError("找不到执行助手：" + adapter.label)
    prompt = (
        "你收到一个来自架构审计仪表盘的自动修复请求。先读取执行任务文件：{request}。"
        "必须先读取请求中已有审查结果，再按规划要求生成计划和架构门禁，并按依赖顺序逐项修复；"
        "每项都要依据已有审查结论独立验收，不要重新审查或重新评分；开始处理每个模块时单独输出一行 [MODULE_START] moduleId=<模块ID>，"
        "完成该模块时输出一行 [MODULE_DONE] moduleId=<模块ID>；全部完成后只将简短结果写入：{result}。"
        "不要修改原始 architecture-review 库，不要等待用户输入，不要终止自己的进程。"
    ).format(request=str(request_path), result=str(result_path))
    if adapter.mode == "codex":
        return [executable, "exec", "-C", str(root), "--dangerously-bypass-approvals-and-sandbox", "-o", str(result_path), prompt]
    if adapter.mode == "claude":
        return [executable, "-p", prompt]
    command = [executable, *adapter.args]
    if adapter.prompt_flag:
        command.append(adapter.prompt_flag)
    command.append(prompt)
    return command
