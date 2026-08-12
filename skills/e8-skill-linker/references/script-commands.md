# 脚本命令

使用 `scripts/skill_manager.py` 进行确定性的检查和安全的软链接操作。除非传入 `--execute`，默认命令都是只读或 dry-run。

## 检查与配置

检查当前状态：

```bash
python3 scripts/skill_manager.py inspect --project .
```

查看当前生效配置：

```bash
python3 scripts/skill_manager.py config --project .
```

只检查链接：

```bash
python3 scripts/skill_manager.py check --project .
```

同时检查用户级 Agent 目录和已配置的中央库：

```bash
python3 scripts/skill_manager.py check --project . --include-user --include-central
```

以 dry-run 方式写入用户级中央目录配置。默认推荐使用 `e8-skill-linker` 专属的非全局目录，不要默认写成 `~/.agents/skills`：

```bash
python3 scripts/skill_manager.py config --scope user --central ~/.e8-skill-linker/AgentSkills --mode centralize
```

如果用户提供的是自定义父目录，使用 `--central-base`，脚本会自动派生 `<父目录>/.e8-skill-linker/AgentSkills`：

```bash
python3 scripts/skill_manager.py config --scope user --central-base "/Users/name/Desktop/WorkSpace" --mode centralize
```

用户确认后写入：

```bash
python3 scripts/skill_manager.py config --scope user --central ~/.e8-skill-linker/AgentSkills --mode centralize --execute
```

如果用户明确选择 Agent 全局 skills 目录作为中央库，执行时必须增加 `--allow-global-central`。如果用户明确把一个不含 `.e8-skill-linker/AgentSkills` 命名空间的路径作为最终中央目录，执行时必须增加 `--allow-non-namespaced-central`。这两个参数只表示用户已经理解并确认风险，不能由 Agent 擅自添加。

## 自举安装

以 dry-run 方式把 `e8-skill-linker` 自身安装到用户级全局目录，便于新项目自动召回：

```bash
python3 scripts/skill_manager.py install-self --source /path/to/e8-skill-linker --agents agents,codex,claude
```

用户确认后执行：

```bash
python3 scripts/skill_manager.py install-self --source /path/to/e8-skill-linker --agents agents,codex,claude --execute
```

如果全局副本已经存在，脚本默认停止。用户明确确认替换后增加 `--replace --execute`；旧副本会移动到同级的 `e8-skill-linker.backup-<UTC 时间>`，不会直接删除。

## 初始化与链接

以 dry-run 方式初始化项目入口目录：

```bash
python3 scripts/skill_manager.py init --project . --agents claude,codex
```

用户确认后执行：

```bash
python3 scripts/skill_manager.py init --project . --agents claude,codex --execute
```

以 dry-run 方式链接单个 skill：

```bash
python3 scripts/skill_manager.py link --project . --source ~/.e8-skill-linker/AgentSkills/write-blog
```

用户确认后执行：

```bash
python3 scripts/skill_manager.py link --project . --source ~/.e8-skill-linker/AgentSkills/write-blog --execute
```

以 dry-run 方式把多个 skills 链接到当前项目：

```bash
python3 scripts/skill_manager.py link-many --project . --sources ~/.e8-skill-linker/AgentSkills/a,~/.e8-skill-linker/AgentSkills/b
```

`link` 和 `link-many` 会拒绝不在当前生效中央库或当前项目 `.agents/skills` 内的源路径。

`link-many` 会先验证所有源、目标名称和目标冲突；任何一项失败时，不创建任何链接。

以 dry-run 方式从当前项目停用某个 skill。此命令只删除软链接或 junction，不删除中央原件：

```bash
python3 scripts/skill_manager.py unlink --target .agents/skills/write-blog
```

用户确认后执行停用：

```bash
python3 scripts/skill_manager.py unlink --target .agents/skills/write-blog --execute
```

## 迁移

以 dry-run 方式把已有真实 skill 目录迁移到中央目录，并在原位置创建软链接：

```bash
python3 scripts/skill_manager.py migrate --source ~/.claude/skills/write-blog --central ~/GitHub/my-skills/skills
```

`migrate --central` 必须等于当前生效配置中的中央 skills 库；不要临时指定未配置目录。

## Git 与仓库

检查单个下载仓库的 git 状态：

```bash
python3 scripts/skill_manager.py git-status --repo ~/GitHub/my-skills
```

检查中央目录下哪些下载的 skill 仓库可能落后远端。默认只使用本地已有的远端跟踪信息，不联网：

```bash
python3 scripts/skill_manager.py updates --central ~/GitHub/my-skills/skills
```

用户确认后，获取最新远端信息再判断哪些仓库有更新：

```bash
python3 scripts/skill_manager.py updates --central ~/GitHub/my-skills/skills --execute
```

用户确认后，更新某个下载仓库：

```bash
python3 scripts/skill_manager.py update --repo ~/GitHub/my-skills --execute
```

`update` 要求当前分支有 upstream，并使用 `git pull --ff-only`。仓库有本地改动、处于 detached HEAD、没有 upstream 或无法 fast-forward 时停止，不自动覆盖或合并。

以 dry-run 方式克隆 skill 仓库到中央仓库父目录：

```bash
python3 scripts/skill_manager.py clone --repo-url https://github.com/user/some-skills.git --dest-parent ~/GitHub
```

用户确认后执行克隆，并在克隆后识别仓库中包含哪些 skills：

```bash
python3 scripts/skill_manager.py clone --repo-url https://github.com/user/some-skills.git --dest-parent ~/GitHub --execute
```

以 dry-run 方式切换某个下载仓库到指定版本：

```bash
python3 scripts/skill_manager.py checkout --repo ~/GitHub/my-skills --ref v1.2.0
```

确认后增加 `--execute`。仓库有本地改动时默认停止；只有用户理解风险并明确确认后才可增加 `--allow-dirty`。

## Windows

Windows 上如果 symlink 权限不足，可以显式使用 junction：

```powershell
python scripts/skill_manager.py link --project . --source C:\Users\you\GitHub\my-skills\skills\write-blog --link-type junction
python scripts/skill_manager.py init --project . --agents claude,codex --link-type junction
python scripts/skill_manager.py migrate --source C:\Users\you\.claude\skills\write-blog --central C:\Users\you\GitHub\my-skills\skills --link-type junction
```
