# E8 Skill Linker

[English](README.md) | 简体中文

安全管理已有 skills、Git 来源和项目入口：**一个管理根，固定 central 主库，其他库由用户自命名；先盘点、先计划、确认后执行。**

## 为什么使用

- 已安装许多 skills：先列清单、解释用途和来源证据，不强制迁移。
- 多个项目：共享已有中央 skill，只为需要的项目建立入口，不为每个项目复制一个库。
- 需要独立版本：在同一个管理根下创建用户命名的库，独立保存仓库和版本。
- GitHub skill pack：保留完整仓库、资源和 Git 历史，通过清单检查和更新来源。
- 不确定旧目录来自哪里：明确区分可靠证据、候选 URL 和来源未知，不猜 GitHub 地址。

## 安装管理器

需要 Python 3.10+；Git 操作需要 Git，无第三方 Python 运行依赖。推荐把管理型 skill-linker 安装到用户级，便于其他项目使用；业务 skills 默认仅按项目启用。

```bash
npx skills add xhanzo-coder/e8-skill-linker --list
npx skills add xhanzo-coder/e8-skill-linker --skill e8-skill-linker --global --agent codex
```

也可指定 --agent codex claude-code。此步骤只安装管理器，不创建库、不接管旧 skills。CLI 的更多选项见 [Skills CLI 文档](https://www.skills.sh/docs/cli)。

## 固定结构，不再到处分散建库

用户只需选一次管理根，例如 E:/SkillsHub；无偏好时建议 ~/.e8-skill-linker/SkillsHub。自选路径就是根本身，不追加隐藏目录。

```text
SkillsHub/
├── .skill-linker-registry.json       # 根身份、唯一库清单、已登记项目
└── libraries/
    ├── central/                     # 固定主库，展示名“中央主库”
    │   ├── .skill-linker-library.json
    │   ├── .skill-linker-lock.json   # Git 来源清单
    │   ├── .repos/github.com/owner/repo/
    │   └── writer -> .repos/.../skills/writer
    └── <用户自定库名>/                # 可选，不随每个项目自动创建
```

project/.agents/skills/writer → SkillsHub/libraries/central/writer → 仓库内 skill。Windows junction 也保留中央入口层；项目不直接链接到 .repos、github.com 或整个仓库。

central 是固定保留名，其他名称由用户决定。不同库可保存同名 skill 的独立版本；同一项目的同名入口只引用其中一个。共享库更新影响所有引用它的项目，切换默认库不会改变已经建立的链接。

## 第一次使用的交互

你可以直接说：“用 skill-linker 盘点我的用户级和当前项目 skills，先给我清单和建议，不迁移。”

1. 只读扫描用户级、当前项目及已配置的库，展示名称、用途、位置、真实原件、可见范围、来源证据和问题；不扫描所有磁盘或执行第三方脚本。
2. 推荐用户级安装管理器；已有副本复用，缺失不阻塞盘点。
3. 有合法 v3 根则复用；发现旧库则审查迁移；没有根则引导选一个根并初始化 central。非空未知目录不能当空库接管。
4. 新项目建议绑定 central；已有 skills 默认保持原样，让用户选择是否接管哪些项。
5. 展示一份含真实绝对路径、库来源、项目入口、配置变化、备份和跳过项的计划，结束本轮等待确认。
6. 收到确认后执行同一计划，核验真实链接和 SKILL.md；分别报告新增、复用和未执行项。

“帮我安装”不是对未展示计划的批准。确认前不 clone（包括临时克隆）、fetch、写配置或建链接。若已完整安装，只给零变更核对单，明确“本次仅检查，未修改文件”，不重复安装。第三方依赖、账号和初始化需另行授权。

## 配置与检测

| 文件 | 唯一职责 |
| --- | --- |
| 用户 ~/.skill-linker.json | schema v3、管理根绝对路径、root_id |
| 根 .skill-linker-registry.json | root_id、库相对路径与 library_id、项目 ID 与绝对路径 |
| 库 .skill-linker-library.json | 核对根身份、库身份与名称 |
| 项目 .skill-linker.json | root_id、project_id、default_library、enabled 的 skill→库映射 |

项目配置不会覆盖或隐藏库清单。机器本地绑定不是可直接共享给团队的依赖清单。检测同时核对 schema、身份、路径边界、实际入口和 skill 身份，不按目录名认定。

根离线、标记缺失、默认库不存在或项目身份冲突会报错，不自动重建、不回退 central。项目移动或复制后显式 project-rebind；只检查登记过的项目，不全盘搜索。整个管理根搬迁/现有用户指针替换仍需单独审查，不自动修复。

## 常用命令

以下从仓库根执行；其他项目请使用脚本绝对路径，并传实际项目 --project .。写入命令默认预览，用户确认后才加 --execute。--home 可指明隔离测试用户，不能用测试改真实用户配置。

```bash
# 只读
python skills/e8-skill-linker/scripts/skill_manager.py onboard --project .
python skills/e8-skill-linker/scripts/skill_manager.py library-list --project .
python skills/e8-skill-linker/scripts/skill_manager.py project-list --project .

# 创建根；根已存在且合法则用 root-connect，不重复创建
python skills/e8-skill-linker/scripts/skill_manager.py root-init --project . --root /absolute/SkillsHub
python skills/e8-skill-linker/scripts/skill_manager.py root-connect --project . --root /absolute/SkillsHub

# 已建立根后绑定项目；不会启用全部 skills
python skills/e8-skill-linker/scripts/skill_manager.py project-bind --project . --library central

# 可选独立库，名称仅为示例
python skills/e8-skill-linker/scripts/skill_manager.py library-add --name project-alpha
python skills/e8-skill-linker/scripts/skill_manager.py library-use --project . --name project-alpha

# 单次选库安装并启用，项目必须已绑定
python skills/e8-skill-linker/scripts/skill_manager.py install-repo --project . --library central --repo-url https://github.com/example/skills.git --skills writer=skills/writer --enable-project

# 从已有中央入口启用、在当前项目停用
python skills/e8-skill-linker/scripts/skill_manager.py link --project . --library central --source /absolute/SkillsHub/libraries/central/writer
python skills/e8-skill-linker/scripts/skill_manager.py unlink --project . --target .agents/skills/writer

# 检查全部库；updates 默认只检查缓存，确认后 --execute 才 fetch
python skills/e8-skill-linker/scripts/skill_manager.py check --project . --all-libraries
python skills/e8-skill-linker/scripts/skill_manager.py updates --project . --all-libraries
```

root-connect 执行还须计划中的 --expected-root-id。config 现在只读；旧 --scope、--central-base、--activate、全局中央库绕过参数已移除。管理根不能与 Agent 发现目录重叠。

根目录 skill 用 name=.，来源目录与名称不同用 codex-with-chatgpt=skill；frontmatter 名称必须一致。来源清单登记的仓库复用本地版本，追加 skill 不自动 fetch。详细参数、项目移动/复制、多 Agent hub、接管恢复和 Git 操作见 [CLI 参考](skills/e8-skill-linker/references/script-commands.md)。

## 检查和更新如何可靠

每库 .skill-linker-lock.json 记录 URL、仓库相对路径、安装 revision、skill 子路径及中央入口。.repos 非空而无合法清单时报错，不猜测来源。revision 只说明本地安装版本；updates 输出区分 local-cache、fetched、fetch-failed，未 fetch 或获取失败不能称为最新。

update 先验证清单和工作区，fetch 后验证候选提交里的已登记 skills，再用 git merge --ff-only <已验证SHA> 更新并记 revision。dirty、无 upstream、detached、分叉、skill 被删除或名称变化均停止。新增 skill 不自动启用；应用后的校验失败不自动 reset 用户工作区。

更新/checkout 会报告已登记项目的声明与实际 hub 引用；失联项目单列错误。未登记项目和用户级外部旧链接不在完整影响图内，不能保证没有其他引用。编辑共享 skill 同样影响全部引用者。

## 已安装的 skills 与旧版迁移

普通独立 skill 文件夹可通过 migrate 选择性接管为本地快照：核对完整内容摘要、审查外部依赖、复制验证、保留原件备份和 receipt，再把原位置改成链接。保持原用户级/项目级范围，不伪造 Git 来源。restore-adoption 可恢复原真实目录并保留中央副本；内容变化则停止。仅标准项目 hub 同名入口登记 enabled，其他入口继续在盘点中展示。

没有 Git 元数据的旧目录不一定能找回准确仓库或版本。README 的 GitHub URL 只是候选；外层业务项目 remote 不是 skill 来源；其他安装器锁文件目前只列出供审查。任意旧 Git 安装转托管来源不是一键功能。

schema v2 配置不能继续直接运行。显式预览：

```bash
python skills/e8-skill-linker/scripts/skill_manager.py migrate-config --root /absolute/NewSkillsHub --main-library <旧主库名>
```

确认后携带 --expected-digest <摘要> --execute。新根必须不存在；复制旧库到新布局，把指定主库映射为 central，保留旧库和旧链接，备份用户配置。旧项目另行 project-bind --replace-v2，之后按计划重连旧入口，不能声称已经全部迁移。

自动迁移仅支持 v2 用户配置；带 .skill-linker-local 接管凭据、未登记嵌套链接、Git worktree/submodule、特殊文件、重叠库或超过每库 10,000 项/256 MiB/32 层时停止。v1 需单独审查。复制失败保留新根部分副本供诊断，原库/用户指针不动；不自动清理或接着重试。详见 [布局与迁移边界](skills/e8-skill-linker/references/bootstrap-and-central-library.md)。

## 安全与平台

- macOS/Linux 支持目录 symlink；Windows 可显式 --link-type junction，不静默提权。
- 不覆盖真实目录、不覆盖指向其他目标的链接；“删除 skill”默认只停用当前项目入口。
- 根登记表/项目绑定使用写锁与执行前状态核对，避免协作写入覆盖；普通失败尝试回滚，不保证跨命令、强杀或断电原子性。
- 项目备份不要提交到 Git；用户级管理器备份位于 Agent 发现目录之外。
- 跨机器项目链接和本机绑定需重新核验；不把脚本测试通过说成所有模型都会遵守确认规则。

## 开发与验证

```bash
python scripts/validate_skill.py skills/e8-skill-linker
python -m unittest discover -s tests -v
python -m py_compile skills/e8-skill-linker/scripts/skill_manager.py skills/e8-skill-linker/scripts/root_state.py
```

核心规则在 SKILL.md，详细流程在 references/，命令与根状态逻辑在 scripts/skill_manager.py 和 scripts/root_state.py。测试包含 Git 流程、盘点/接管与 test_root_state.py；对话规则证据独立记录在 [interaction-cases.md](tests/interaction-cases.md)，不将历史回放当作新版已通过。

[贡献指南](CONTRIBUTING.md) · [安全政策](SECURITY.md) · [更新日志](CHANGELOG.md) · [MIT License](LICENSE)
