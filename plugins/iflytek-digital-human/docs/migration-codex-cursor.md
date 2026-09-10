# 迁移到 Codex / Cursor 说明

本目录是 iflytek-digital-human 的 Codex 适配包；本仓库同时包含 Claude Code、Cursor / Codex 适配包，三者使用各自的安装目录。若从 Claude Code 源包重新生成适配包，除了执行格式转换命令外，还需处理几处平台差异。本文档说明完整步骤与已知降级项。

## 一、转换命令

```bash
# 转换到 Cursor
npx -y @disdjj/acplugin convert . -t cursor

# 转换到 Codex
npx -y @disdjj/acplugin convert . -t codex
```

> **执行前务必确认**：真实密钥、登录态、个人信息已从仓库清除。否则会被一并复制进转换产物。本仓库已完成清理，但若你重新跑过依赖 cookie 的脚本（如 `tools/xfyun_common.py` 登录），会重新生成 `xfyun_cookies.json`，转换前需再次删除。

## 二、转换命令覆盖不到的事

`convert` 只做 skill/agent 的**格式转换**，以下都不在它的处理范围内，需要手动完成。

### 1. Python 工具链依赖

`tools/*.py` 依赖三个第三方库，转换后在新环境仍需手动安装：

```bash
pip install -r tools/requirements.txt
playwright install chromium   # playwright 装库后还需单独装浏览器
```

Codex / Cursor 的运行环境不保证有 Python3 或这些库。若目标环境无法跑 Python，依赖 `tools/` 的 skill（凭据获取、知识库、直播创建等）将无法执行。

### 2. Hooks 接入边界

Claude Code 的 Hook 机制与 Codex 的 Hook 机制均只对当前消息中的显式 skill 调用启用；自然语言、引用历史、代码块和普通后端 NLP 调试不会触发隐私门禁。

Claude Code 源包的 `hooks/hooks.json` 注册了 `UserPromptSubmit` 钩子：当前消息显式调用 `/iflytek-digital-human:<skill>` 或 `$iflytek-digital-human:<skill>` 时运行 `hooks/route_hint.py`，把本地授权状态注入上下文。

Claude Code 与当前稳定版 Codex 都支持这组生命周期事件。Codex 包通过根目录 `hooks.json` 注册 `UserPromptSubmit`、`PreToolUse`、`PostToolUse`、`Stop` 和 `SessionEnd`；命令处理器使用 `commandWindows`、`timeout`、同步 `async: false` 和 Codex 的 `hookSpecificOutput`。`hooks/list` 返回的运行时元数据会把超时显示为 `timeoutSec`，不要反向写进配置文件。Cursor 仍不假设提供同等生命周期，因此入口 Skill 保留显式门禁作为兼容路径：

| 项目 | Claude Code 源包 | Codex 适配包 | Cursor 适配包 |
|------|-------------|----------------|----------------|
| 入口 Skill 是否存在 | 是 | 是 | 是 |
| `UserPromptSubmit` 自动路由 | 有 | 有 | 无对应生命周期假设 |
| 首次授权门禁 | Hook 注入状态 | Hook 注入 + PreToolUse / Stop 阻断 + 入口回退 | 入口 Skill 显式执行 |
| workflow / invocation | Hook 辅助记录 | Hook 辅助 + `telemetry.py start` / `invoke` 显式兜底 | 显式记录 |
| 完成或失败 | Stop / SessionEnd + Reporter | Stop 只验证，真实完成仍走门禁和显式 `complete` / `fail` | 显式收口 |
| 用户体验 | 提到“虚拟人”即自动分流 | 强虚拟人信号自动分流 | 需显式调用入口 Skill |

Cursor 少了自动分流这一层，补偿方式二选一：

- 在 Cursor 的 rules / system prompt 里，把“检测到虚拟人关键词 → 先走 avatar-workflow-entry”的规则写进去；
- 或在用户文档里注明：处理虚拟人任务前需显式调用入口 Skill。

Hook 文件存在不等于已生效。Codex 首次加载或 Hook 内容变化后会进入未受信任状态，必须由用户在宿主信任界面确认；自动化环境只有在外部已经审查 Hook 来源时才能使用 `--dangerously-bypass-hook-trust`。Hook 被关闭、未受信任或 Python 不可用时，入口 Skill 的显式流程仍然有效。

显式生命周期不能模拟宿主未提供的强退事件。Codex 的 `SessionEnd` 只会把未完成 workflow 收口为 `interrupted`，不会伪造成 `completed`；进程被直接杀死而来不及触发 Hook 时，本地 workflow 保持 `in_progress`。

### 3. 路径与命令假设

Skill 里大量使用 `python tools/xfyun_xxx.py` 这类命令，并用 `<plugin-root>` 表示当前已安装包的根目录。转换后：

- `<plugin-root>` 是文档占位符，不是环境变量；执行前应解析为当前 Codex 包的真实绝对路径。
- 工作目录可能与 Claude Code 不同，优先使用解析后的绝对脚本路径。

### 4. 凭据获取流程

当前 `tools/` 提供两条获取密钥的路线：

- **浏览器登录**（`xfyun_common.py`）：由当前用户登录讯飞平台，并把 Cookie 仅保存在当前包的 `.runtime/`；不得复用或提交他人的登录态。
- **用户自填 + 本地加密**（`xfyun_secrets.py`）：让用户自己输入 appId/apiKey/apiSecret，加密存储在本地。

发布给他人使用时，两条路线都必须使用终端用户自己的账号或凭据，Cookie、SSO token 和密钥不得进入对话、遥测报文或版本库。

## 三、转换后验证清单

转换完成后，在**每个**目标平台分别实测，不要只信"转换成功"：

- [ ] 入口 skill `avatar-workflow-entry` 能被识别/调用
- [ ] `pip install -r tools/requirements.txt` 且 `playwright install chromium` 成功
- [ ] 至少跑通一个依赖 `tools/` 的 skill（如凭据验证）
- [ ] 确认路径/环境变量替换后命令可执行
- [ ] 确认自动路由降级已通过 rules 或文档补偿
- [ ] 全库再次扫描无真实密钥/appId/session 残留

## 四、推荐顺序

1. 确认清理无误（密钥、cookie、备份文件均已移除）
2. 去讯飞控制台重置曾泄漏的密钥并重新登录使旧 session 失效
3. 执行 `convert`
4. 按上面清单逐项验证

