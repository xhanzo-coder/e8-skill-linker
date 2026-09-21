# CLI 命令参考

使用 `scripts/skill_manager.py` 执行确定性操作。不带 `--execute` 的写入命令只输出计划。

## 检查

```bash
python3 scripts/skill_manager.py inspect --project .
python3 scripts/skill_manager.py config --project .
python3 scripts/skill_manager.py library-list --project .
python3 scripts/skill_manager.py check --project . --include-user --include-central
python3 scripts/skill_manager.py check --project . --library work
python3 scripts/skill_manager.py check --project . --all-libraries
```

## 创建 schema v2 配置

首次配置一个名为 `personal` 的用户级中央库：

```bash
python3 scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize
```

用户确认后增加 `--execute`。用户提供自定义父目录时使用 `--central-base`，脚本会派生 `<parent>/.e8-skill-linker/AgentSkills`。

`config` 会创建一份新配置；目标配置已存在时，计划会明确显示 `will_replace_config`。增加中央库应使用 `library-add`，不用 `config` 覆盖整份配置。

## v1 配置迁移

```bash
python3 scripts/skill_manager.py migrate-config \
  --scope user \
  --library personal
```

确认输出中的原路径、schema 与风险后：

```bash
python3 scripts/skill_manager.py migrate-config \
  --scope user \
  --library personal \
  --execute
```

迁移只更改配置文件，不移动中央库内容。

## 命名中央库

```bash
# 增加 work，但不切换
python3 scripts/skill_manager.py library-add \
  --scope user \
  --name work \
  --central-base /Volumes/Work

# 增加后立即设为活动库
python3 scripts/skill_manager.py library-add \
  --scope user \
  --name work \
  --central-base /Volumes/Work \
  --activate

# 切换已登记的活动库
python3 scripts/skill_manager.py library-use --scope user --name work
```

确认后增加 `--execute`。`library-use` 只改变配置选择，不静默重写项目中的旧链接。

`install-repo`、`link`、`link-many`、`check`、`updates` 和 `update` 可用 `--library work` 单次选库。`updates`、`check` 的 `--all-libraries` 处理当前生效配置内所有库，与 `--library` 互斥；不会合并用户级与项目级配置。

选择 Agent 全局 skills 目录需要用户明确确认后增加 `--allow-global-central`。最终路径故意不包含 `.e8-skill-linker/AgentSkills` 时，需要确认后增加 `--allow-non-namespaced-central`。

## 仓库安装

先根据远程仓库结构确定 skill 规格，然后 dry-run：

```bash
python3 scripts/skill_manager.py install-repo \
  --project . \
  --library personal \
  --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer,reviewer=.agents/skills/reviewer \
  --enable-project
```

根目录就是 skill 时使用 `--skills skill-name=.`。计划会列出 `.repos/<host>/<owner>/<repo>`、中央 skill 入口、可选项目入口和 `.skill-linker-lock.json`。用户确认后增加 `--execute`。

`install-repo` 要求完整计划中的 skill 名称与路径都已知。它会原子化地克隆仓库、验证 `SKILL.md`、创建入口并写入来源清单；失败时回滚本次新建内容。

根目录 skill 的名称可以不同于仓库名。仓库已经登记时复用本地版本；再运行相同命令可追加 skill，或用 `--enable-project --project <另一个项目>` 启用已有 skill。新增失败保留已有仓库、入口与清单，不自动 fetch。

`clone` 保留为低层命令，只克隆并发现 skills，不登记到中央库。

## 项目入口

```bash
python3 scripts/skill_manager.py init --project . --agents claude,codex
python3 scripts/skill_manager.py link --project . --source ~/.e8-skill-linker/AgentSkills/write-blog
python3 scripts/skill_manager.py link-many --project . --sources /central/a,/central/b
python3 scripts/skill_manager.py unlink --target .agents/skills/write-blog
```

开始写入前先运行 dry-run，用户确认后增加 `--execute`。`unlink` 只删除链接或 junction，不删除中央原件。

## 迁移已有真实 skill

```bash
python3 scripts/skill_manager.py migrate \
  --project . \
  --source ~/.claude/skills/write-blog \
  --central ~/.e8-skill-linker/AgentSkills
```

`--central` 必须与当前活动中央库一致。确认后增加 `--execute`。

## Git 检查与更新

```bash
python3 scripts/skill_manager.py git-status --repo /central/.repos/github.com/example/skills

# 默认仅检查活动库的本地缓存
python3 scripts/skill_manager.py updates --project .

# 确认后获取指定库的最新远程状态
python3 scripts/skill_manager.py updates --project . --library work --execute

# 检查生效配置中的全部库
python3 scripts/skill_manager.py updates --project . --all-libraries --execute

# 确认后更新具体仓库
python3 scripts/skill_manager.py update --library work --repo /central/.repos/github.com/example/skills --execute

# 切换版本
python3 scripts/skill_manager.py checkout --repo /central/.repos/github.com/example/skills --ref v1.2.0
```

`updates` 不再接受任意 `--central` 路径，只处理选定库清单中的仓库。结果区分 `local-cache`、`fetched`、`fetch-failed`；失败或没有 upstream 时不能声称最新。

`update` 先 fetch，验证候选提交的已登记 skill，再用 `git merge --ff-only <候选SHA>` 更新。更新后校验入口并同步 revision。有本地改动、detached HEAD、没有 upstream、不能快进、skill 路径消失或名称变化时停止。该命令没有 `--allow-dirty` 绕过选项。

`--library` 与 `--repo` 同用时验证仓库归属。新增的上游 skills 只列出，不自动启用；追加入口需要再次运行 `install-repo`。

## Windows

目录 symlink 权限不足时可明确使用 `--link-type junction`：

```powershell
python scripts/skill_manager.py install-repo `
  --repo-url https://github.com/example/skills.git `
  --skills writer=skills/writer `
  --enable-project `
  --link-type junction
```

用户确认后增加 `--execute`。不让 Agent 静默提权或绕过 UAC。
