# CLI 命令参考

以下命令从 skill 目录执行；其他目录须使用 skill_manager.py 的真实绝对路径。当前项目取运行环境的实际 cwd，使用 --project .；项目根必须已存在，不重打路径中的引号、不忽略 cd 失败。

写入命令不带 --execute 只预览。预览成功不是批准：在最终回复展示完整计划，结束本轮，收到确认后对同一计划加 --execute。检查命令只读；updates --execute 会 fetch，仍须确认。--home 用于明确的用户目录，测试必须使用隔离目录。

## 盘点和健康检查

```bash
python scripts/skill_manager.py onboard --project .
python scripts/skill_manager.py inspect --project .
python scripts/skill_manager.py config --project .
python scripts/skill_manager.py library-list --project .
python scripts/skill_manager.py project-list --project .
python scripts/skill_manager.py check --project . --include-user --include-central
python scripts/skill_manager.py check --project . --all-libraries
```

config 不再写配置。project-list 不扫描未登记项目。

## 初始化、连接和项目选择

```bash
# 首次：明确选择管理根，固定生成 libraries/central
python scripts/skill_manager.py root-init --project . --root /absolute/SkillsHub

# 已有合法 v3 根但无用户指针：先预览，再确认后携带输出的 root_id
python scripts/skill_manager.py root-connect --project . --root /absolute/SkillsHub
python scripts/skill_manager.py root-connect --project . --root /absolute/SkillsHub --expected-root-id <root_id> --execute

# 根存在后，给当前项目绑定默认主库
python scripts/skill_manager.py project-bind --project . --library central

# 仅确有隔离需求时，用户自定名称（project-alpha 只是示例）
python scripts/skill_manager.py library-add --name project-alpha
python scripts/skill_manager.py library-use --project . --name project-alpha

# 项目搬家或复制之后，明确选择一种重绑定方式
python scripts/skill_manager.py project-rebind --project . --mode move
python scripts/skill_manager.py project-rebind --project . --mode copy
```

除显式演示确认后执行的 root-connect 外，上例均预览；其他写入同样确认后加 --execute。项目默认库变更不改已有链接。没有 --scope、--central-base、--activate 或 allow-global 绕过参数。

## v2 到 v3

```bash
python scripts/skill_manager.py migrate-config --root /absolute/NewSkillsHub --main-library <旧主库名>
# 确认后：
python scripts/skill_manager.py migrate-config --root /absolute/NewSkillsHub --main-library <旧主库名> --expected-digest <摘要> --execute

# 已迁移根后，处理旧 v2 项目配置，旧入口仍保留
python scripts/skill_manager.py project-bind --project . --library central --replace-v2
```

这是复制迁移，不删除旧库、不自动重连项目。v1、有本地接管记录、嵌套链接或超限库不能直接迁移，详见[根与绑定](bootstrap-and-central-library.md)。

## 仓库安装

```bash
python scripts/skill_manager.py install-repo --project . --library central \
  --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer,reviewer=.agents/skills/reviewer --enable-project
```

项目启用前必须 project-bind。只收藏到库时省略 --enable-project。仓库根 skill 使用 name=.；目录与名称不同可用 codex-with-chatgpt=skill。名称必须等于 SKILL.md frontmatter，来源路径不得越界。计划列出完整 .repos 路径、中央入口、项目入口、Git 清单和项目 enabled 变化。

确认后克隆、校验、建入口并登记；普通失败回滚本次新增内容。已登记仓库复用本地版本，追加 skill 不自动 fetch。clone 是低层命令，不自动登记中央库。

## 项目入口

```bash
python scripts/skill_manager.py init --project . --agents claude,codex
python scripts/skill_manager.py link --project . --library central --source /absolute/SkillsHub/libraries/central/writer
python scripts/skill_manager.py link-many --project . --sources /absolute/SkillsHub/libraries/central/a,/absolute/SkillsHub/libraries/central/b
python scripts/skill_manager.py unlink --project . --target .agents/skills/writer
```

项目入口指向库根层 skill，不直接指向 .repos。link/link-many 与 unlink 同步绑定中的 enabled；冲突停止，不覆盖真实目录。init 只统一 Agent 入口，不自动启用库内全部 skills。

## 旧普通目录接管与恢复

```bash
python scripts/skill_manager.py migrate --project . --library central --central /absolute/SkillsHub/libraries/central --source ~/.claude/skills/write-blog
python scripts/skill_manager.py restore-adoption --project . --receipt /absolute/receipt.json
```

migrate 执行还须 --expected-digest <摘要> --dependencies-reviewed --execute；先人工审查外部依赖，摘要不代替用户确认。恢复确认后加 --execute；中央副本保留。普通独立目录接管不伪造 Git 来源；原可见范围不变。只有标准项目 hub 同名入口纳入 enabled；用户级、别名和直接 Agent 入口不冒充项目 hub 管理项。

## Git 检查与更新

```bash
python scripts/skill_manager.py git-status --repo /absolute/SkillsHub/libraries/central/.repos/github.com/example/skills
python scripts/skill_manager.py updates --project .
python scripts/skill_manager.py updates --project . --all-libraries
python scripts/skill_manager.py update --project . --library central --repo /absolute/SkillsHub/libraries/central/.repos/github.com/example/skills
python scripts/skill_manager.py checkout --project . --repo /absolute/SkillsHub/libraries/central/.repos/github.com/example/skills --ref v1.2.0
```

updates 不带 --execute 只读缓存；确认后加 --execute 才 fetch，区分 local-cache/fetched/fetch-failed。update 验证候选 skill 后按固定 SHA 快进；dirty、无 upstream、detached、分叉或身份变化停止。checkout 和 update 报告已登记项目影响，不声称覆盖全机。项目不可访问时影响列表不完整，必须披露。

## Windows

支持目录 junction；明确加 --link-type junction，不静默提权。symlink 权限失败需解释，不能绕过 UAC。命令输出的 verified_project_entries 是实际项目入口证据，不能用中央库成功代替项目成功。
