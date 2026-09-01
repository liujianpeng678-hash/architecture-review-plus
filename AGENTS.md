# Architecture Review Plus

- 本目录是 Plus 版，负责方案选择、本机修复桥接、规划执行和进度展示。
- `modules.json` 由被审计项目持有；本 Skill 不把项目的 `.codemap/` 数据提交到仓库。
- 桥接只允许 `127.0.0.1`，必须校验请求对应的项目根目录。
- `assets/template.html` 是随 Plus 版发布的模块图模板，不能依赖安装目录之外的免费版。
