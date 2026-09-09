---
name: avatar-troubleshoot
description: 虚拟人集成故障诊断与修复。用于错误码、黑屏、连接失败，以及 avatar authentication failed、authorization invalid、WebSocket 1008 等运行时鉴权问题。
tags:
  - troubleshooting
  - debugging
  - diagnosis
priority: high
optional_tools:
  - name: query-scene-config
    when: 连接失败类（10110/10113/10114/10121）——查场景发布状态与配置
    fallback: 按 references/error-code-lookup.md 手动排查
  - name: publish-scene
    when: 确认 sceneId 未发布（10121）后一键修复
    fallback: 指引用户在控制台手动发布
---

# avatar-troubleshoot: 故障排查

## 定位

虚拟人集成任务的**故障诊断与修复**，快速定位和解决常见问题。

## 调用时机

- 用户报告错误或异常行为
- 提供了错误码
- 由 `avatar-workflow-entry` 路由
- 验证失败时诊断原因

---

## 诊断流程

```
Step 1: 收集信息
Step 2: 错误码查询
Step 3: 症状匹配
Step 4: 根因分析
Step 5: 生成修复方案
Step 6: 验证修复

→ 输出: 诊断报告 + 修复建议
```

| 步骤 | 目的 | 详细参考 |
|------|------|----------|
| Step 1 收集信息 | 确定平台/错误码/症状/日志 | references/info-collection.md |
| Step 2 错误码查询 | 查错误码库定位根因 | references/error-code-lookup.md |
| Step 3 症状匹配 | 无错误码时按症状匹配场景 | references/symptom-matching.md |
| Step 4 根因分析 | 决策树 + 根因分类 | references/root-cause-analysis.md |
| Step 5 生成修复方案 | 输出结构化诊断报告 | references/fix-plan.md |
| Step 6 验证修复 | 编译/运行/功能/回归验证 | references/fix-verification.md |

---

## 决策分支（场景 → 应读哪个 reference）

- **需要向用户收集信息** → references/info-collection.md
- **已有错误码，需要查库** → references/error-code-lookup.md
- **无错误码，只有症状描述** → references/symptom-matching.md
- **需要走排查决策树 / 判定根因类别** → references/root-cause-analysis.md
- **准备输出修复方案** → references/fix-plan.md
- **修复后需要验证** → references/fix-verification.md
- **需要标准输出结构（diagnosed / needs_more_info / unable_to_diagnose）** → references/output-formats.md
- **`avatar authentication failed` / `authorization invalid` / 1008 / 10110 / 10113 / 10114 / 10120 / 10121** →
  必须读 `references/authentication-failed.md` 并执行其中的证据驱动恢复流程
- **Android Gradle 构建卡住 / 超时 / 缓存锁 / daemon 异常 / 下载慢** → `../shared/android-gradle-stability.md`

分析策略：**有错误码**直接查错误码库（Step 2）；**无错误码**走症状匹配 + 逐步排查（Step 3 → Step 4）。

Android 构建类故障必须按 `../shared/android-gradle-stability.md` 的「卡住诊断」和「超时后的强制流程」
处理：命令超时先检查原 Gradle/Java 进程并续接，禁止立即重复运行；禁止无依据执行
`clean --refresh-dependencies`、禁止递归删除全局 Gradle 缓存、禁止用杀死全部 Java 进程代替定位
具体 daemon。

---

## 关键约束 / Red Flags

排查方法约束：

- **优先检查错误码**，其次症状库匹配，避免过度深入排查。
- 修复方案必须**标注难度与预估时间**，并附**验证方法**。
- 修复后必须做**回归验证**（文本驱动、事件监听、资源释放仍正常），防止引入新问题。
- 面向用户使用**友好语言**，避免技术黑话，提供具体命令和代码。
- 新问题应回写到错误码库，更新症状匹配规则与诊断决策树。

Web 运行时高频坑（写代码时提前规避，详见运行时案例 reference）：

1. **鉴权失败不能只凭通用文案定因** —— scene 未发布、凭据错配、资源未授权、签名过期等都可能表现为
   `authentication failed`；必须按 `references/authentication-failed.md` 取得平台或关闭码证据
2. **bitrate 必须 ≥ 200** —— 数字类型，推荐 2000
3. **NLP answer 是对象** —— 取 `data.answer.displayContent`，不要直接拼接
4. **流式 NLP 是累积内容** —— 复用同一消息框更新，不要每帧新建
5. **SDK 在 esm 子目录** —— 路径 `/sdk/avatar-sdk-web_*/esm/index.js`，动态导入加 `/* @vite-ignore */`
6. **自动播放需用户交互** —— 监听 `playNotAllowed`，浏览器安全策略无法绕过

完整领域约束见 `rules/avatar-domain/sdk-conventions.md`。

---

## 常见问题快速索引

### 1. 连接失败
```yaml
症状: 无法连接、初始化失败、WebSocket 超时
错误码: 10110, 10113, 10114, 10200, 10201
诊断: avatar-network-debug
快速检查:
  - [ ] appId/apiKey/apiSecret 拼写正确
  - [ ] sceneId 已发布
  - [ ] 网络可达
  - [ ] 防火墙放行 WebSocket
```
> 工具增强：若用户提供了 `xfyun-tools`，可用 `python tools/xfyun_model_manage.py query <sceneId>`
> 直接确认发布状态；确认 10121（未发布）后用 `publish <sceneId>` 一键修复。
> 无工具则指引控制台手动发布。

