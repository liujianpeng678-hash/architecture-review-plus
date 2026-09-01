# Architecture Review Plus

这是架构审查的 Plus 版。它在中文审计仪表盘和模块图基础上，提供修复方案选择、本机 AI 修复桥接、规划执行和实时进度悬浮球。

## 使用边界

- 只有用户明确选择方案并点击“开始规划并修复”后，才会提交修复请求。
- 桥接只绑定 `127.0.0.1`，不会暴露到公网。
- 单模块修复不会触发本 Skill 的规划链。
- 审计项目的 `.codemap/`、本机凭据和生成报告不应提交到此仓库。

## 快速开始

```text
python scripts/dashboard.py --root <project> --state <project>/.codemap/modules.json \
  --out-html <project>/.codemap/audit-dashboard.html --open
python scripts/repair_bridge.py --root <project> --port 8767
```

本机 Agent 需要已经安装并完成认证。支持 Codex、Claude Code、WorkBuddy、ZCode、豆包及配置的本地 Agent 命令。
