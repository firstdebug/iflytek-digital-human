# Web SDK 构建 Playbook（HARD-GATE 强制流程）

> **适用**：用户要求"用 SDK 自建 Web 虚拟人工程"（非官方模板、非直播）。
> **原则**：本文件是 Web SDK 自建工程的**唯一权威落地流程**。按此流程生成的代码必须**一次运行成功**，
> 不允许"先生成、再靠报错逐个打补丁"。所有字段值来自 SDK 反编译核对（v3.2.3.1002）与
> `avatar-webapi-protocol/references/protocols.md`。`index.d.ts` 是导出方式和方法签名的权威来源；协议载荷字段仍以本 Playbook 和协议文档为准，不能互相替代。

---

## 0. 为什么需要这个 Playbook（血泪根因）

SDK 的 TypeScript 类型定义（`index.d.ts` 的 `IGlobalConfig`）与**运行时实际发送到平台的报文结构不一致**。
只看类型定义写代码，会反复踩下面两个坑，且报错信息具有误导性：

| 症状（运行时报错） | 表面原因 | **真实根因（反编译确认）** |
|---|---|---|
| `'$.parameter.avatar.stream.bitrate' value must be larger or equal than 200` | 以为 bitrate 设小了 | SDK 内部对顶层 `stream.bitrate` 执行 **`Math.floor(bitrate/1024)`**。你写 `2000` → 实际发送 `floor(2000/1024)=1` → 触发 ≥200 校验失败 |
| `'$.parameter.avatar.stream.protocol' field is required` | 以为漏了字段 | 同源问题：顶层 stream 的单位/结构没按 SDK 预期给，导致组装出的 `avatar.stream` 不完整 |

**SDK 真实组装逻辑（反编译 `index.js` 的 start 报文构造函数）**：
```js
// globalConfig = 你传给 setGlobalParams 的对象
l = globalConfig.stream ?? {}
d = l.protocol ?? "xrtc"
v = l.bitrate  ?? 1000000                       // 默认 100万
h = { ...l 去掉 protocol/bitrate }              // 即 fps / alpha
_ = { ...globalConfig.avatar 去掉 avatar_id/width/height }  // 含你手写的 avatar.stream（若有）

parameter.avatar = Object.assign(
  { stream: { ...h, protocol:d, bitrate: Math.floor(v/1024) },   // ← SDK 自动算的 stream
    avatar_id, width, height },
  _                                              // ← _ 在后，若含 stream 会【覆盖】上面算出的 stream
)
```

**两条硬结论**：
1. SDK 会把顶层 `stream.bitrate` **除以 1024** 再发送。要让平台收到 `2000 kbps`，顶层要写 `2000*1024`，
   **或**干脆不写 bitrate（默认 100万/1024 ≈ 976 kbps，合法）。
2. `parameter.avatar.stream` 是 SDK **自动组装**的，**不是**必须你手填。若你在 `avatar` 里手写 `stream`，
   它会通过 `Object.assign` **覆盖** SDK 的计算结果（此时你写的值原样发送，不再 /1024）。

> 因此本 Playbook 采用**方案 A（推荐）**：显式手写 `avatar.stream` 并用真实 kbps 值，
> 让"所见即所发"（WYSIWYG），彻底避开 /1024 陷阱、且不依赖顶层 stream 的隐式换算。
> 这样任何人读代码看到 `bitrate: 2000` 就知道平台收到的就是 2000，不会有认知偏差。

---

## 1. 强制架构（安全 HARD-GATE）

Web 工程**必须**是"Node 后端 + 静态前端"，**禁止**纯静态页面把 `apiSecret` 写进前端 JS。