### 2. 黑屏无视频
```yaml
症状: 画面黑屏、视频区域空白
错误码: 20002, 700002, 700003, 10120
快速检查:
  - [ ] 收到 stream_start 事件
  - [ ] 播放器创建成功
  - [ ] avatarId 已授权
  - [ ] 播放器依赖完整
```

### 3. 无声音
```yaml
症状: 画面有但无声音
错误码: NotAllowedError (Web)
快速检查:
  - [ ] (Web) 是否收到 playNotAllowed 事件
  - [ ] (Web) 是否在用户交互后调用 player.resume()
  - [ ] (Android) 系统音量是否静音
  - [ ] (iOS) AVAudioSession 是否配置正确
```

### 4. 录音无反应
```yaml
症状: 麦克风无法使用、录音失败
错误码: 20003, NotAllowedError
诊断: avatar-permissions-setup
快速检查:
  - [ ] (Web) HTTPS 或 localhost 环境
  - [ ] 权限配置 (AndroidManifest / Info.plist)
  - [ ] 运行时权限已申请
  - [ ] 系统设置中权限已开启
```

### 5. Web 运行时常见案例（6 个实测 bug 案例集）

实际 Web 项目运行时高频遇到的 6 个现象，详细诊断和修复代码见对应 reference：

| 现象 / 错误 | 严重度 | 详解 |
|------------|--------|------|
| `avatar authentication failed` / 1008（通用鉴权失败，必须取证后定因） | Critical | references/authentication-failed.md |
| `bitrate value must be larger or equal than 200` | Critical | references/bitrate-and-sdk.md |
| `Failed to fetch dynamically imported module`（SDK esm 路径） | High | references/bitrate-and-sdk.md |
| 有视频无声音 / `playNotAllowed`（自动播放限制） | Medium | references/bitrate-and-sdk.md |
| NLP 回复显示 `[object Object]`（需取 displayContent） | High | references/nlp-display.md |
| 流式 NLP 一句话刷屏、每帧新建消息框 | High | references/nlp-display.md |

> 需要系统性自检时 → references/runtime-check.md（`runtimeCheck()` 自检函数，已集成到 `avatar-verification` Layer 7 运行时验证）。

---

## 工具增强（authentication failed 自动诊断 + 修复）

`avatar authentication failed` 是通用错误文案，不等于“场景没 publish”。若存在平台工具，先只读查询
app/scene 归属、类型、发布状态和资源授权，再按已确认根因执行单项修复：

```bash
python tools/xfyun_query_services.py list-apps
python tools/xfyun_query_services.py list-scenes
python tools/xfyun_model_manage.py check <sceneId>
python tools/xfyun_model_manage.py query-interact <sceneId>
```

只有平台查询明确确认未发布时才运行 `publish`；scene 不存在/归属错误时走 `xfyun_interface.py create`；
资产未授权时走 `xfyun_interface.py auth-avatar`。平台写操作需在用户修复授权范围内执行。完整命令、权限边界、
复验和停止条件见 `references/authentication-failed.md`。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| references/info-collection.md | Step 1 信息收集：必需/可选信息字段、交互式收集脚本 |
| references/error-code-lookup.md | Step 2 错误码查询：错误码库加载、10113 匹配示例、修复建议模板 |
| references/symptom-matching.md | Step 3 症状匹配：症状库加载、黑屏场景示例、diagnoseNoVideo 诊断脚本 |
| references/root-cause-analysis.md | Step 4 根因分析：黑屏排查决策树、四类根因（配置/依赖/代码/环境） |
| references/fix-plan.md | Step 5 修复方案：诊断报告结构模板、修复优先级（Critical/High/Medium） |
| references/fix-verification.md | Step 6 验证修复：基础/回归验证清单、verifyFix 验证脚本 |
| references/output-formats.md | 三种标准输出格式：diagnosed / needs_more_info / unable_to_diagnose |
| references/error-codes.yaml | 错误码数据库（errors + scenarios） |
| references/authentication-failed.md | 运行时案例 6：鉴权失败（sceneId 未发布/凭据错误/时长耗尽）的诊断+修复流程 |
| references/bitrate-and-sdk.md | 运行时案例 1/3/4：bitrate、SDK esm 路径、自动播放的诊断+修复代码 |
| references/nlp-display.md | 运行时案例 2/5：NLP [object Object]、流式刷屏的完整方案 |
| references/runtime-check.md | runtimeCheck() 自检函数 + avatar-verification Layer 7 集成 |

---

## 排障收尾（条件上报）

问题确认解决后上报，但**仅在以下条件全部满足时**：

1. 本次对话的**原始诉求就是排障**（用户一开头就是报错/黑屏/错误码），
   而不是在 SDK 集成、模板创建等流程中途顺带修的问题
2. 问题已实际验证修复（重跑复现步骤不再出错），不是只给了建议
3. 本次未由 `avatar-verification` 或其他终局 skill 上报过完成

```bash
python "${CLAUDE_PLUGIN_ROOT}/tools/telemetry.py" complete --type troubleshoot
```

不满足任一条 → **不要**执行。集成流程中途的排障由该流程自己的终局 skill 上报，
在此重复上报会导致同一工作流被计两次。

---

## 相关技能

- `avatar-workflow-entry`: 路由入口
- `avatar-network-debug`: 网络问题专项诊断
- `avatar-permissions-setup`: 权限问题专项处理
- `error-codes.yaml`: 错误码数据库
