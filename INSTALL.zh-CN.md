# 架构审查 Skill：安装与使用

本项目按 [MIT 许可证](LICENSE) 开源，任何人都可以下载、使用、修改和分发，无需邀请或激活码。AI 编程工具及模型服务由使用者自行准备。

## 准备

- 支持读取项目文件、执行 Python 脚本的 AI 编程工具。
- Python 3.9 或更高版本；脚本只使用标准库，无需 pip 安装依赖。
- Git（可选，不安装 Git 时使用 ZIP）。

## 在 Codex 中安装

直接把这句话发给 Codex：

```text
使用 $skill-installer 安装 https://github.com/liujianpeng678-hash/architecture-review-plus 。SKILL.md 位于仓库根目录，请安装完整目录。
```

也可以在 Windows PowerShell、macOS 或 Linux 终端执行：

```sh
git clone https://github.com/liujianpeng678-hash/architecture-review-plus.git "$HOME/.agents/skills/architecture-review-plus"
```

此路径依据 [Codex 官方技能文档](https://learn.chatgpt.com/docs/build-skills)。如果你已经通过安装器或旧版本安装在其他位置，请保留一份有效安装，避免同名 Skill 重复注册。发现不了新技能时重启 Codex。

没有 Git：点击 [下载 ZIP](https://github.com/liujianpeng678-hash/architecture-review-plus/archive/refs/heads/main.zip)，解压完整目录，将目录名改为 `architecture-review-plus`，放入用户目录的 `.agents/skills/`。最终结构应为 `.agents/skills/architecture-review-plus/SKILL.md`，不要多套一层目录。

## 开始使用

在 Codex 中打开要审查的项目，然后发送：

```text
用 $architecture-review 审查当前项目的模块职责、依赖关系和代码质量，基于代码证据生成交互式架构图和中文报告。
```

后续修改项目后，可以发送：

```text
用 $architecture-review 增量更新上次审查，说明哪些模块变了、哪些结论需要重新验证。
```

审查数据保存在被审查项目中，保留版本位于其 `.codemap/` 目录。请按代理给出的实际路径打开 HTML 报告。审查本身不代表授权修改项目代码。

其他 AI 编程工具可以使用它们支持的 Skill 目录；也可以让代理读取本项目的 `SKILL.md` 并按其执行。必须保留 `scripts/`、`reference/` 和 `assets/` 等完整资源。

## 更新与反馈

Git 安装用户执行（安装在其他位置时替换路径）：

```sh
git -C "$HOME/.agents/skills/architecture-review-plus" pull --ff-only
```

如果修改过安装目录里的文件，先保存你的改动。ZIP 用户重新下载，并保留旧目录备份后替换。

问题反馈请到 [GitHub Issues](https://github.com/liujianpeng678-hash/architecture-review-plus/issues)，附上操作系统、Python 版本、复现步骤和脱敏后的报错。
