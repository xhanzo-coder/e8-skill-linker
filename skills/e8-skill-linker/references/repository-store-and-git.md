# 仓库存储、安装与 Git 生命周期

## 两层中央库模型

第三方 Git 来源必须保留完整仓库，不默认抽取或复制单个 skill 子目录。中央库使用两层布局：

```text
AgentSkills/
├── .repos/
│   └── github.com/owner/repository/   # 完整 Git 仓库
├── skill-a -> .repos/.../skills/skill-a
└── skill-b -> .repos/.../skills/skill-b
```

- `.repos` 是仓库存储层，保留 `.git`、remote、分支、LICENSE、测试和共享资源。
- 中央库根层是 skill 发现层，只包含真实 skill 目录或指向仓库内 skill 目录的链接。
- `.skill-linker-lock.json` 记录仓库 URL、当前安装 commit、内部路径和已暴露的 skills，是受管理仓库的权威清单。
- 本地创建、不属于 Git 仓库的 skill 可作为真实目录直接位于中央库根层。

项目入口统一为 `项目/.agents/skills/writer → 中央库/writer → 仓库内 skill`，Windows junction 也保留中央入口这一层。不要将 `.repos`、host 或整个 skill pack 作为项目 skill。

仓库存储路径保留完整 namespace，GitHub 通常是一层 owner。读取清单时验证 schema、路径边界和重复入口；仓库操作前验证 Git 根目录、origin、HEAD、skill 名称及中央链接。`.repos` 非空却没有清单，或记录与实际状态不一致时，报告错误并审查修复，不猜测来源。

## 仓库安装

用户给出仓库时，先按[安装交互规则](output-and-confirmation.md)进入“检查与计划 → 等待确认 → 执行验证”。只读查看仓库结构，确定要安装的 skill 名称与仓库内相对路径；确认前不通过临时 clone 或第三方安装脚本探查。脚本使用显式 `name=relative/path` 规格：

```text
writer=skills/writer,reviewer=.agents/skills/reviewer
```

仓库根目录本身就是 skill 时使用 `skill-name=.`。相对路径不能越出仓库；仓库内部目录名不要求与 skill 名称一致。例如 `codex-with-chatgpt=skill` 表示读取 `skill/SKILL.md`，验证 frontmatter `name` 为 `codex-with-chatgpt`，再创建同名中央入口。保留仓库原始布局，不重命名来源目录。

根目录 skill 的 frontmatter 名称可以不同于仓库名，中央入口名仍必须等于 frontmatter 名称。

安装计划必须同时列出：

- 当前活动中央库；
- 完整仓库的 `.repos/<host>/<owner>/<repo>` 目标；
- 每个中央 skill 入口及目标；
- 如果用户要立即使用，列出当前项目入口；
- 将写入的来源清单；
- 任何名称或路径冲突。

用户确认完整计划后才运行 `install-repo --execute`。执行时克隆完整仓库，验证每个 `SKILL.md` 的 frontmatter `name` 与计划一致，再创建中央和项目入口。任一步失败都回滚本次新建的入口与仓库。

已登记仓库复用当前本地版本，不再次 clone 或自动 fetch。再次运行 `install-repo` 可追加其他 skill、为另一个项目启用已有 skill，或重复执行相同计划。URL、子路径或入口冲突时停止。追加失败只回滚本次新增入口，保留原仓库、已有入口与原清单。上游刚新增的 skill 需要先更新仓库，再追加安装。

上述重复执行能力不是自动写入许可。若只差项目入口，先列启用计划等确认；若请求目标已全部满足，只交付零变更核对单，不重跑 `install-repo --execute`。skill 文件与入口安装不包含第三方依赖、构建、账号连接或初始化，这些需求单独报告和授权。

同一库内同名 skill 冲突，不同库可以独立保存同名 skill。用 `--library <name>` 单次选库，省略时使用活动库，不修改默认选择。

如果无法在写入前确定远程 skill 路径，停止并说明需要先预览或用户指定；不在安装时猜测路径。用户明确要不可更新的快照时，可单独讨论 vendor/copy 模式，但它不是默认安装策略。

## 更新检查

`updates --library work` 检查指定库；省略时检查活动库。`--all-libraries` 检查生效配置内全部库。只处理清单登记的仓库，不再扫描旧式根层 Git 仓库，也不自动登记未知目录。

默认只读取本地 remote-tracking 状态。如果需要最新远程信息，先说明将运行 `git fetch --prune`，获得用户确认后再传入 `--execute`。当前没有后台自动检查。

必须区分输出中的 freshness：

- `local-cache`：未 fetch，不能用于声称 GitHub 最新。
- `fetched`：本次 fetch 成功，状态对应获取时刻。
- `fetch-failed`：网络或鉴权失败，更新状态为 `unknown`，不把旧 ahead/behind 当作最新结果。

没有 upstream 时也报告 `unknown`。命令退出码非零时，不能汇报“全部已是最新”。`revision` 记录安装状态，不能替代 fetch。

报告包含全部变更文件、直接修改的已安装 skills、新增/删除的 `SKILL.md`、未暴露的可用 skill 路径和身份错误。共享资源变化也可能影响未直接修改的 skill；不要仅凭其子目录未变就断言不受影响。删除与新增可能代表移动或重命名，需要审查，不猜测新映射。

## 应用更新

`update --repo <完整仓库路径> --library work` 要求仓库登记在 work。更新前报告分支、upstream、本地改动及影响。仓库有本地改动、没有 upstream、detached HEAD 或不能快进时停止。

确认后依次执行：

1. 校验当前来源清单、仓库和中央入口。
2. fetch 并固定本次获取的候选提交 SHA。
3. 从 Git 对象检查候选 `SKILL.md` 是否存在、为普通文件、frontmatter 名称是否一致。失败时保留工作区和清单，先讨论入口迁移。
4. 用 `git merge --ff-only <候选SHA>` 应用已检查的提交，不进行第二次网络拉取。
5. 再次验证 skill 与中央入口，成功后记录新 revision。

已有项目链接会立即读取新版。上游新增 skill 不自动创建入口。fetch 会更新本地远端跟踪记录，即使后续验证拒绝更新也保留这些记录。应用后的验证或清单写入如失败，报告实际状态，不声称已回滚 Git 工作区，也不自动 reset 用户文件。

## Checkout 与 fork

checkout 前先检查当前 Git 状态并列出将切换的 ref。有本地改动时默认停止；拒绝以 `-` 开头的 ref。

来源清单管理的仓库成功 checkout 后同步 revision。长期修改第三方 skill 可以讨论 fork：`origin` 指向用户 fork，`upstream` 指向原作者。切换来源时必须同步审查清单中的 URL，不自动 fork、改 remote、改清单或 push，除非用户明确确认。
