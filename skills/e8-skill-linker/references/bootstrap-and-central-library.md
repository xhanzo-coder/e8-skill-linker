# 管理根、中央主库与项目绑定

## 管理器自举

先按[首次使用与接管](first-use-and-adoption.md)只读盘点。推荐将管理型 e8-skill-linker 安装到用户级 Agent skills 目录；缺失不阻塞盘点，已有副本复用。替换须单独列入确认计划，先备份到 ~/.e8-skill-linker/backups/e8-skill-linker/<UTC时间戳>，不得把备份留在 Agent 发现目录。业务 skills 默认按项目启用。

## 固定布局：一个根，多库，多项目引用

用户选择的是**管理根目录本身**，例如 E:/SkillsHub，不再追加隐藏命名空间。无偏好时建议 ~/.e8-skill-linker/SkillsHub（Windows 为 %USERPROFILE%/.e8-skill-linker/SkillsHub），该建议不是静默创建或回退路径。

```text
<root>/
├── .skill-linker-registry.json
└── libraries/
    ├── central/                     # 固定中央主库，保留名称
    │   ├── .skill-linker-library.json
    │   ├── .skill-linker-lock.json   # 安装 Git 来源后生成
    │   ├── .repos/github.com/owner/repo/
    │   └── writer -> .repos/.../skills/writer
    └── <用户自定库名>/                # 可选，同样结构
```

central 是固定主库标识，展示为“中央主库”；不是 personal 或 work。其他库名由用户决定，使用 1–64 位小写字母、数字、连字符分隔片段，排除 Windows 设备名。示例名称不是预创建的默认库。

新项目通常复用 central，不为每个项目新建物理库。确实需要版本或内容隔离时才创建独立库，同一仓库在不同库内是独立 checkout。项目可从多个库启用不同名称的 skills；同名入口只能引用其中一个。多个项目可共享同一库。

## schema v3：三份配置各司其职

用户 ~/.skill-linker.json 仅保存根指针：

```json
{"schema_version":3,"root":"/absolute/SkillsHub","root_id":"<UUID>"}
```

管理根 .skill-linker-registry.json 是唯一库目录与已登记项目索引：

```json
{
  "schema_version":3,
  "root_id":"<UUID>",
  "libraries":{"central":{"path":"libraries/central","library_id":"<UUID>"}},
  "projects":{"<项目UUID>":{"path":"/absolute/project"}}
}
```

每个库的 .skill-linker-library.json 保存 schema_version、root_id、name、library_id，必须与登记表完全一致。UUID 由命令生成，示例占位符不可直接写入配置。

项目 <project>/.skill-linker.json 只保存绑定和启用来源，不另造或覆盖库清单：

```json
{
  "schema_version":3,
  "root_id":"<UUID>",
  "project_id":"<项目UUID>",
  "default_library":"central",
  "enabled":{"writer":"central"}
}
```

enabled 跟踪经管理器登记的项目 .agents/skills/<name>。原有真实目录、旧链接、直接安装在 .codex/.claude 的独立入口不因绑定项目而自动接管；检查时如实标记未登记。该文件含机器本地身份，不是可直接跨机器复用的团队依赖清单。

## 如何检测：验证身份，不猜目录名

1. 读取用户指针，验证 schema、绝对路径、root_id。
2. 读取根登记表，验证 root_id 一致、固定 central 存在、库名与 libraries/<name> 路径一致。
3. 验证每个库目录和身份标记；拒绝链接父路径、越界、重复身份或未知字段。
4. 读取实际 cwd 的项目绑定，核对 root_id、project_id、登记绝对路径、默认库和 enabled 来源。
5. 检查真实项目链接的直接目标、中央入口及 SKILL.md 身份；配置声明不等于安装成功。

没有用户指针：只读盘点，询问创建新根或连接已存在的 v3 根；不凭 SkillsHub/central 文件夹名自动接管。root-connect 先显示根身份，确认后携带 --expected-root-id 执行。

没有项目绑定：推荐绑定 central，列入计划确认后执行 project-bind；不会自动创建独立库，也不自动启用全部 skills。中央收藏操作不强制绑定项目，项目启用必须先绑定。

已配置但根离线、库缺失、身份不符、默认库不存在、项目路径变化：明确报错；不自动新建空库、不回退到 central、不搜另一个同名目录。整个根目录迁移/切换现有用户指针不在自动修复范围，需要单独审查。

## 命令语义

- root-init --root <目录>：仅接受不存在或空目录；创建 central、身份标记、根登记表和用户指针，不搬旧 skills，不绑定项目。已有用户配置不覆盖。
- root-connect --root <目录>：连接合法 v3 根；不能覆盖指向其他状态的用户指针。
- config / library-list：只读，显示同一根下的完整库清单、项目绑定和默认库。
- library-add --name <名称>：固定创建 <root>/libraries/<名称>，不接受外部路径，不改项目默认库。
- project-bind --project . --library central：登记已有项目，enabled 初始为空，旧入口不动。
- library-use --project . --name <名称>：只改当前项目默认库，已有 enabled 和链接不动。
- --library <名称>：单次选库，不改变项目默认；check/updates --all-libraries 范围是当前根登记的全部库。
- project-list：仅核验已登记项目及实际 hub 入口，不全盘找项目，不自动清理失联记录。
- project-rebind --mode move|copy：路径变化需明确计划；move 要求原路径不存在并保留 ID，copy 分配新 ID。两者保留入口，不保证复制来的链接有效，执行后检查。

所有写入默认 dry-run，最终展示计划并结束本轮等用户确认。同一已确认计划无需逐条再问。元数据写入采用锁和执行前状态核对，普通写入失败尝试回滚；不承诺多命令、整批操作或断电时全局原子性。残留写锁需先审查，不自动删除。

## v2 显式迁移，拒绝静默兼容

运行 migrate-config --root <不存在的新根> --main-library <旧主库名> 预览。用户必须明确旧库中哪个成为 central，其他库保留名称并集中到 libraries/ 下。它复制原库、重建新库内部的中央链接、核对内容和 Git 清单，再备份旧用户配置并写入 v3 指针。执行必须携带计划摘要 --expected-digest，摘要不是批准令牌。

原库和旧项目链接保留不动；旧项目 v2 配置需要 project-bind --replace-v2 单独备份并改为绑定。旧链接仍指向旧库时要另列 unlink/link 计划，不能报告所有项目迁移完成。无需迁移的用户可新建空根，但不能直接覆盖已有配置。

当前自动迁移边界：仅 v2 用户配置；拒绝含本地接管记录 .skill-linker-local 的库、未登记嵌套链接、worktree/submodule Git 文件、特殊文件、重叠来源路径；每库最多 10,000 项、256 MiB、32 层。v1、超限或有接管凭据的库先单独审查，不提供兼容分支。复制失败保留新根的部分副本供诊断，旧原件/用户指针不变；不能直接重跑或删除而不审查。

管理根不得与用户级/当前项目级 Agent 发现目录重叠，不能是盘符根、用户目录或项目根本身；不提供 allow-global 等绕过开关。
