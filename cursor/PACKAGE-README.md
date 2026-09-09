# iflytek-digital-human - Cursor 插件包

这是 `iflytek-digital-human` 1.1.0 的 Cursor 适配包，包含 Agent Skills、配套 Python 工具、配置、规则和参考资料。

## 从 GitHub 导入

在 Cursor Dashboard 中打开：

`Plugins` -> `Team Marketplaces` -> `Add Marketplace` -> `Import from Repo`

填写仓库地址：

`https://github.com/firstdebug/avatar-platform`

仓库根目录的 `.cursor-plugin/plugin.json` 会把 Cursor 组件指向 `cursor/skills/` 和 `cursor/agents/`。导入后可在 Cursor 的 `Customize` -> `Plugins` 或 `Customize` -> `Skills` 中检查是否已启用。

## 直接使用包目录

如果不使用 Marketplace，也可以将本目录中的 `skills/` 复制到目标项目的 `.cursor/skills/`，或复制到用户目录 `~/.cursor/skills/`。入口 Skill 为 `avatar-workflow-entry`。首次调用时，入口会先展示 `docs/capabilities.md` 和 `tools/telemetry.py notice` 的完整声明，再等待用户明确同意或拒绝使用统计；拒绝不影响功能。本地遥测状态保存在 `~/.cursor/iflytek-digital-human/telemetry`，报文 `agent` 默认为 `cursor`。

## 运行依赖

- Python 3.8 或更高版本
- `pip install -r tools/requirements.txt`
- 涉及网页登录时执行 `playwright install chromium`

工具运行时可能创建 `.runtime/`；该目录、Cookie 和凭据不得提交到 Git。

## 平台差异

Cursor 不执行 Claude Code 的 `UserPromptSubmit`、`Stop` 或 `SessionEnd` Hook，因此任务路由和生命周期记录由 Skill 显式执行：入口通过 `telemetry.py start` 获取 `workflowId`，下游使用 `invoke`，最后用同一 ID 执行 `complete` 或 `fail`；宿主被强制关闭时不能伪造完成事件。建议直接从 `avatar-workflow-entry` 开始。此包不依赖 `${CLAUDE_PLUGIN_ROOT}`，工具路径以当前包目录为基准。
