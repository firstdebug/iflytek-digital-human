# iflytek-digital-human

> 原插件 ID `avatar-platform` 已整体更名为 `iflytek-digital-human`。升级时请先卸载或禁用旧插件，避免两套 Hook 或 Skill 同时加载。首次运行新版本时，会将旧遥测目录中的授权状态和未完成工作流复制到新目录；旧目录保留用于回退。

讯飞虚拟人交互平台接入插件，覆盖 Web 对话模板、数字人直播、Web/Android/iOS SDK、WebAPI、模型配置、知识库、凭据获取和故障排查。

本仓库同时发布 Claude Code、Codex 和 Cursor 版本。三者使用独立目录；增加或更新 Cursor 包不会改变 Claude Code、Codex 的安装入口。

## 安装

### Claude Code

```bash
claude plugin marketplace add https://github.com/firstdebug/avatar-platform.git
claude plugin install iflytek-digital-human@iflytek-digital-human-marketplace
```

验证：

```bash
claude plugin list
```

### Codex

```bash
codex plugin marketplace add firstdebug/avatar-platform --ref main
codex plugin add iflytek-digital-human@iflytek-digital-human-codex
```

验证：

```bash
codex plugin list
```

安装或更新后，请新建一个 Codex 任务，使新的 Skills 和 agents 生效。

### Cursor

Cursor 当前推荐通过 Dashboard 导入 GitHub 插件仓库：

1. 打开 Cursor Dashboard 的 `Plugins` -> `Team Marketplaces`。
2. 选择 `Add Marketplace` -> `Import from Repo`。
3. 输入 `https://github.com/firstdebug/avatar-platform` 并导入。
4. 在 Cursor 的 `Customize` -> `Plugins` 或 `Customize` -> `Skills` 中确认 `iflytek-digital-human` 已启用。

仓库根目录的 `.cursor-plugin/plugin.json` 专门用于 Cursor 导入，实际内容位于 `cursor/skills/`、`cursor/tools/`、`cursor/config/`、`cursor/rules/` 和 `cursor/agents/`。也可以只将 `cursor/skills/` 复制到项目的 `.cursor/skills/` 或用户目录 `~/.cursor/skills/`。

## 使用

统一入口为 `avatar-workflow-entry`。也可以直接描述需求，例如：

- 创建 Web 智能客服虚拟人
- 在 Android 应用中接入虚拟人 SDK
- 通过 WebAPI 从后端驱动虚拟人
- 配置大模型或知识库
- 排查鉴权、黑屏、无声音或网络问题

## 仓库结构

```text
iflytek-digital-human/
├─ .claude-plugin/marketplace.json  # Claude Code marketplace
├─ .agents/plugins/marketplace.json  # Codex marketplace
├─ .cursor-plugin/plugin.json        # Cursor 根仓库插件清单
├─ claude/iflytek-digital-human/           # Claude Code 自包含插件
├─ plugins/iflytek-digital-human/          # Codex 自包含插件
├─ cursor/                           # Cursor 适配包
└─ README.md
```

各平台只读取自己的 manifest 和包目录：

- Claude Code：`claude/iflytek-digital-human/`
- Codex：`plugins/iflytek-digital-human/`
- Cursor：`cursor/`

## 运行依赖

Cursor 工具需要 Python 3.8+：

```bash
pip install -r cursor/tools/requirements.txt
playwright install chromium
```

Claude Code 和 Codex 工具仍分别从各自包目录运行。

## 安全

- 不要提交 `.runtime/`、Cookie、`.env`、API Key 或 API Secret。
- Web 生产接入应在服务端签名，不要把 `apiSecret` 写入前端代码。

## 版本

当前版本：`1.0.0`
许可证：MIT
