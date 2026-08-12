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

- 中央库保存 skill 原件，默认推荐 `~/.e8-skill-linker/AgentSkills`。
- macOS/Linux 的 Agent 全局目录通常是 `~/.agents/skills`、`~/.codex/skills` 或 `~/.claude/skills`。
- Windows 使用 `%USERPROFILE%\.e8-skill-linker\AgentSkills` 作为默认中央库。
- 项目级 `.agents/skills`、`.codex/skills` 和 `.claude/skills` 是当前项目的入口。

业务 skills 默认不直接安装到 Agent 全局目录。`e8-skill-linker` 自己是管理型 skill，为了让新项目和新对话能够召回它，可以作为例外安装到用户级全局目录。

## 环境与兼容性

- Python 3.10 或更高版本；运行时不依赖第三方 Python 包。
- 只有克隆、更新、checkout 和仓库状态命令需要 Git。
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

1. 检查 `e8-skill-linker` 是否已经安装在用户级 Agent skills 目录中。
2. 读取当前项目和用户级 `.skill-linker.json`。
3. 如果没有配置，推荐非全局中央库：macOS/Linux 使用 `~/.e8-skill-linker/AgentSkills`，Windows 使用 `%USERPROFILE%\.e8-skill-linker\AgentSkills`。
4. 允许用户提供自定义父目录，并在该目录下派生 `.e8-skill-linker/AgentSkills`。
5. 只读扫描项目级和用户级 skills，明确区分来源、目标和影响。
6. 对配置、迁移、同步、链接、删除、克隆和 Git 更新先给出计划，用户确认后才执行。

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

项目级配置优先于用户级配置。普通个人使用建议只配置一个用户级中央库；项目级配置用于团队共享、客户隔离或测试场景。

配置示例：

```json
{
  "central_skills_dir": "/Users/you/.e8-skill-linker/AgentSkills",
  "default_mode": "centralize"
}
```

Windows 示例：

```json
{
  "central_skills_dir": "C:\\Users\\you\\.e8-skill-linker\\AgentSkills",
  "default_mode": "centralize"
}
```

先执行 dry-run：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize
```

用户确认后再执行：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
  --central ~/.e8-skill-linker/AgentSkills \
  --mode centralize \
  --execute
```

如果用户提供的是自定义父目录，使用 `--central-base`，实际中央库会派生为 `<父目录>/.e8-skill-linker/AgentSkills`：

```bash
python3 skills/e8-skill-linker/scripts/skill_manager.py config \
  --scope user \
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

# 从当前项目停用 skill，只删除入口链接
python3 skills/e8-skill-linker/scripts/skill_manager.py unlink \
  --target .agents/skills/write-blog

# 检查中央目录中的 Git 仓库更新
python3 skills/e8-skill-linker/scripts/skill_manager.py updates \
  --central ~/.e8-skill-linker/AgentSkills
```

`link`、`link-many` 和 `migrate` 会拒绝未配置或未授权的源路径。不要把下载目录、桌面目录、仓库根目录或临时目录直接作为软链接目标。

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
└── tests/test_skill_manager.py
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
