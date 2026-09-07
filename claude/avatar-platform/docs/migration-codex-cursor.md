# 迁移到 Codex / Cursor 说明

本插件原生为 Claude Code 编写。迁移到 Codex 或 Cursor 时，除了执行格式转换命令外，还需处理几处平台差异。本文档说明完整步骤与已知降级项。

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

### 2. Hooks 自动路由会失效（降级项）

`hooks/hooks.json` 注册了一个 `UserPromptSubmit` 钩子：每次用户发消息时运行 `hooks/route_hint.py`，检测"虚拟人/数字人"等关键词，自动把请求导向入口 skill `avatar-workflow-entry`，并把本地授权状态注入上下文，避免模型重复执行状态检查命令。

这是 **Claude Code 独有机制**，Codex / Cursor 没有对应的 `UserPromptSubmit` 概念。转换后：

| 项目 | Claude Code | Codex / Cursor |
|------|-------------|----------------|
| 入口 skill 是否存在 | 是 | 是（转换保留） |
| 关键词自动触发路由 | 有 | **失效** |
| 用户体验 | 提到"虚拟人"即自动分流 | 需显式调用入口 skill |

**功能不会崩溃**，只是少了自动分流这一层便利。补偿方式二选一：

- 在目标平台的 rules / system prompt 里，把"检测到虚拟人关键词 → 先走 avatar-workflow-entry"的规则写进去；
- 或在用户文档里注明：处理虚拟人任务前需手动调用入口 skill。

### 3. 路径与命令假设

skill 里大量使用 `python tools/xfyun_xxx.py` 这类相对路径命令，并依赖环境变量 `${CLAUDE_PLUGIN_ROOT}` 定位插件根目录。转换后：

- `${CLAUDE_PLUGIN_ROOT}` 是 Claude Code 特有变量，Codex / Cursor 下不存在，需替换为目标平台的等价定位方式或绝对路径。
- 工作目录可能与 Claude Code 不同，确认相对路径 `tools/...` 仍从插件根目录解析。

### 4. 凭据获取流程

当前 `tools/` 提供两条获取密钥的路线：

- **cookie 抓取**（`_fetch_creds.py` + `xfyun_common.py` 登录）：依赖作者本地登录态，**别人的环境跑不通**，仅作者本地开发用。
- **用户自填 + 本地加密**（`xfyun_secrets.py`）：让用户自己输入 appId/apiKey/apiSecret，加密存储在本地。

发布给他人使用时，应以 `xfyun_secrets.py` 这条路线为主，并在文档里引导用户自行填入凭据。不要期望终端用户能复用 cookie 抓取路线。

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