```
project/
├── server.js          # Node/Express：挂载 canonical handler、托管静态资源
├── xfyun-auth.mjs     # 由 websocket_auth.py 生成并校验哈希；读取 env、生成 signedUrl
├── package.json       # type:module, 依赖 express + dotenv
├── .env               # 凭据（必须进 .gitignore）
├── .gitignore         # 必含 .env / node_modules
├── public/
│   ├── index.html
│   ├── app.js         # SDK 集成（只拿 signedUrl，永远看不到 apiSecret）
│   └── style.css
└── sdk/               # avatar-sdk-web_3.2.3.1002（从 avatar-artifact-download 获取）
```

**理由**：`apiSecret` 一旦进前端 bundle，任何人 F12 就能拿到，等同泄露。服务端签名后前端只持有
一次性 `signedUrl`（会话级有效），是唯一合规做法。详见 `rules/avatar-domain/sdk-conventions.md` 安全约束。

**签名实现禁止手写**。`web_delivery.py` 会调用 `websocket_auth.py install` 生成 canonical 模块。
`server.js` 只保留以下挂载，不得出现 `createHmac()` 或自行拼 authorization：

```javascript
import { avatarAuthHandler, avatarConfigHandler } from './xfyun-auth.mjs';

app.get('/api/config', avatarConfigHandler);
app.get('/api/avatar-auth', avatarAuthHandler);
```

模块从 dotenv 已加载的 `process.env` 读取 `APP_ID/API_KEY/API_SECRET/SCENE_ID/AVATAR_ID/VCN/WS_URL`；
Key 和 Secret 必须都是完整 32 位，`WS_URL` 必须是 `wss://.../v1/interact`。最终 gate 会按 `.env`
中的 Secret 重新计算 HMAC，并核对 signed URL 的 host、path、date、headers 和 signature。

---

## 2. 六步构建流程（严格按序，每步有验证）

| Step | 动作 | 产出 | 验证方式 |
|------|------|------|----------|
| 1 | 确认凭据就绪 | `.env`（6 项凭据 + WS_URL） | `avatar-credentials` 校验 6 项齐全 |
| 2 | 下载 SDK | `sdk/.../esm/index.js` 存在 | `avatar-artifact-download` |
| 3 | 生成后端 `server.js` | 签名 + 静态托管 | 启动后 `/api/avatar-auth` 返回 signedUrl |
| 4 | 生成前端 `app.js` | SDK 集成（用锁定字段表） | 见 §3 字段锁定表逐项核对 |
| 5 | 生成 HTML/CSS + package.json | 可运行工程 | `npm install` 成功 |
| 6 | 启动 + 浏览器端到端验证 | 连接成功、首帧渲染 | 见 §5 验证清单 |

**HARD-GATE**：Step 4 生成的 `setGlobalParams` **必须**逐项对照 §3 锁定表，不允许自由发挥字段结构。

Step 1-2 必须由确定性编排器执行并检查退出码，不能改写成手动下载说明：

运行前主 agent 必须先 Read `../../avatar-credentials/SKILL.md`、`../../avatar-artifact-download/SKILL.md` 和
`../../avatar-network-debug/references/auth-verification.md`。这些是实际 Skill/参考读取，不能用状态机内部的 Python 调用冒充 invocation。

若当前 workflowId 已知（来自 Claude Code hook，或 Cursor/Codex 通过 `telemetry.py start` 返回），必须贯穿传入 `--workflow <workflowId>`；没有显式 workflowId 时才允许退回 project 作用域匹配。

```bash
python "<plugin-root>/tools/web_delivery.py" run --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" --interaction text --workflow "<workflowId>"
```

返回 `blocked_missing_sdk` 或其它非零退出码时，保持当前 workflow 进行中并修复确定性阻塞；不得继续宣称项目完成。下载后先读实际 `esm/index.d.ts`，确认默认导出与方法签名：

```javascript
const module = await import(sdkUrl);
const AvatarPlatform = module.default;
const { SDKEvents, PlayerEvents } = module;
```

禁止把 `AvatarPlatform` 当具名导出，也禁止使用类型文件中不存在的 `setServerUrl()`、`getPlayer()` 等调用。

---

## 3. setGlobalParams 字段锁定表（HARD-GATE — 逐项对照，不允许偏离）

