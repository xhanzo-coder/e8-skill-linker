---
name: 118-skill-linker
description: 管理、安装、链接、迁移、同步和更新 Agent skills 的中央库与项目入口。用户说“安装一个 skill”“帮我整理 skills”“这个项目启用某个 skill”“同步 Codex/Claude/.agents skills”“把 skill 放到中央库”“检查 skill 更新”“删除/停用 skill”“为什么新项目读不到 skill”“把 118-skill-linker 装到全局”“初始化 .agents/.codex/.claude/skills”“修复失效软链接”“切换 skill 版本”“fork/更新别人写的 skill”时使用。用于检查和配置 .skill-linker.json、推荐非全局中央库 ~/.118-skill-linker/AgentSkills、区分 Agent 全局 skills 目录与项目级 skills 入口、把业务 skills 按项目软链接启用、以及在确认后将 118-skill-linker 作为管理型 skill 安装到用户级全局目录以便新项目自动召回。
---

# 118 Skill Linker

## 核心职责

使用这个 skill，把中央来源中的 Agent skills 安全链接到项目级 skills 目录中。默认只做只读检查；在任何写入、同步、替换、删除、克隆或 git 更新前，先解释计划并获得用户确认。

如果已经存在 `.skill-linker.json` 配置，优先使用配置中的中央 skills 目录，不要在新对话里重新把当前项目目录猜成中央目录。

## 不可违反的规则

- 除非用户明确要求某个安全的写入操作，否则先从只读检查开始。
- 在把某个目录视为中央 skills 目录前，必须先让用户确认。
- 不要默认把 `~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills` 当作中央库；这些是 Agent 全局发现目录。
- 首次没有配置时，默认推荐非全局中央目录：macOS/Linux 使用 `~/.118-skill-linker/AgentSkills`，Windows 使用 `%USERPROFILE%\.118-skill-linker\AgentSkills`。
- 用户提供自定义父目录时，实际中央库必须派生为 `<父目录>/.118-skill-linker/AgentSkills`，不要把 skill 原件直接散放在父目录下。
- 创建软链接时，链接目标只能指向已配置的中央 skills 库，或当前项目的项目级 skills 入口目录。不要把任意下载目录、临时目录、桌面目录、仓库根目录或其他未授权路径直接作为软链接目标。
- 在同步或迁移前，列出所有计划创建、替换、跳过、备份、删除或 git 操作，并等待用户确认。
- 不要用软链接覆盖已有的真实目录。
- 用户说“删除 skill”时，默认理解为“从当前项目停用”，只删除入口链接；不要删除真实 skill 目录，除非用户明确要求删除那个具体目录。
- 通过软链接编辑文件前要提醒用户：这会修改中央原件，并影响所有指向它的项目。
- 在 Windows 上创建 symlink 可能需要 Developer Mode 或管理员终端；不要让 Agent 静默提权、绕过 UAC 或输入管理员密码。

## 任务路由

根据用户请求读取对应 reference。只加载当前任务需要的文件。

- 自举安装、首次配置、中央库选择、`.skill-linker.json`、全局目录风险：读取 [references/bootstrap-and-central-library.md](references/bootstrap-and-central-library.md)。
- 初始化项目入口、链接、批量链接、迁移、同步、删除或停用 skill：读取 [references/link-sync-and-removal.md](references/link-sync-and-removal.md)。
- 检查结果、整理方案、确认口令、用户级/项目级路径表达：读取 [references/output-and-confirmation.md](references/output-and-confirmation.md)。
- 下载/克隆 skills 仓库、检查更新、更新仓库、checkout、fork 建议：读取 [references/git-update-and-fork.md](references/git-update-and-fork.md)。
- Windows symlink、junction、权限和跨盘注意事项：读取 [references/windows-links.md](references/windows-links.md)。
- 需要确定命令参数或 dry-run/execute 示例时：读取 [references/script-commands.md](references/script-commands.md)。

## 基本流程

1. 判断用户请求属于检查、初始化、下载/克隆、链接、批量链接、取消链接/停用、同步、迁移、更新、切换版本、fork 建议或解释。
2. 状态未知时先执行只读检查，并读取当前项目 `.skill-linker.json` 与用户级 `~/.skill-linker.json`。
3. 同时区分项目级目录和用户级目录：
   - 项目级：`.agents/skills`、`.codex/skills`、`.claude/skills`
   - 用户级：`~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills`
4. 如果配置中已有中央目录，围绕该中央目录给出建议方案；如果没有配置，按首次配置流程推荐非全局中央目录。
5. 写入、迁移、同步、删除、克隆、fetch、pull、checkout 前，先给用户可审查的计划和明确确认口令。
6. 用户确认后才执行；执行完成后再运行检查命令验证结果。

## 自举提醒

每次触发后，先判断 `118-skill-linker` 自己是否已经安装在用户级全局 Agent skills 目录中，例如 `~/.agents/skills/118-skill-linker`。如果当前加载的是项目级副本或非全局中央库副本，先说明它是管理型 skill，建议作为例外安装到用户级全局目录，以便新项目和新对话能自动召回它。业务型 skills 仍然不默认全局安装。

不要自动迁移或安装。给出计划并等待用户确认。推荐确认口令：

```text
确认全局安装 118-skill-linker
```

详细流程见 [references/bootstrap-and-central-library.md](references/bootstrap-and-central-library.md)。

## 脚本入口

使用 `scripts/skill_manager.py` 进行确定性的检查和安全的软链接操作。除非传入 `--execute`，默认命令都是只读或 dry-run。

常用入口：

```bash
python3 scripts/skill_manager.py inspect --project .
python3 scripts/skill_manager.py config --project .
python3 scripts/skill_manager.py check --project .
```

更多命令示例见 [references/script-commands.md](references/script-commands.md)。
