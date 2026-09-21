---
name: e8-skill-linker
description: 安全管理 Agent skills 的命名中央库、Git 仓库来源和项目级入口。当用户要安装 GitHub skill 或 skill pack、初始化或切换中央库、为项目启用/停用 skill、同步 Codex/Claude/.agents 入口、检查或更新仓库、迁移现有 skills、修复链接或管理 fork 时使用。区分中央原件库与 Agent 全局发现目录；业务 skills 默认只按项目启用。
---

# E8 Skill Linker

## 所有权边界

将三层路径始终分开：

- 中央库保存 skill 原件与可发现入口。第三方 Git 仓库完整保存在 `<central>/.repos/`，中央库根层只暴露包含 `SKILL.md` 的 skill 入口。
- 项目级 `.agents/skills/<name>` 指向中央库根层 `<name>`，再由中央入口指向仓库内 skill；Windows junction 同样保留这一层。`.codex/skills` 和 `.claude/skills` 可指向项目 hub。
- 用户级 `~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills` 是 Agent 全局发现目录，不是默认中央库。`e8-skill-linker` 作为管理型 skill 可例外安装到用户级。

## 默认交互

1. 识别请求是检查、配置、仓库安装、项目启用、停用、迁移、更新、checkout 还是 fork。
2. 状态未知时先只读检查：读取项目级与用户级 `.skill-linker.json`，确定当前生效的命名中央库。
3. 只读查询立即执行。一个写入目标形成一份完整计划，列出配置、仓库、中央入口、项目入口、更新、备份与删除影响。
4. 获得一次作用域明确的确认后，再使用 `--execute` 执行该计划。遇到计划外冲突就停止，不静默改用其他路径或策略。
5. 执行后自动检查配置、仓库清单、`SKILL.md` 和链接目标，然后汇报结果。

## 中央库配置

schema v2 允许在一份配置中登记多个命名中央库，但每个项目只有一个 `active_library`。项目级配置整体优先于用户级配置，不合并两者。v1 配置必须经过 `migrate-config` 显式升级；不做静默兼容。

安装、链接、检查和更新可用 `--library <name>` 单次选库，不改变默认库。`updates` 和 `check` 支持 `--all-libraries`，范围为当前生效配置。切换默认库不迁移项目链接，报告已有链接的实际库归属。

没有配置时，推荐非全局中央库：macOS/Linux 使用 `~/.e8-skill-linker/AgentSkills`，Windows 使用 `%USERPROFILE%\.e8-skill-linker\AgentSkills`。自定义父目录必须派生为 `<parent>/.e8-skill-linker/AgentSkills`。

## 不可违反的安全规则

- 不用链接覆盖真实目录或指向其他目标的链接。
- 仓库安装前验证用户指定的 `name=relative/path`、`SKILL.md` frontmatter 和名称冲突；安装失败时回滚本次新建的仓库与入口。
- 用户说“删除 skill”时默认只从当前项目停用；除非明确要求，不删除中央原件或 Git 仓库。
- 更新检查以 `.skill-linker-lock.json` 为仓库清单；只有本次 fetch 成功才报告远端状态，缓存或失败不能称为“最新”。
- Git 更新先 fetch，验证候选提交中的已登记 skill，再用 `merge --ff-only <已验证提交>` 更新并校验入口、记录 revision。有本地改动、detached HEAD、没有 upstream、无法 fast-forward 或候选 skill 失效时停止。
- 通过链接编辑会修改中央原件并影响所有引用项目，操作前要提醒用户。
- Windows 上可用 junction；不静默提权、绕过 UAC 或输入管理员密码。

## 按需路由

- 自举、schema v2、命名库和首次配置：[references/bootstrap-and-central-library.md](references/bootstrap-and-central-library.md)
- 第三方仓库安装、`.repos`、来源清单、更新、checkout 和 fork：[references/repository-store-and-git.md](references/repository-store-and-git.md)
- 项目入口、批量链接、迁移和停用：[references/link-sync-and-removal.md](references/link-sync-and-removal.md)
- 检查结果、计划表和确认口令：[references/output-and-confirmation.md](references/output-and-confirmation.md)
- Windows 链接权限与跨盘：[references/windows-links.md](references/windows-links.md)
- CLI 参数与 dry-run/execute 示例：[references/script-commands.md](references/script-commands.md)

## 管理器自身

每次触发后检查 `e8-skill-linker` 是否已安装在用户级 Agent skills 目录。未安装时，说明它是管理型 skill 的全局例外，给出计划并等待 `确认全局安装 e8-skill-linker`；不自动迁移。

确定性操作使用 `scripts/skill_manager.py`。除非传入 `--execute`，所有写入命令均为 dry-run。
