# 输出格式与确认规则

## 一个目标、一份计划、一次确认

只读检查不要求确认。配置、安装、同步、迁移、替换、备份、链接、删除、`git fetch`、Git 更新或 checkout 前，必须先给用户一份计划。属于同一个用户目标的多个写入步骤应组合成一个原子计划，不要让用户为每个内部步骤重复确认。计划至少包含：

- 是否会写入配置文件；如果会，写明是用户级 `~/.skill-linker.json` 还是项目级 `.skill-linker.json`
- 如果写入用户级配置，说明这会影响这台电脑上以后所有未设置项目级覆盖的项目
- 如果用户提供的是自定义父目录，说明实际中央库会创建在 `<父目录>/.e8-skill-linker/AgentSkills`
- 将创建哪些目录
- 将创建哪些软链接，以及每个软链接指向哪里
- 将跳过哪些已有目录或冲突项
- 是否会备份任何内容
- 是否会删除软链接
- 是否会克隆仓库，以及克隆到哪里
- 将使用哪个命名中央库，仓库是否进入 `<central>/.repos/<host>/<owner>/<repo>`
- 仓库中哪些 `name=relative/path` 将被暴露为中央 skill 入口
- 是否写入 `<central>/.skill-linker-lock.json`
- 是否会运行 `git fetch`、快进到已验证提交或 `git checkout`；联网检查和实际更新分开说明
- 明确说明不会删除真实 skill 目录，除非用户明确要求

用户确认后再执行。执行中出现计划外冲突时停止并回滚本次新建内容；不静默改用另一个中央库、别名或链接策略。执行完成后，再运行检查命令验证结果。

更新结果注明库名与 freshness。只有本次 fetch 成功的仓库才有已核实的远端状态，失败和未获取不能写成“没有更新”。显示直接变更的 skills 与仓库共享文件；切换默认库时显示现有项目链接的实际归属。Git 更新后若验证或清单写入失败，报告当前 HEAD 和失败，不声称 Git 工作区已自动回滚。

## 用户级与项目级必须分开

向用户汇报检查结果和整理方案时，必须把“用户级”和“项目级”分开写清楚。不要只写 `.agents/skills`、`.codex/skills`、`.claude/skills`，因为这些名称在用户级和项目级都可能出现。

整理方案必须额外区分五种角色：

- 活动中央库：当前生效配置选中的命名库，例如 `personal`
- 仓库存储层：`<central>/.repos`，保存完整第三方 Git 仓库
- 中央 skill 入口：中央库根层的真实 skill 目录或指向 `.repos` 的链接
- 项目级入口目录：当前项目引用 skills 的入口，例如 `/abs/project/.agents/skills`
- Agent 入口目录：Codex 或 Claude 在当前项目读取的入口，例如 `/abs/project/.codex/skills`、`/abs/project/.claude/skills`

必须明确说明：项目级 `.agents/skills` 只是当前项目的 skills 入口目录，不是中央 skills 库；用户级 `~/.agents/skills` 是 Agent 全局目录，也不应默认当中央库。

路径必须尽量同时提供：

- 层级标签：`用户级`、`项目级`、`中央候选`、`备份目录`
- Agent 标签：`通用 .agents`、`Codex .codex`、`Claude .claude`
- 相对路径：例如 `.codex/skills`
- 绝对路径：例如 `/Users/name/project/.codex/skills`
- 状态：`真实目录`、`软链接`、`junction`、`失效链接`、`不存在`

## 推荐汇报格式

```text
项目根目录：
/abs/path/to/project

中央目录：
- [用户级配置][非全局中央目录][真实目录] ~/.e8-skill-linker/AgentSkills
  绝对路径：/Users/name/.e8-skill-linker/AgentSkills

当前项目入口目录：
- [项目级][通用 .agents][入口目录] .agents/skills
  绝对路径：/abs/path/to/project/.agents/skills
  说明：这是当前项目的 skills 入口目录，不是中央库

项目级 skills：
- [项目级][通用 .agents][真实目录] .agents/skills
  绝对路径：/abs/path/to/project/.agents/skills
  数量：41
- [项目级][Codex .codex][真实目录] .codex/skills
  绝对路径：/abs/path/to/project/.codex/skills
  数量：47

用户级 skills：
- [用户级][Codex .codex][真实目录] ~/.codex/skills
  绝对路径：/Users/name/.codex/skills
```

## 推荐执行计划格式

```text
我建议执行以下变更：

| 动作 | 来源 | 目标 | 影响 | 是否删除真实目录 |
| --- | --- | --- | --- | --- |
| 写入用户级配置 | 无 | [用户级配置] /Users/name/.skill-linker.json | 后续未设置项目级覆盖的项目默认使用该中央目录 | 否 |
| 创建中央命名空间目录 | [自定义父目录] /Users/name/Desktop/WorkSpace | [中央目录] /Users/name/Desktop/WorkSpace/.e8-skill-linker/AgentSkills | skill 原件集中放在带 e8-skill-linker 标识的目录下 | 否 |
| 迁移 | [项目级][通用 .agents] /abs/project/.agents/skills/foo | [中央目录] /Users/name/.e8-skill-linker/AgentSkills/foo | foo 原件进入中央目录 | 否 |
| 备份 | [项目级][Claude] /abs/project/.claude/skills | /abs/project/.skill-linker-backup/.../.claude/skills | 保留原目录副本 | 否 |
| 建立软链接 | [项目级][通用 .agents] /abs/project/.agents/skills/foo | /Users/name/.e8-skill-linker/AgentSkills/foo | 当前项目入口指向中央原件 | 否 |
| 建立软链接 | [项目级][Claude] /abs/project/.claude/skills | ../.agents/skills | Claude 入口指向当前项目入口目录 | 否 |
```

确认口令要包含作用范围，避免用户误解。例如：

```text
如果你确认要整理“当前项目级 skills”，请回复：确认整理当前项目
```

不要使用含糊口令，例如只写“确认整理”。如果操作会影响用户级目录，确认口令必须明确写出“用户级”。

如果计划会写入用户级配置或迁移到中央目录，确认口令必须体现配置和中央目录影响，例如：

```text
如果你确认要写入用户级配置并使用非全局中央目录整理“当前项目级 skills”，请回复：确认写入用户级配置并整理当前项目
```