以下是**唯一正确**的 `setGlobalParams` 结构。生成代码后**必须**逐字段核对。

```javascript
avatar.setGlobalParams({
  // 顶层 stream：SDK 会读 protocol/bitrate 用于组装（bitrate 会被 /1024）。
  // 保留它是为兼容 SDK 逻辑，但真实生效值以下面 avatar.stream 为准。
  stream: {
    protocol: 'xrtc',   // xrtc | webrtc | rtmp（透明背景必须 xrtc）
    fps: 25,            // 13-25
    bitrate: 2000,      // ⚠️ 顶层此值会被 SDK /1024，仅作占位；真实值看 avatar.stream
  },
  avatar: {
    avatar_id: config.avatarId,   // 平台授权的形象 id（未授权报 10120）
    width: 720,                   // 4 的倍数，[300,4096]
    height: 1280,                 // 4 的倍数，[300,4096]
    // ✅ 关键：手写 avatar.stream，值【原样发送】不再 /1024（WYSIWYG）
    stream: {
      protocol: 'xrtc',   // 必填，与顶层一致
      fps: 25,            // 必填
      bitrate: 2000,      // 必填，单位 kbps，[200,20000]，这就是平台实际收到的值
      alpha: 0,           // 必填，0=不透明 1=透明（透明仅 xrtc 生效）
    },
  },
  tts: {
    vcn: config.vcn,   // 平台授权的发音人 id
    speed: 50,         // [0,100]
    pitch: 50,         // [0,100]
    volume: 50,        // [0,100]
  },
  avatar_dispatch: {
    interactive_mode: 0,   // 0=append 追加 1=break 打断
  },
});
```

### 字段逐项约束（违反即连接失败）

| 路径 | 类型 | 合法值 | 必填 | 违反后果 |
|------|------|--------|------|----------|
| `avatar.stream.protocol` | string | xrtc/webrtc/rtmp | ✅ | `field is required` |
| `avatar.stream.fps` | int | 13-25 | ✅ | 组装不完整 |
| `avatar.stream.bitrate` | int | **200-20000（kbps）** | ✅ | <200 报 `must be ≥ 200` |
| `avatar.stream.alpha` | int | 0/1 | ✅ | 透明背景异常 |
| `avatar.avatar_id` | string | 已授权形象 id | ✅ | 10120 未授权 / 连上即断 |
| `avatar.width/height` | int | 4 的倍数 [300,4096] | ✅ | 渲染异常 |
| `tts.vcn` | string | 已授权发音人 | ✅ | 连上即断 |

> **绝对不要**只写顶层 `stream` 而省略 `avatar.stream` 并期望 `bitrate:2000` 生效——
> 那会走 SDK 的 /1024 逻辑，`2000` 变 `1`，必然报错。

---

## 4. 三个初始化顺序 HARD-GATE

摘自 `rules/avatar-domain/sdk-conventions.md`，**顺序错误必然连接失败**：

```
1. new AvatarPlatform()
2. setApiInfo({ signedUrl, appId, sceneId })   ← 用服务端签名 URL，不传 apiSecret
3. setGlobalParams({...})                        ← 必须在 start 前（照 §3 锁定表）
4. avatar.on(事件)                                ← 必须在 start 前注册，否则漏事件
5. await avatar.start({ wrapper })
```

**必须监听的 4 个事件**（缺一不可）：`connected` / `error` / `disconnected` / `stream_start`。
**必须处理**浏览器自动播放限制：监听 `PlayerEvents.playNotAllowed`，引导用户点击后 `player.resume()`。

服务端签名格式仍以 `../../avatar-network-debug/references/auth-verification.md` 为准，但实现只允许使用 canonical `xfyun-auth.mjs`。修改路由后立即运行 `node --check server.js`，不能在未启动检查的情况下继续。

---

## 5. 端到端验证清单（Step 6 — 全绿才算完成）

