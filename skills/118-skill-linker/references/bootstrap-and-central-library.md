# 自举安装与中央库配置

## 自举安装检查

每次触发后，先判断 `118-skill-linker` 自己是否已经安装在用户级全局 Agent skills 目录中，例如：

- `~/.agents/skills/118-skill-linker`
- `~/.codex/skills/118-skill-linker`
- `~/.claude/skills/118-skill-linker`

如果当前加载的是项目级副本或非全局中央库副本，先向用户说明：

```text
118-skill-linker 是管理型 skill。为了让新项目和新对话能自动召回它，建议把它安装到用户级全局 skills 目录。
这是管理器自身的例外；业务型 skills 仍然不默认全局安装，而是放在非全局中央库中，再按项目软链接启用。
```

不要自动迁移或安装。给出计划并等待用户确认。推荐确认口令：

```text
确认全局安装 118-skill-linker
```

确认后再执行安装。优先把当前稳定副本复制/同步到 `~/.agents/skills/118-skill-linker`；如果当前 Agent 需要 `~/.codex/skills` 或 `~/.claude/skills` 才能全局发现，则再创建对应全局入口链接。不要把所有业务 skills 一起迁移到全局目录。

## 配置文件

支持用 `.skill-linker.json` 记住用户已经确认过的中央 skills 目录。

普通个人使用时，默认推荐写用户级配置 `~/.skill-linker.json`，让这台电脑上的新项目和新对话都能复用同一个中央 skills 目录。项目级 `.skill-linker.json` 只是覆盖例外，只有用户明确说某个项目要用另一套中央库、团队共享库、客户隔离库或测试库时才建议写入。

中央 skills 库不应该默认等同于 Agent 全局 skills 目录。首次没有配置时，默认推荐 `118-skill-linker` 专属的非全局目录：

```text
macOS/Linux: ~/.118-skill-linker/AgentSkills
Windows: %USERPROFILE%\.118-skill-linker\AgentSkills
```

这个目录用于存放 skill 原件；它不是 Agent 全局 skills 目录，不会默认让所有项目启用里面的 skill。用户也可以自定义一个父目录，例如 `~/Skills`、`~/GitHub/<repo>`、`/Volumes/WorkDisk` 或 `D:\AI`。当用户提供的是父目录时，实际中央库必须派生为 `<父目录>/.118-skill-linker/AgentSkills`，不要把 skill 原件直接散放在用户选择的父目录下。

`~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills` 是 Agent 全局发现目录；把中央库放在那里会让很多 skill 变成全局可见，只有用户明确选择这种模式时才使用。

读取优先级：

1. 当前项目 `.skill-linker.json`
2. 用户级 `~/.skill-linker.json`
3. 没有配置时，推荐默认中央目录，同时扫描候选目录并允许用户自定义

推荐的用户级配置位置：

```text
macOS/Linux: ~/.skill-linker.json
Windows: C:\Users\you\.skill-linker.json
```

配置示例：

```json
{
  "central_skills_dir": "/Users/name/.118-skill-linker/AgentSkills",
  "default_mode": "centralize"
}
```

Windows 配置示例：

```json
{
  "central_skills_dir": "C:\\Users\\name\\.118-skill-linker\\AgentSkills",
  "default_mode": "centralize"
}
```

字段含义：

- `central_skills_dir`：已经确认过的中央 skills 原件目录。
- `default_mode: "centralize"`：默认把项目里真实 skill 迁入或同步到中央目录，再把项目入口改为软链接。
- `default_mode: "project-local"`：允许当前项目 `.agents/skills` 作为本项目内部中心目录。
- `default_mode: "ask"`：每次列出选项，让用户选择。

项目级配置优先级高于用户级配置，但不要把“优先级更高”理解为“默认应该写项目配置”。项目级配置用于覆盖全局默认；如果用户只是第一次确认中央目录，优先建议写入用户级配置。

## 首次触发流程

用户第一次要求“管理 skills”“统一 skills”“同步 Codex 和 Claude 的 skills”或类似任务时，按以下顺序处理：

1. 先运行只读检查，不创建目录、不创建软链接、不删除文件。
2. 先读取配置文件：
   - 如果当前项目 `.skill-linker.json` 存在，使用它。
   - 否则如果 `~/.skill-linker.json` 存在，使用它。
   - 如果配置中的中央目录存在，明确写出 `[已配置中央目录]`，不要重新猜测中央目录。
3. 同时扫描用户级目录和当前项目目录：
   - 用户级：`~/.agents/skills`、`~/.codex/skills`、`~/.claude/skills`
   - 项目级：`.agents/skills`、`.codex/skills`、`.claude/skills`
4. 汇总发现：哪些目录存在、哪些不存在、哪些是真实目录、哪些是软链接、哪些软链接已经失效、哪些 skill 名在多个位置重复、哪些路径可能是中央 skills 目录。
5. 如果已有有效配置，围绕配置的中央目录生成方案。
6. 如果没有配置，推荐默认中央目录：macOS/Linux 使用 `~/.118-skill-linker/AgentSkills`，Windows 使用 `%USERPROFILE%\.118-skill-linker\AgentSkills`；同时说明用户可以自定义非全局路径。
7. 如果用户选择自定义路径，先判断它是“父目录”还是“最终中央目录”。默认把用户给的自定义路径当父目录处理，并派生实际中央库 `<自定义路径>/.118-skill-linker/AgentSkills`；只有用户明确说“这就是最终中央目录”且路径已经包含 `.118-skill-linker/AgentSkills` 时，才直接使用该路径。
8. 如果用户选择 `~/.agents/skills`、`~/.codex/skills` 或 `~/.claude/skills` 这类 Agent 全局目录，先给出全局可见风险提醒，并要求明确确认口令 `确认使用全局 skills 目录作为中央库`。
9. 用户确认中央目录后，给出“写入配置 + 创建 `<父目录>/.118-skill-linker/AgentSkills` 中央命名空间目录 + 迁移或同步项目真实 skill + 创建项目入口软链接”的计划。不要把“只整理当前项目级入口、不迁移到中央库”作为推荐方案。
10. 在没有配置且用户未确认中央目录前，不要执行迁移、同步、替换或 git 更新。

如果没有发现明显的中央目录，推荐 `~/.118-skill-linker/AgentSkills` 或 Windows 的 `%USERPROFILE%\.118-skill-linker\AgentSkills`，并询问用户是否接受或自定义父目录；不要自行创建中央目录，除非用户明确同意。

## 反例

如果用户选择 `/Users/name/Desktop/WorkSpace` 作为中央库位置，不要把配置写成 `/Users/name/Desktop/WorkSpace/AgentSkills` 或 `/Users/name/Desktop/WorkSpace`。正确做法是把它当父目录，配置为 `/Users/name/Desktop/WorkSpace/.118-skill-linker/AgentSkills`，并在计划中明确会创建 `.118-skill-linker/AgentSkills`。

如果项目里有 `.agents/skills/foo` 真实目录，同时只发现 `~/.agents/skills`，不要回复“我建议先只整理当前项目级入口，不迁移到用户级中央库”，也不要把 `~/.agents/skills` 标成默认推荐中央库。正确做法是说明 `~/.agents/skills` 是 Agent 全局目录，并推荐 `~/.118-skill-linker/AgentSkills`；用户确认后，再给出“写入用户级配置 + 创建中央命名空间目录 + 迁移或同步项目真实 skill + 创建项目入口软链接”的计划。
