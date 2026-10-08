# E8 Skill Linker

[English](README.md) | [简体中文](README.zh-CN.md)

[![CI](https://github.com/xhanzo-coder/e8-skill-linker/actions/workflows/ci.yml/badge.svg)](https://github.com/xhanzo-coder/e8-skill-linker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-compatible-111827.svg)](https://agentskills.io/)

`e8-skill-linker` 是一个用于管理 Agent skills 的管理型 skill。它帮助你把 skill 原件集中放在一个明确的中央目录中，再按项目创建入口链接，从而同时管理 Codex、Claude Code 和其他支持 Agent Skills 的工具。

它适合这些场景：

- 在多个项目之间复用同一批 skills。
- 安装、克隆、迁移、链接、更新或停用 skills。
- 区分用户级 Agent 目录、项目级入口和中央 skills 原件目录。
- 长期维护自己修改过的第三方 skill，并检查 Git 更新或 fork 状态。
- 在 macOS、Linux 和 Windows 上使用 symlink 或 junction 管理项目入口。

## 重要概念

这个仓库包含一个 skill，位于 `skills/e8-skill-linker/`。其中：

- `SKILL.md`：Agent 触发后读取的核心规则。
- `references/`：按任务加载的详细流程。
- `scripts/`：执行检查、配置、链接和迁移的确定性脚本。

中央 skills 库和 Agent 全局目录不是同一个概念：

- 中央库根层保存可发现的 skill 原件或入口，默认推荐 `~/.e8-skill-linker/AgentSkills`。
- 第三方 Git 仓库完整保存在 `<central>/.repos/<host>/<owner>/<repo>`，根层 skill 通过 symlink 或 junction 指向仓库内目录。
- `<central>/.skill-linker-lock.json` 记录仓库来源、当前 commit、子路径与中央 skill 入口。
- macOS/Linux 的 Agent 全局目录通常是 `~/.agents/skills`、`~/.codex/skills` 或 `~/.claude/skills`。
- Windows 使用 `%USERPROFILE%\.e8-skill-linker\AgentSkills` 作为默认中央库。
- 项目级 `.agents/skills`、`.codex/skills` 和 `.claude/skills` 是当前项目的入口。

业务 skills 默认不直接安装到 Agent 全局目录。`e8-skill-linker` 自己是管理型 skill，为了让新项目和新对话能够召回它，可以作为例外安装到用户级全局目录。

## 环境与兼容性

- Python 3.10 或更高版本；运行时不依赖第三方 Python 包。
- 克隆、更新、checkout、仓库状态及 `onboard` 的本地来源取证需要 Git。
- macOS 和 Linux 使用目录软链接。
- Windows 支持目录软链接和 junction。软链接可能需要开启 Developer Mode 或使用管理员终端；junction 通常不需要。
- Codex、Claude Code 以及其他能从兼容项目目录发现 Agent Skills 的工具，可以共享同一个项目级 skill 入口。

## 通过 npx 安装

这里的 `npx skills` 是开源 Agent Skills 生态的安装 CLI。它从 GitHub 等来源发现并安装包含有效 `SKILL.md` 的 skill，不需要把本项目发布成 npm 包。

先查看仓库能发现哪些 skills：

```bash
npx skills add xhanzo-coder/e8-skill-linker --list
```

项目级安装到 Codex：

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --agent codex
```

全局安装到 Codex：

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --global \
  --agent codex
```

同时安装到 Codex 和 Claude Code：

```bash
npx skills add xhanzo-coder/e8-skill-linker \
  --skill e8-skill-linker \
  --global \
  --agent codex claude-code
```

安装完成后，首次使用 `e8-skill-linker` 时，它仍然会检查中央库配置，并在需要时询问是否进行全局自举安装。`npx skills add` 负责安装管理型 skill，本身不会自动创建或选择 `~/.e8-skill-linker/AgentSkills`。

更新或卸载全局安装的管理型 skill：

```bash
npx skills update e8-skill-linker --global
npx skills remove e8-skill-linker --global --agent codex
```

更多安装来源和 CLI 选项见 [Skills CLI](https://www.skills.sh/docs/cli)。

## 第一次使用

首次触发时，skill 会按以下顺序工作：

1. 使用 `onboard --project .` 只读盘点用户级、当前项目和已登记中央库，展示名称、用途、范围、原件位置、来源证据、重复关系和问题。不会扫描其他项目或执行第三方脚本。
2. 展示清单后推荐用户级安装管理器；已安装则复用，未安装不影响先看盘点结果。
3. 有有效中央库则推荐复用；疑似库先让用户确认角色；配置或来源清单损坏先报告。没有库时推荐 `personal` 和非全局路径，或让用户指定已有自定义目录，不强制搬家。
4. 让用户选择“只初始化”或具体接管项；已有 skills 默认全部保留，创建库不等于自动迁移。
5. 汇总管理器、配置、接管项、备份、原入口范围与未处理项的完整计划，结束本轮等待确认；确认后只执行选定动作。
6. 普通独立目录采用有备份的本地快照接管，保留原用户级/项目级入口。验证并提供恢复凭据；不将未知来源伪装成可更新 Git 仓库。

可以直接说：“用 skill-linker 盘点我的用户级和当前项目 skills，先给我清单和建议，不要迁移。”

```bash
python skills/e8-skill-linker/scripts/skill_manager.py onboard --project .
```

`migrate` 先输出计划及内容摘要，确认后还须提供 `--expected-digest <摘要> --dependencies-reviewed --execute`。`restore-adoption --receipt <凭据>` 先预览恢复，确认后加 `--execute`，保留中央副本。详见[首次使用与接管](skills/e8-skill-linker/references/first-use-and-adoption.md)。

来源识别有边界：文档 URL 仅为候选，业务项目的父级 Git remote 不作为 skill 来源；其他安装器锁文件目前仅列出待审查位置，未做通用格式解析。无 Git 元数据的目录不能保证找回来源或安装版本。任意旧 Git 安装转受管理仓库仍需单独核验，尚无一键转换命令。

默认不会把 `~/.agents/skills`、`~/.codex/skills` 或 `~/.claude/skills` 当作中央库。如果用户选择这些全局目录，必须明确提醒它们可能让 skills 对所有项目可见，并要求确认。

CLI 也会强制确认例外选择：只有用户确认使用 Agent 全局目录后才添加 `--allow-global-central`；只有用户确认最终中央路径故意不包含 `.e8-skill-linker/AgentSkills` 时才添加 `--allow-non-namespaced-central`。

Agent 全局目录通常会同时触发这两项提醒，因此只有用户分别确认两种影响后，执行时才能同时添加两个参数。

## 配置中央库

用户级配置文件为：

```text
~/.skill-linker.json
```

项目级配置文件为：

```text
当前项目/.skill-linker.json
```

项目级配置整体优先于用户级配置。schema v2 可登记多个命名中央库，但一份生效配置同时只选择一个 `active_library`。

配置示例：

```json
{
  "schema_version": 2,
  "libraries": {
    "personal": {
      "path": "/Users/you/.e8-skill-linker/AgentSkills"
    },
    "work": {
      "path": "/Volumes/Work/.e8-skill-linker/AgentSkills"
    }
  },
  "active_library": "personal",
  "default_mode": "centralize"
}
```

Windows 示例：

```json
{
  "schema_version": 2,
  "libraries": {
    "personal": {
      "path": "C:\\Users\\you\\.e8-skill-linker\\AgentSkills"
    }
  },
  "active_library": "personal",
  "default_mode": "centralize"
}
```

先执行 dry-run：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize
```

用户确认后再执行：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize \
  --execute
```

如果用户提供的是自定义父目录，使用 `--central-base`，实际中央库会派生为 `<父目录>/.e8-skill-linker/AgentSkills`：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --library personal \
  --central-base "/Users/name/Desktop/WorkSpace" \
  --mode centralize
```

## 常用命令

以下命令默认只检查或 dry-run。涉及写入时，用户确认后再增加 `--execute`。

```bash
# 查看当前项目、用户级目录和链接状态
python3 skills/e8-skill-linker/scripts/skill_manager.py inspect --project .

# 查看当前生效配置
python3 skills/e8-skill-linker/scripts/skill_manager.py config --project .

# 查看所有命名库与生效作用域
python3 skills/e8-skill-linker/scripts/skill_manager.py library-list --project .

# 显式将 v1 配置升级为 v2（先 dry-run）
python3 skills/e8-skill-linker/scripts/skill_manager.py migrate-config --scope user --library personal

# 向用户配置增加 work 库（先 dry-run）
python3 skills/e8-skill-linker/scripts/skill_manager.py library-add \
  --scope user --name work --central-base /Volumes/Work

# 检查失效链接和结构问题
python3 skills/e8-skill-linker/scripts/skill_manager.py check --project .

# 同时检查用户级 Agent 目录和已配置的中央库
python3 skills/e8-skill-linker/scripts/skill_manager.py check \
  --project . \
  --include-user \
  --include-central

# 初始化项目级入口
python3 skills/e8-skill-linker/scripts/skill_manager.py init \
  --project . \
  --agents claude,codex

# 链接中央库中的一个 skill
python3 skills/e8-skill-linker/scripts/skill_manager.py link \
  --project . \
  --source ~/.e8-skill-linker/AgentSkills/write-blog

# 链接多个 skills
python3 skills/e8-skill-linker/scripts/skill_manager.py link-many \
  --project . \
  --sources ~/.e8-skill-linker/AgentSkills/a,~/.e8-skill-linker/AgentSkills/b

# 完整保留第三方仓库，创建中央入口，并在当前项目启用
python3 skills/e8-skill-linker/scripts/skill_manager.py install-repo \
  --project . \
  --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer,reviewer=.agents/skills/reviewer \
  --enable-project

# 从当前项目停用 skill，只删除入口链接
python3 skills/e8-skill-linker/scripts/skill_manager.py unlink \
  --target .agents/skills/write-blog

# 检查中央目录中的 Git 仓库更新
python3 skills/e8-skill-linker/scripts/skill_manager.py updates --project .
```

`link`、`link-many` 和 `migrate` 会拒绝未配置或未授权的源路径。不要把下载目录、桌面目录、仓库根目录或临时目录直接作为软链接目标。

## 多中央库与仓库更新

项目链接在所有平台上保留中央入口这一层，Windows junction 也遵循相同结构：

```text
项目/.agents/skills/writer
  → 中央库/writer
    → 中央库/.repos/github.com/owner/repository/skills/writer
```

`install-repo`、`link`、`link-many`、`check`、`updates`、`update` 可使用 `--library work` 单次选库，不修改 `active_library`。项目级配置仍完整覆盖用户配置。每个库独立保存仓库与来源清单；切换默认库会显示当前项目链接的归属，但保留原链接。

以下示例从本仓库执行；在其他目录使用时，请将脚本改为绝对路径。带 `--execute` 的示例以已审查并确认作用范围为前提。

```bash
# 安装到 work，以后增加同仓库的其他 skill 时复用该仓库
python3 skills/e8-skill-linker/scripts/skill_manager.py install-repo \
  --library work --repo-url https://github.com/example/skills.git \
  --skills writer=skills/writer --execute

# 在另一个项目通过中央入口启用已有 skill
python3 skills/e8-skill-linker/scripts/skill_manager.py link \
  --project /path/to/project --library work \
  --source /Volumes/Work/.e8-skill-linker/AgentSkills/writer --execute

# 联网检查生效配置中的全部中央库
python3 skills/e8-skill-linker/scripts/skill_manager.py updates --all-libraries --execute

# 应用已经审查的 work 库仓库更新
python3 skills/e8-skill-linker/scripts/skill_manager.py update --library work \
  --repo /Volumes/Work/.e8-skill-linker/AgentSkills/.repos/github.com/example/skills --execute

python3 skills/e8-skill-linker/scripts/skill_manager.py check --all-libraries
```

更新检查以 `.skill-linker-lock.json` 为权威仓库清单，不再扫描中央库根层的旧式 Git 仓库。`.repos` 非空却缺少清单时直接报错。清单中的 revision 记录已安装提交，不能代替 fetch 检测 GitHub 更新。

`updates` 输出区分 `local-cache`、`fetched` 和 `fetch-failed`。只有本次 fetch 成功才有新获取的远端状态；获取失败或没有 upstream 时是“未知”，不能报告成“已是最新”。目前没有后台自动检查。

`update` 先 fetch，从 Git 对象中检查已登记 skill 的路径和身份，再通过 `git merge --ff-only <候选SHA>` 应用已验证提交，最后校验入口并写入 revision。有本地改动、detached HEAD、没有 upstream、分叉、skill 路径消失或名称变化时停止。候选版本被拒绝时工作区保持原样，但已获取的 Git 元数据保留。应用后的校验或清单写入若失败，报告实际状态，不自动 reset 工作区。

报告区分仓库变更、直接修改的已安装 skills、新增/删除的 skill 路径及尚未暴露的 skills。共享资源变化也可能影响其他 skill。上游新增 skill 需要用户显式选择，再次运行 `install-repo` 即可复用仓库追加入口。根目录 skill 用 `name=.`，名称允许不同于仓库名。

已有项目中直接指向 `.repos` 的旧链接不会自动重建。先通过 `check` 查看直接目标，再明确执行 unlink/link，使其经过中央入口。管理器自身替换安装时，备份固定保存到 `~/.e8-skill-linker/backups/e8-skill-linker/`，避免旧副本被 Agent 重复发现。

所有平台都允许仓库目录名与 skill 名称不同。例如 `--skills codex-with-chatgpt=skill` 将 `skill/SKILL.md` 暴露为 `codex-with-chatgpt` 入口。入口名必须匹配 frontmatter `name`，来源路径必须位于仓库内，不重命名上游目录。

项目根目录必须已经存在。操作当前项目时，从环境取得真实工作目录并使用 `--project .`，不要手抄路径标点，也不要在 `cd` 失败后继续执行。安装和链接完成后输出已验证的项目入口绝对路径、直接目标及可读的 skill 身份；只校验中央库不能证明项目安装成功。

普通安装请求遵循“只读检查与计划 → 结束本轮等待确认 → 执行并验证”。确认前不克隆（含临时克隆）、fetch、写配置、建链接或运行第三方脚本；dry-run 成功不等于用户确认。中央库已有但项目未启用时，先给启用计划；目标已全部满足时展示核对单，明确“本次仅检查，未执行安装、未修改文件”，建议保留现状，不重跑写入命令。第三方依赖和初始化另行授权。同一计划的已有确认，或用户主动、明确要求跳过确认且作用范围明确时，无需重复询问。这项对话要求不能靠 CLI 参数强制证明，对应的独立行为检查见[交互回放用例](tests/interaction-cases.md)。

## Windows

Windows 上可以使用目录 symlink，也可以使用 junction：

```powershell
python skills\e8-skill-linker\scripts\skill_manager.py init `
  --project . `
  --agents claude,codex `
  --link-type junction

python skills\e8-skill-linker\scripts\skill_manager.py link `
  --project . `
  --source C:\Users\you\.e8-skill-linker\AgentSkills\write-blog `
  --link-type junction
```

创建 symlink 可能需要 Developer Mode 或管理员终端。Agent 可以检测并解释权限错误，但不应该静默提权、绕过 UAC 或输入管理员密码。

## 安全行为

- 默认先做只读检查或 dry-run。
- 在配置中央库、迁移、同步、克隆、更新、checkout、删除或创建链接前，先列出计划并等待确认。
- 不用链接覆盖已有真实目录。
- 批量链接或初始化多个 Agent 入口前，先完成所有目标的预检。
- 用户明确确认替换全局 `e8-skill-linker` 时，先保留旧版本备份。
- 用户说“删除 skill”时，默认只从当前项目停用，不删除中央原件。
- 通过链接编辑 skill 会修改中央原件，并影响所有指向它的项目。
- 拒绝路径穿越名称以及指向未授权目录的链接。
- 第三方 skill 有本地修改、没有 upstream 或无法 fast-forward 时，不自动 pull；长期维护时先讨论 fork 和 Git 策略。

完整信任边界和私密漏洞上报方式见 [SECURITY.md](SECURITY.md)。

## 仓库结构

```text
e8-skill-linker/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── workflows/ci.yml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── README.zh-CN.md
├── SECURITY.md
├── scripts/validate_skill.py
├── skills/
│   └── e8-skill-linker/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       └── scripts/
└── tests/
    ├── test_skill_manager.py
    ├── test_repository_workflows.py
    ├── test_onboarding.py
    └── interaction-cases.md
```

## 开发与验证

本项目遵循 [Agent Skills Specification](https://agentskills.io/specification)。修改 skill 后，至少检查：

```bash
python3 scripts/validate_skill.py skills/e8-skill-linker
python3 -m unittest discover -s tests -v
python3 -m py_compile skills/e8-skill-linker/scripts/skill_manager.py tests/test_skill_manager.py
```

CI 会在 Ubuntu、macOS 和 Windows 上使用 Python 3.10 与 3.13 运行验证和测试。详细 Agent 流程应放在 `skills/e8-skill-linker/references/`；README 面向人类用户，不是 Agent 的运行规则。

欢迎参与贡献。请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，安全问题通过 [SECURITY.md](SECURITY.md) 中的私密渠道报告，版本变化记录在 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目使用 [MIT License](LICENSE) 开源。
