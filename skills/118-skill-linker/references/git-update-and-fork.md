# Git 更新、克隆、checkout 与 fork

## 下载或克隆 skills 仓库

当用户要求下载、克隆或安装一个仓库时，先判断它是否可能是 skills 仓库。判断依据包括：

- 仓库名或路径包含 `skill` 或 `skills`
- 用户描述中提到 agent skills
- 克隆或下载后能发现 `SKILL.md`、`skills/*/SKILL.md`、`.agents/skills/*/SKILL.md`

如果判断为 skills 仓库，询问用户是否要克隆到中央 skills 仓库父目录，例如 `~/GitHub`。不要默认克隆到当前项目里。

克隆完成后，识别仓库内的 skill 位置：

- 仓库根目录存在 `SKILL.md`：整个仓库可能就是一个 skill。
- 仓库内存在 `skills/<name>/SKILL.md`：这些子目录是可链接 skills。
- 仓库内存在 `.agents/skills/<name>/SKILL.md`：这些子目录是可链接 skills。

## 更新检查

更新时，把 git 作为版本管理来源。先用 `git-status` 或 `updates` 报告仓库路径、当前分支、上游分支、本地改动、ahead/behind 状态。

默认不要联网检查；如果需要知道远端是否有新提交，先说明会运行 `git fetch --prune`，获得用户确认后再执行。

运行 `git pull` 前，报告仓库路径以及是否有本地改动；有本地改动时默认不要更新。

如果用户问“哪个下载的 skill 更新了”，先确认中央 skills 目录，然后运行 `updates --central <目录>`。如果结果可能过期，说明它只是本地远端跟踪信息；询问用户是否允许获取远端信息，确认后再运行 `updates --central <目录> --execute`。只在用户明确确认后，才对具体仓库运行 `update --repo <仓库> --execute`。

不要为定时任务添加自动化逻辑；如果用户要求定时更新，先解释该 skill 当前不内置定时任务，再建议手动运行更新检查命令。

## Checkout

如果用户需要固定某个版本，先运行 `git-status` 查看本地改动和当前分支，再说明将执行 `git checkout <ref>`。

有本地改动时默认不要切换；用户确认风险后才能使用 `--allow-dirty`。

## Fork 决策

fork 的意思是：把别人的 GitHub 仓库复制成你自己账号下的一份仓库。适用于你需要长期修改别人的 skill，同时还希望以后能从原作者那里同步更新。

触发 fork 建议的典型情况：

- 用户说“我经常要改这个别人的 skill”。
- git 状态显示中央仓库有本地改动，同时用户又想更新远端。
- 用户担心自己的修改被 `git pull` 覆盖、冲突或难以维护。
- 用户想把本地修复提交到自己的 GitHub。

处理流程：

1. 先确认当前仓库是不是用户自己的仓库；如果不确定，查看 `git remote -v` 并向用户说明。
2. 如果这是别人的仓库且用户要长期改，建议用户 fork 一份到自己的 GitHub。
3. fork 后，把本地仓库的 `origin` 指向用户自己的 fork，把原作者仓库作为 `upstream`。
4. 后续本地修改提交到 `origin`；需要同步原作者更新时，从 `upstream` 拉取。
5. 不要自动执行 fork、改 remote 或推送，除非用户明确确认。
