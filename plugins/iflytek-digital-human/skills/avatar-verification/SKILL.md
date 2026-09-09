---
name: avatar-verification
description: 项目交付前的完整验证流程。自动检测并修复常见问题，确保项目开箱即用。
---

# avatar-verification: 交付前验证

## 定位

在项目交付给用户前，自动执行完整的验证流程，检测并修复常见问题，确保用户拿到的是**开箱即用**的项目。

先读 `../avatar-shared/delivery-modes.md`，接收上游 `workflow_mode: quick | strict`。

- `quick`：执行完整验证，但只在上下文和最终回复中保留简短结果，不创建 `verification-report.md`。
- `strict`：执行完整验证并按 `references/integration-output.md` 生成审计报告。

**模式只改变报告形态，不降低验证覆盖**：`quick` 同样要跑完构建、运行、凭据安全和目标功能验证。
只验证用户确认启用的能力——用户未选择语音时，不把麦克风权限、录音或 ASR 当作必检项。

Android 构建必须读取 `../avatar-shared/android-gradle-stability.md`，串行完成在线预热与 `--offline` 复验。

**调用时机**:
- 项目代码生成完成后
- 凭据配置完成后
- SDK 下载完成后
- 启动服务器之前（HARD-GATE；Web SDK 由 `web_delivery.py` 管理）

---

## 关键约束

- **HARD-GATE**: Web SDK 项目必须由 `tools/web_delivery.py run` 管理凭据、canonical auth 模块、服务状态和最终验证；只有状态机返回 `ready_to_deliver: true` 才交付给用户。
- **固定端点门禁**：`WS_URL` 必须由工具写成
  `wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`；不得询问用户、接受其他 host/path，或自行拼接控制台 URL。
- **门禁上报由状态机负责**：退出码 2（静态阻断）和退出码 3（等待运行证据）都保持同一 workflow 为
  `in_progress`，由 `web_delivery.py` 自动调用非终态 `report_gate`，记录 `gate/status/remaining_issues`；
  模型不得手动调用 `report_gate`、`report_fail` 或 `report_complete` 改写状态。
- Critical 问题未修复 → 禁止交付。
- 能自动修复的问题优先自动修复；无法自动修复的问题必须列入 `remaining_issues` 并回退到 `avatar-troubleshoot`。
- Web SDK 项目不得直接运行 `web_sdk_gate.py`；首次运行 `python "<plugin-root>/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction "<target>"`，浏览器证据产生后重复同一命令；只有退出码 0 才能交付。

### Red Flags（最常见的交付前问题）

- `bitrate < 200` → SDK 报错 `value must be larger or equal than 200`，修复为 2000
- SDK 路径错误 → SDK 加载失败，需匹配实际下载目录
- 凭据未用 `import.meta.env.VITE_*` 加载
- 缺少关键事件监听（connected / error / disconnected）
- SDK 未下载 / node_modules 未安装

---

## 核心工作流概览

按顺序执行 7 层验证，每层失败记录 issue，最后统一汇总并尝试自动修复。

| Layer | 名称 | 检查内容 |
|-------|------|----------|
| 1 | 文件完整性 | 所有必需文件存在且内容完整 |
| 2 | 凭据验证 | `.env` 存在、格式正确、值非空 |
| 3 | SDK 验证 | SDK 已下载、路径正确、关键文件存在 |
| 4 | 依赖验证 | `node_modules` 存在、`package.json` 正确 |
| 5 | 配置参数验证（关键） | 检查并修复已知错误配置 |
| 6 | 编译验证 | 代码语法正确、无明显错误 |
| 7 | 运行时验证 | 启动开发服务器、检查报错 |

---

## 工具增强（Layer 2 发布状态确认）

`.env` 格式正确≠凭据可用——**sceneId 未发布**是头号交付后连接失败原因（10121 /
`authentication failed`）。本地校验查不出，但若用户提供了 `xfyun-tools`，可主动确认：

```bash
if [ -f tools/xfyun_model_manage.py ]; then
    # 查询场景真实配置：是否已发布、是否具备对话能力
    python tools/xfyun_model_manage.py query <sceneId>
    # → 未发布则 Layer 2 记为 Critical issue，交接 avatar-model-config publish 修复
fi
```

**Fallback**: 无工具时，Layer 2 只做本地格式校验，并在报告中**明确提醒**用户手动确认
控制台已点击"发布"。

---

## 决策分支（场景 → 应读哪个 reference）

- **Layer 5 配置参数验证 / 已知配置陷阱（bitrate、SDK 路径、凭据加载、事件监听）的检测与自动修复代码** → 详见 `references/config-checks.md`
- **完整验证流程实现（`verifyProject()` 全量代码，含 7 层逻辑与自动修复汇总）** → 详见 `references/verify-workflow.md`
- **集成到 avatar-executing 工作流、验证报告格式、输出结构（passed / failed）** → 详见 `references/integration-output.md`

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/config-checks.md` | Layer 5 已知配置陷阱：bitrate、SDK 路径、凭据加载、事件监听的检测函数与自动修复函数 |
| `references/verify-workflow.md` | `verifyProject()` 完整实现：7 层验证流程、问题分级、自动修复汇总 |
| `references/integration-output.md` | 集成到 avatar-executing（Step 8-10）、验证报告格式、输出 YAML 结构 |

---

## 验证清单 / 交接协议

交付前必须确认:
- [ ] 第一项先检查本轮浏览器证据是否出现 `avatar authentication failed`、
  `authorization invalid`、WebSocket 1008 或 10110/10113/10114/10120/10121/11203；命中时
  `web_sdk_gate.py` 返回 `authentication_failed`，先走
  `../avatar-troubleshoot/references/authentication-failed.md`，禁止判定完成
- [ ] Layer 1-7 全部通过（或已自动修复）
- [ ] 无未修复的 Critical 问题
- [ ] `ready_to_deliver: true`

交接:
- 验证通过 → 交付给用户（开箱即用）
- 验证失败且无法自动修复 → 调用 `avatar-troubleshoot` 处理 `remaining_issues`

---

## 验证结果落盘（必做）

Web SDK 的验证结论必须由确定性交付状态机落盘，模型不得手写 `ready_to_deliver: true`：

```bash
python "<plugin-root>/tools/web_delivery.py" run \
  --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" \
  --interaction "<text|voice|audio>"
```

- 退出码 2 / `failed`：静态门禁失败，修复后在同一 workflow 复验。
- 退出码 3 / `needs_runtime_verification`：缺少新鲜的 `connected`、`stream_start`、首帧或目标交互浏览器证据，仍是同一 workflow。
- 退出码 0 / `ready_to_deliver`：工具已写入新鲜的 `.runtime/verification-result.json`，才允许完成上报。

`.runtime/web-runtime-evidence.json` 必须由 Playwright/浏览器验证产生，并晚于本轮源码和 SDK 变更；不能由模型按预期值手工构造。

仅在状态机退出码为 0 后才会自动上报完成状态；2/3 只上报门禁，不写 `ended_at` 或 `completion_method`。
模型不得手动调用 Reporter complete：

由 `web_delivery.py` 内部调用，禁止单独执行。

---

## 相关技能

- `avatar-executing`: 执行后调用本技能
- `avatar-troubleshoot`: 如果验证失败，调用故障排查
- `avatar-code-reviewer` (agent): 代码审查后验证配置
