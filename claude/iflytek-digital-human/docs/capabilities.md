# 功能清单——我能帮你做什么

当你问"有哪些功能"、"能做什么"时,这里是完整回答。

## 一、创建标准应用(零代码快速搭建)

基于虚拟人交互平台的产品模板,快速搭建标准应用,无需写代码:

**1. Web 对话模板**(`avatar-web-template` skill)

- 场景:智能客服、H5 对话页、大屏交互展示
- 能力:文本交互、语音交互、知识库问答、动作控制
- 产物:生成可预览的跳转页面(如 `https://virtual-man.xfyun.cn/interact_web/common/screen/...`),可直接嵌入到你的前端应用或分享给用户访问

**2. 数字人直播平台**(`avatar-live-streaming` skill)

- 场景:虚拟主播带货、直播间互动、商品讲解
- 能力:分镜脚本编排、商品列表配置、实时互动
- 产物:生成可预览的直播页面链接(同上格式),可嵌入到直播间或单独部署

---

## 二、基于 SDK 构建自定义应用(编程接入)

提供三端 SDK,适合有开发能力、需要深度定制的场景:

**Web SDK**(`text-driver` / `voice-interact` / `full-duplex` 等 skill)

- 适用:浏览器端集成、H5 页面、桌面 Web 应用
- 能力:文本/语音驱动、NLP 交互、全双工、动作控制、透明背景、字幕

**Android SDK**(`toolchain` skill + Android 分支)

- 适用:原生 Android 应用
- 能力:与 Web SDK 相同的完整交互能力,适配移动端

**iOS SDK**(`toolchain` skill + iOS 分支)

- 适用:原生 iOS 应用
- 能力:与 Web SDK 相同,适配 iOS 生态

**SDK 获取**:我会在 `avatar-preflight` 或 `avatar-artifact-download` 阶段自动下载对应平台的 SDK,你无需手动下载。

---

## 三、Web API 报文接入(后端直连,无 SDK)

不使用任何 SDK,直接用后端语言(Python/Java/Node)通过 WebSocket 对接虚拟人接口:

**avatar-webapi-protocol** skill

- 适用:后端服务、API 网关、需要完全自主控制报文的场景
- 能力:手工构造 JSON 请求报文、解析 JSON 响应报文、判断会话状态
- 核心产物:可运行的 demo(打印每条请求/响应),用于理解协议、调试报文
- WebSocket 地址:`wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`

包含:鉴权(HMAC-SHA256,三语言)、9 个协议请求模板、event_type 全表、状态判断逻辑。

---

## 四、其他核心能力

### 接入准备与配置

- **avatar-credentials**:登录平台、获取凭据、检查应用授权
- **avatar-preflight**:环境门禁(Node/npm/防火墙/依赖),开工前一次性检查
- **avatar-config-authoring**:配置调整(分辨率/码率/形象/背景/音色)
- **toolchain**:工具链检查(按平台分 web/android/ios)

### 故障排查与调试

- **avatar-troubleshoot**:错误码定位、运行时案例库、常见问题排查
- **avatar-permissions-setup**:浏览器权限配置(麦克风/摄像头/自动播放)
- **avatar-network-debug**:网络诊断(WSS 连通性/DNS/防火墙)

### 交互能力 skill(SDK 客户端)

- **文本驱动**(`text-driver`):发送文本让数字人播报
- **文本交互**(`text-interact`):大模型对话(带知识库/函数调用)
- **音频驱动**(`audio-driver`):发送音频让数字人播报
- **语音交互**(`voice-interact`):ASR 识别 + NLP 对话 + TTS 播报
- **全双工**(`full-duplex`):实时打断、流式识别
- **动作控制**(`action-control`):触发预设动作(挥手/点头等)
- **字幕配置**(`subtitle-setup`):同步字幕显示
- **透明背景**(`transparent-bg`):抠像、叠加到自定义背景

### 平台管理(xfyun-tools)

- **avatar-model-config**:绑定/切换大模型(星火/GPT/Claude)
- **avatar-knowledge-base**:创建/上传/管理知识库文档
- **avatar-scene-management**:查询场景状态、发布接口服务

### 开发辅助

- **integration-guides**:分平台集成指南(Web/Android/iOS)
- **avatar-artifact-download**:自动下载 SDK 和资源

---

> 本文档是"你能做什么"的快速索引。具体任务进入对应 skill,由 `avatar-workflow-entry` 自动路由。
