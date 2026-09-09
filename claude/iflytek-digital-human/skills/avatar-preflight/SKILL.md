---
name: avatar-preflight
description: 虚拟人平台开发环境门禁（HARD-GATE）。在进入设计/编码前，分层验证凭据、资源授权、SDK 依赖、网络连通、工具链和最小链路，确保开发环境就绪。
optional_tools:
  - name: query-services
    when: Layer 1 凭据验证——用户已登录控制台，可自动拉取场景与凭据
    fallback: 走 references/credentials.md 手动输入流程
  - name: check-scene-capability
    when: Layer 2 资源授权——自动检查场景是否具备 LLM 对话授权
    fallback: 参考 references/resource-authorization.md 手动确认
---

# avatar-preflight — 环境门禁

分层预检技能。在虚拟人应用开发进入设计与编码阶段前，作为**强制门禁**逐层验证开发环境是否就绪。

## 触发条件 / 调用时机

- 由 `avatar-brainstorming` 在 Phase 2 之后调用，作为进入 Phase 3（意图分类）前的 HARD-GATE
- 用户主动执行 `avatar-preflight`
- 强制重检：`avatar-preflight --force-recheck` 或删除 `~/.avatar-code/dev-env.yaml`

## 核心工作流概览

按 Layer 顺序执行，前一层 FAIL 原则上阻塞后续层。Layer 0 判定平台后，Layer 3 与 Layer 5 走对应平台分支。

| Layer | 名称 | 平台范围 | 是否必选 | 详细 reference |
|-------|------|----------|----------|----------------|
| 0 | 平台判定 | 全部 | 必选 | （在本文件决策分支中判定） |
| 1 | 凭据验证 | 全部 | 必选 | `references/credentials.md` |
| 2 | 资源授权（avatarId / vcn） | 全部 | 必选 | `references/resource-authorization.md` |
| 3 | SDK 依赖检查 | 平台差异 | 必选 | 见平台分支 |
| 4 | 网络连通性 | 全部 | 必选（4.2 可选） | `references/network-validation.md` |
| 5 | 工具链验证 | 本地开发平台 | 平台差异 | 见平台分支 |
| 6 | 最小验证（首帧链路） | 全部 | 可选但强烈建议 | 见平台分支 + `references/network-validation.md` |

## 决策分支（场景 → 应读哪个 reference）

- **判定平台后按平台读实现细节**：
  - Web 平台（SDK 文件 / 浏览器环境 / Web 工具链 / Web 最小验证）→ 详见 `references/web-implementation.md`
  - Android 平台（AAR / Gradle / 权限 / Android 工具链 / Android 最小验证）→ 详见 `references/android-implementation.md`
  - iOS 平台（Framework / Info.plist / 签名 / iOS 工具链 / iOS 最小验证）→ 详见 `references/ios-implementation.md`
- **凭据读取与有效性验证**（含错误码 10110/10113/10114）→ 详见 `references/credentials.md`
- **形象/发音人授权检查与用户选择交互** → 详见 `references/resource-authorization.md`
- **WebSocket / 流媒体连通性、最小验证通用链路** → 详见 `references/network-validation.md`
- **门禁结果处理、缓存复用规则、成功/失败 JSON 输出结构** → 详见 `references/gate-results-and-output.md`

## 工具增强（自动化预检）

如果用户提供了 `xfyun-tools`（见 `config/tools.yaml`），Layer 1/2 可自动化，免手输：

```bash
# 检测工具
if [ -f tools/xfyun_query_services.py ]; then
    # Layer 1: 自动拉取账号下所有场景与凭据（输出脱敏）
    python tools/xfyun_query_services.py
    # → 让用户选择场景，自动获得 sceneId/appId/apiKey（apiSecret 从控制台 API 取，不进对话框）

    # Layer 2: 自动检查该场景是否具备对话能力（LLM 授权）
    python tools/xfyun_model_manage.py check <sceneId>
    # → 有授权则 Layer 2 PASS，无授权直接给出"换场景/联系平台开通"建议
fi
```

**优势**: 凭据不进对话框、自动脱敏、一次拉取多场景。
**Fallback**: 工具不存在或执行失败时，降级到 `references/credentials.md` 与
`references/resource-authorization.md` 的手动流程。安全约束（apiSecret 不落文件、
测试后断开、日志脱敏）在两种路径下都必须遵守。

---

## 关键约束 / HARD-GATE / Red Flags

### HARD-GATE 原则（不可绕过）
- 环境门禁是**强制通过**的检查；任何 FAIL 都应阻止进入后续设计阶段
- 允许"跳过"选项，但**必须明确风险提示**：
  - 跳过凭据验证 → 后续连接必定失败
  - 跳过 SDK 检查 → 编译/运行时错误
  - 跳过网络检查 → 运行时连接失败

### 安全约束（Red Flags）
- **apiSecret 绝不保存到文件**，每次从环境变量或用户输入读取
- 测试连接后**立即断开**，避免占用并发路数
- 日志中**脱敏**敏感信息

### 关键错误码（速查）
| 错误码 | 含义 |
|--------|------|
| 10110 | appId 不存在或格式错误 |
| 10113 | apiSecret 错误或签名生成有误 |
| 10114 | sceneId 不存在或未发布 |
| 10120 | avatarId 未授权 |

### 平台差异要点
- Web：侧重浏览器环境和 HTTPS（麦克风权限要求 HTTPS 或 localhost）
- Android/iOS：侧重工具链、签名和权限

### 用户体验与性能
- 检查失败时给出**明确的修复建议**和**直达链接**（控制台、文档、下载），避免技术黑话
- 利用缓存避免重复检查；并行执行无依赖的检查项；网络检查设置合理超时

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/credentials.md` | Layer 1：凭据读取来源、用户输入提示、保存策略、有效性验证代码、错误码处理 |
| `references/resource-authorization.md` | Layer 2：形象授权检查、发音人授权检查、检查方式与用户交互 |
| `references/web-implementation.md` | Layer 3.1 / 5.3 / 6：Web SDK 文件检查、浏览器环境检查、Web 工具链、Web 最小验证 |
| `references/android-implementation.md` | Layer 3.2 / 5.1 / 6：AAR 检查、Gradle 配置、权限配置、Android 工具链、Android 最小验证 |
| `references/ios-implementation.md` | Layer 3.3 / 5.2 / 6：Framework 检查、Info.plist 权限、签名配置、iOS 工具链、iOS 最小验证 |
| `references/network-validation.md` | Layer 4 / 6：WebSocket 连通性、流媒体连通性、最小验证通用链路 |
| `references/gate-results-and-output.md` | 门禁结果处理（全 PASS / 部分 FAIL）、缓存与复用规则、成功/失败 JSON 输出格式 |

## 验证清单 / 交接协议

门禁通过后：
1. 将验证结果写入 `~/.avatar-code/dev-env.yaml`（结构见 `references/gate-results-and-output.md`）
2. 返回 `avatar-brainstorming`，进入 Phase 3（意图分类）
3. 部分 FAIL 时输出：失败检查项、失败原因、修复建议、相关文档链接（结构见 `references/gate-results-and-output.md`）

缓存复用规则：SDK 路径缓存有效跳过扫描；工具链 24 小时内缓存有效；网络 1 小时内缓存有效；apiSecret 始终重新读取。

## 相关技能

- `avatar-workflow-entry`：智能路由入口
- `avatar-brainstorming`：调用本技能的父流程
- `toolchain`：工具链详细检查（按 platform 参数走 web/android/ios 分支）
- `avatar-config-authoring`：配置文件生成
