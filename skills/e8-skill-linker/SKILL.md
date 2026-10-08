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

首次初始化、盘点或接管已有 skills 时，先读[首次使用与接管](references/first-use-and-adoption.md)，运行 `onboard --project .`，展示用途、范围、来源证据和问题列表。先扫描再推荐用户级安装管理器；中央库初始化与旧 skill 接管分开选择，不能默认全选迁移。旧 skill 接管保留原用户级/项目级入口；“新装业务 skill 默认项目级”不用于缩小旧 skill 的可见范围。

1. 按用户意图分流：“检查是否安装”只读检查；“帮我安装”进入安装计划流程，即使发现已安装，也不能改成含糊的“安装完成”。安装请求先读[安装交互规则](references/output-and-confirmation.md)和[仓库安装](references/repository-store-and-git.md)。
2. 从运行环境取得实际项目工作目录，核实目录存在，再读取项目级与用户级配置。对“当前项目”使用该工作目录下的 `--project .`，不要手抄或替换路径字符；`cd` 失败就停止，不模糊匹配另一个目录。
3. 确认前只读查看来源、配置与入口，必要时 dry-run；不 clone（包括临时克隆）、fetch、写配置、建链接或运行第三方脚本。无法确定 skill、中央库或项目时先询问，不猜测。
4. 在最终回复展示具体计划：来源与 skill 映射、项目和中央库绝对路径、已有状态、新增/复用/跳过动作、清单与备份/删除影响。然后结束本轮，等待用户下一条确认消息；参数完整、dry-run 成功或过程消息展示计划都不算确认。其他写入操作也遵守同一确认边界。
5. 三层已完整安装时展示核对单，写明“本次仅检查，未执行安装、未修改文件”，建议保留现状并询问是否需要其他处理，然后停止；不自动重装、更新或重写清单。中央库已有但项目缺入口时，仍须先给项目启用计划。
6. 同一计划已获确认，不重复询问；只有用户主动、明确要求跳过确认并在明确范围内全自动执行，才可省略等待。确认后只执行该计划，范围变化或计划外冲突就停止。校验项目入口、直接目标与可读 `SKILL.md`，区分本次新增与已有复用；第三方依赖安装、账号连接和初始化另行授权。

## 中央库配置

schema v2 允许在一份配置中登记多个命名中央库，但每个项目只有一个 `active_library`。项目级配置整体优先于用户级配置，不合并两者。v1 配置必须经过 `migrate-config` 显式升级；不做静默兼容。

安装、链接、检查和更新可用 `--library <name>` 单次选库，不改变默认库。`updates` 和 `check` 支持 `--all-libraries`，范围为当前生效配置。切换默认库不迁移项目链接，报告已有链接的实际库归属。

没有配置时，推荐非全局中央库：macOS/Linux 使用 `~/.e8-skill-linker/AgentSkills`，Windows 使用 `%USERPROFILE%\.e8-skill-linker\AgentSkills`。自定义父目录必须派生为 `<parent>/.e8-skill-linker/AgentSkills`。

## 不可违反的安全规则

- 不用链接覆盖真实目录或指向其他目标的链接。
- 项目根目录必须已经存在。只在该目录内创建项目入口，不自动新建、模糊匹配或纠正项目根路径。
- 仓库安装前验证用户指定的 `name=relative/path`、`SKILL.md` frontmatter 和名称冲突；入口名称必须等于 frontmatter `name`，仓库内部目录名可以不同。安装失败时回滚本次新建的仓库与入口。
- 用户说“删除 skill”时默认只从当前项目停用；除非明确要求，不删除中央原件或 Git 仓库。
- 更新检查以 `.skill-linker-lock.json` 为仓库清单；只有本次 fetch 成功才报告远端状态，缓存或失败不能称为“最新”。
- Git 更新先 fetch，验证候选提交中的已登记 skill，再用 `merge --ff-only <已验证提交>` 更新并校验入口、记录 revision。有本地改动、detached HEAD、没有 upstream、无法 fast-forward 或候选 skill 失效时停止。
- 通过链接编辑会修改中央原件并影响所有引用项目，操作前要提醒用户。
- Windows 上可用 junction；不静默提权、绕过 UAC 或输入管理员密码。

## 按需路由

- 自举、schema v2、命名库和首次配置：[references/bootstrap-and-central-library.md](references/bootstrap-and-central-library.md)
- 首次盘点、来源证据、选择性接管和恢复：[references/first-use-and-adoption.md](references/first-use-and-adoption.md)
- 第三方仓库安装、`.repos`、来源清单、更新、checkout 和 fork：[references/repository-store-and-git.md](references/repository-store-and-git.md)
- 项目入口、批量链接、迁移和停用：[references/link-sync-and-removal.md](references/link-sync-and-removal.md)
- 检查结果、计划表和确认口令：[references/output-and-confirmation.md](references/output-and-confirmation.md)
- Windows 链接权限与跨盘：[references/windows-links.md](references/windows-links.md)
- CLI 参数与 dry-run/execute 示例：[references/script-commands.md](references/script-commands.md)

## 管理器自身

首次盘点同时检查 `e8-skill-linker` 是否已安装在用户级 Agent skills 目录。未安装不阻塞只读盘点；展示结果后说明全局安装的好处，将它纳入用户选定的初始化计划并等待确认。已安装就复用，有多个副本先比较；不自动迁移或替换管理器。

确定性操作使用 `scripts/skill_manager.py`。除非传入 `--execute`，所有写入命令均为 dry-run。
