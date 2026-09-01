---
name: architecture-review-plus
description: >-
  默认 Plus 架构审计与本机修复：在中文仪表盘和模块图基础上提供方案选择、
  localhost 修复桥接、实时进度窗口与可拖动悬浮球。用于用户明确选择修复方案
  并要求本机 AI 按既有审计结果规划和逐模块修复时；不用于单模块直接修复。
---

# 架构审查 Skill（Plus 版）

Plus 版是默认架构审计入口，在 `architecture-review-report-only` 免费开源版的审计输出之上，提供本机
修复流程。免费版只负责中文仪表盘和模块图；本 Skill 才提供方案选择、桥接和进度反馈。

## 输出与边界

- 保留 `<project>/.codemap/modules.json`、中文审计报告、仪表盘、模块图和不可变审计历史。
- 方案卡只在用户选定方案后展示修复范围：模块数量、文件数量和预计修改代码行数。
- 只有用户选择方案后点击“开始规划并修复”才允许提交修复请求。单模块修复不触发本 Skill。
- 本机桥接仅绑定 `127.0.0.1`，请求仅可作用于其启动时指定的项目根目录。
- 面向用户的页面不显示内部 Skill 名称、提示词、角色或规划细节；只显示普通状态与进度。

## 修复流程

1. 基于已有审计结果确定尚未满足的方案，不重新发起审计。
2. 桥接将请求交给本机可用 Agent（Codex、Claude Code、WorkBuddy、ZCode、豆包或用户配置的命令）。
3. 先由 `project-blueprint-planner` 规划，再由 `plan-execution-orchestrator` 按依赖顺序逐模块执行。
4. 每个任务完成后依据已捕获的审计证据独立验收；达到方案门槛或发生范围变化、失败、回归时停止并返回状态。
5. 进度页可最小化为可拖动悬浮球，单击悬浮球恢复同一个进度窗口。

短期方案要求主要模块达到 75 分且没有 HIGH；长期维护方案要求所有模块达到 80 分且没有 HIGH；
完美方案要求所有模块达到 90 分且没有 HIGH 或 MED。已满足的方案必须显示为不可选。

## 命令

```text
python SKILL_DIR/scripts/version.py publish --root <project> --open-dashboard
python SKILL_DIR/scripts/dashboard.py --root <project> --state <project>/.codemap/modules.json --open
python SKILL_DIR/scripts/repair_bridge.py --root <project> --port 8767
```

`dashboard.py` 与 `version.py --open-dashboard` 会自动检查并配置同项目的 localhost 桥接。
若端口已服务另一个项目，会选择可用本机端口。桥接需要已安装并完成认证的本地 Agent CLI；
静态页面本身不直接编辑源码。

## 审计规则

沿用免费版的固定审计合同：先读 `reference/STANDARDS.md` 与 `reference/DATA_MODEL.md`；
模块分数来自独立审计；`.codemap/` 不纳入被审计源码，且不得删除或覆盖历史版本。
