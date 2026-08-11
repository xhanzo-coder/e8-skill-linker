# Windows 链接兼容

Windows 可以使用中央目录 + 项目链接方案，但链接机制和权限与 macOS/Linux 不同。

## 优先顺序

1. 先尝试普通目录 symlink。
2. 如果失败，说明可能需要开启 Windows Developer Mode 或使用管理员权限终端。
3. 如果只是链接 skill 目录，可以建议使用 junction：`mklink /J`。
4. 不要自动提权，不要绕过 UAC，不要代替用户输入管理员密码。

## 概念说明

- symlink：最接近 macOS/Linux 的软链接，命令类似 `mklink /D link target`。
- junction：Windows 的目录联接，命令类似 `mklink /J link target`，常用于目录，权限要求通常更友好。
- `.lnk` 快捷方式：不要用于 skills；很多 Agent 和脚本不会把 `.lnk` 当真实目录读取。

## 脚本行为

- 默认 `--link-type auto`。
- 在 Windows 上，`auto` 会先尝试 symlink；如果权限不足，会尝试 junction。
- 如果 junction 也失败，向用户说明 Developer Mode、管理员终端和手动 `mklink /J` 命令。
- 用户明确想使用 junction 时，传入 `--link-type junction`。

Agent 引导用户时可以这样说明：

```text
当前 Windows 环境可能没有权限创建目录 symlink。
你可以选择开启 Developer Mode、用管理员权限终端重试，或改用 junction。
我不会自动提权；你确认后我可以继续生成或执行对应命令。
```