```
后端：
[ ] node server.js 启动无报错
[ ] curl /api/config 返回 appId/sceneId/avatarId/vcn
[ ] curl /api/avatar-auth 返回 signedUrl（含 authorization/date/host）
[ ] 前端 bundle 中 grep 不到 apiSecret（安全验证）

浏览器（localhost 或 HTTPS）：
[ ] 第一项先查本轮证据无 avatar authentication failed / authorization invalid / 1008 / 10110 / 10113 / 10114 / 10120 / 10121 / 11203
[ ] 点击启动 → 收到 SDKEvents.connected
[ ] 收到 SDKEvents.stream_start（云端推流）
[ ] 播放器首帧渲染（PlayerEvents.play/playing）
[ ] 文本驱动：writeText 后虚拟人播报
[ ] 语音交互（如启用）：录音 → asr 识别 → nlp 回复 → 播报
[ ] 无 bitrate/protocol 校验类报错
```

**若任一项失败**：先查 §0 根因表和 §3 锁定表，**不要**盲目改字段试错。

浏览器测试必须通过 `<plugin-root>/tools/web_runtime_evidence.py` 自动生成 `.runtime/web-runtime-evidence.json`。当 `web_delivery.py run` 返回 `awaiting_runtime_verification` 时，只执行返回 JSON 中 `next_action.commands[0]` 的证据采集命令；脚本会打开本轮 URL、点击启动按钮、等待 `connected / stream_start / first_frame`、执行文本交互，并写入 `prepared_at_epoch`、`credential_fingerprint`、`project_fingerprint`、`url`、目标交互和浏览器错误。不得由模型判断或手写 JSON 代替脚本采集。

自动 evidence 的目标是证明“虚拟人能出现并能通过文本链路回话”。语音、麦克风、录音、全双工不走无人自动化；如用户要求这些能力，必须单独询问并安排人工/真机验证，不能把 text evidence 包装成语音验证。

完成后再次运行同一个 `web_delivery.py run` 命令（保留同一个 `--workflow`），状态机内部才允许执行最终 gate 和完成上报：

```bash
python "<plugin-root>/tools/web_delivery.py" run --project "<project>" --interaction text --workflow "<workflowId>"
```

命中上述鉴权拒绝时，即使 `connected`、首帧或交互字段为 true，最终门禁也必须先返回
`authentication_failed`，执行 `avatar-troubleshoot/references/authentication-failed.md`，不得进入完成状态。

退出码 2 表示阻塞，3 表示 `needs_runtime_verification`，0 才表示 `ready_to_deliver`。Quick 与 Strict 都执行；Quick 只省略过程文档和常规 reviewer。模型不得手写运行证据、直接调用 gate 或直接调用 `telemetry.py complete`。

---

## 6. 常见错误码速查（连接阶段）

| 错误码 | 含义 | 排查 |
|--------|------|------|
| 10110 | 应用配置错误 | 检查 appId |
| 10113 | 认证失败 | 检查 apiKey/apiSecret、签名逻辑、date 是否 UTC GMT |
| 10120 | 形象未授权 | avatarId 未授权给该 appId，用 `list-assets` 探测 |
| 10121 | sceneId 未发布 | 控制台 publish 场景 |
| 11203 | 并发路数超限 | 上一会话未 destroy 就开新会话 |
| 600003 | 连测试地址 | serverUrl 未显式设置，用了 SDK 内置测试地址 |

---

## 7. 与其他 skill 的关系

- **上游**：`avatar-credentials`（Step 1）、`avatar-artifact-download`（Step 2）
- **模型/知识库**：如需自定义模型 + 知识库对话，先用 `avatar-model-config` + `avatar-knowledge-base`
  在平台侧配好并发布，前端只需 `writeText(text, { nlp: true })` 走 NLP。
- **排查**：连接/字段问题→本文件 §0/§3；其他运行时问题→`avatar-troubleshoot`
- **权威协议**：`avatar-webapi-protocol/references/protocols.md`（报文结构最终裁决源）
