# Agent 适配

副本桥接服务使用统一的 `architecture-review-repair/v1` 请求，不把执行器绑定到单一 Agent。

内置探测器支持 Codex、Claude Code、WorkBuddy、ZCode 和豆包的本地命令；实际存在且可调用的命令才会被标记为可用。默认使用 Codex，也可以通过 `ARCHITECTURE_REVIEW_AGENT` 指定适配器。

没有稳定本地命令的 Agent 可在项目 `.codemap/agent-adapters.json` 注册：

```json
{
  "agents": [
    {
      "id": "workbuddy",
      "label": "WorkBuddy",
      "command": "C:/path/to/workbuddy.exe",
      "mode": "generic",
      "args": [],
      "promptFlag": "--prompt"
    }
  ]
}
```

`mode` 为 `generic` 时，桥接器只负责传递统一任务提示和结果路径；Agent 自己负责读取规划要求并执行。页面只显示普通进度，适配器名称、提示词和内部 Skill 不写入用户界面。
