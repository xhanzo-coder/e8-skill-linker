# 自举安装与命名中央库

## 管理器自举

每次触发时先判断 `e8-skill-linker` 是否已安装在用户级 Agent skills 目录，例如 `~/.agents/skills/e8-skill-linker`。已安装时继续用户的当前任务，不重复提醒。

未安装时，说明它是管理型 skill，可作为全局例外安装，便于新项目和新对话自动召回。业务 skills 仍默认保存在非全局中央库并按项目启用。展示计划并等待：

```text
确认全局安装 e8-skill-linker
```

全局目标已存在时默认停止。用户明确确认替换后，先将旧副本移到 `~/.e8-skill-linker/backups/e8-skill-linker/<UTC时间戳>`，再安装新副本。备份必须在 Agent 全局发现目录之外，避免旧副本被重复加载。

## schema v2

用户级配置默认位于 `~/.skill-linker.json`。项目级 `<project>/.skill-linker.json` 用于完整覆盖用户默认，适合团队共享、客户隔离或测试项目。两个配置不合并。

```json
{
  "schema_version": 2,
  "libraries": {
    "personal": {
      "path": "/Users/name/.e8-skill-linker/AgentSkills"
    },
    "work": {
      "path": "/Volumes/Work/.e8-skill-linker/AgentSkills"
    }
  },
  "active_library": "personal",
  "default_mode": "centralize"
}
```

规则：

- `libraries` 可登记多个命名中央库；名称只能使用小写字母、数字和连字符。
- `active_library` 必须精确指向 `libraries` 中的一项。一个生效配置同时只有一个活动中央库。
- 项目级配置整体优先于用户级配置；不根据名称或路径暗中合并。
- `default_mode` 只能是 `centralize`、`project-local` 或 `ask`。
- 必需字段缺失、未知字段、重复路径或无效活动库都直接报错。

## v1 迁移

如果发现仅包含 `central_skills_dir` 和 `default_mode` 的 v1 配置，不继续执行写入操作，也不静默兼容。先运行 `migrate-config` dry-run，展示将使用的库名称、原路径、配置作用域和风险提醒。用户确认后才增加 `--execute`。

迁移只重写配置 schema，不移动中央库内容，也不把现有根层 Git 仓库自动移入 `.repos`。仓库布局整理应作为另一份可审查计划。

## 首次配置

1. 只读检查项目级与用户级配置。
2. 没有配置时，推荐库名 `personal` 和非全局路径：
   - macOS/Linux：`~/.e8-skill-linker/AgentSkills`
   - Windows：`%USERPROFILE%\.e8-skill-linker\AgentSkills`
3. 用户提供自定义父目录时，派生为 `<parent>/.e8-skill-linker/AgentSkills`；不把原件散放在父目录。
4. 列出配置路径、库名、中央库路径、将创建的目录及影响范围。
5. 获得用户确认后写入配置，再运行只读检查验证。

## 命名库操作

- `library-list` 只读显示用户级、项目级和当前生效配置。
- `library-add` 在指定作用域增加一个新库；同名或同路径时停止。
- `library-use` 切换指定配置的活动库，输出当前项目已有链接的直接目标和库归属，不重写这些链接。如果需要迁移项目，另列链接差异与冲突。
- `install-repo`、`link`、`link-many`、`check`、`updates`、`update` 接受 `--library <name>`。该选择仅用于本次操作，不修改 `active_library`。`update` 的 `--repo` 必须属于指定库的来源清单。
- `check --all-libraries` 和 `updates --all-libraries` 处理当前生效配置中全部库。存在项目级配置时不会额外合并用户级库。
- 每个库独立保存仓库和来源清单；同名 skill 可存在于不同库，项目 hub 中的同名入口仍只能指向一个库。

## 高风险中央路径

`~/.agents/skills`、`~/.codex/skills` 或 `~/.claude/skills` 会让内容对大量项目全局可见。用户主动选择时，先说明风险并等待明确确认；执行层使用 `--allow-global-central`。

最终中央路径故意不包含 `.e8-skill-linker/AgentSkills` 时，说明它不符合默认命名空间并等待确认；执行层使用 `--allow-non-namespaced-central`。两类风险同时存在时必须同时满足两个确认条件。
