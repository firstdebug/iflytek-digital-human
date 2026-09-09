# 用户接入流程——每一步在做什么

本文档帮你理解"从零到跑通虚拟人应用"的完整流程,避免不知道当前在干什么、为什么要这么做。

## 流程全景(5 步)

```
订阅产品 → 登录平台 → 检查应用授权 → 选择接入方式 → 开始集成
  ↓          ↓          ↓               ↓              ↓
 平台操作   credentials  自动判断      路由决策      对应skill
```

---

## 第 1 步:订阅产品(平台操作,一次性)

**在做什么**:在虚拟人交互平台申请应用,获得使用资格。

**为什么做**:虚拟人服务需要授权和资源配额,必须先订阅产品才能调用接口或创建应用。

### 操作步骤

1. 访问[虚拟人交互平台](https://virtual-man.xfyun.cn/)
2. 注册/登录账号
3. 进入"项目中心"或"我的订阅",点击"申请订阅"
4. **关键选择**:根据你的需求选产品类型

| 你要做什么                   | 应该订阅     | appType | 必选授权（产品类型） |
| ----------------------- | -------- | ------- | ---------- |
| Web 对话模板、H5、智能客服        | **标准产品** | 2       | Web对话系统    |
| 数字人直播平台                 | **标准产品** | 2       | 数字人直播      |
| SDK 开发(Web/Android/iOS) | **接口能力** | 1       | 无(基础接口)    |
| WebAPI 报文接入(后端直连)       | **接口能力** | 1       | 无(基础接口)    |

5. **可选授权**:
   
   - 需要大模型对话(知识库问答/智能客服)→ 勾选”大模型对话”开关
   - 标准产品想用数字人直播 → 勾选数字人直播产品类型

6. 提交订阅,等待生效(这个生效需要我们公司人员做审核，想快点得打电话咨询)

**易错点**:

- ❌ 想做 Web 模板却订阅了接口能力 → 无法创建模板(接口能力只能调 API)
- ❌ 想用大模型对话,但订阅时忘记打开大模型对话开关 → 后续对话功能报错 10107

---

## 第 2 步:登录平台获取凭据(avatar-credentials)

**在做什么**:用你的平台账号登录,获取调用接口必需的 appId / apiKey / apiSecret / sceneId。

**为什么做**:虚拟人接口需要鉴权,这些凭据是身份标识和签名密钥。

### 触发方式

当我检测到需要凭据时(你说要集成、或任务需要 appId),会自动调用 `avatar-credentials` skill:

1. 调用 `xfyun_login.py`,打开浏览器让你登录
2. 登录成功后,凭据保存到本地文件 `xfyun_cookies.json`(已在 `.gitignore`,不会进 git)
3. 从文件读取 appId/apiKey/apiSecret

**你要做什么**:在弹出的浏览器里输入平台账号密码,登录即可。登录一次,凭据持久化,下次不用重复。

---

## 第 3 步:检查应用授权(自动,在 avatar-credentials 里)

**在做什么**:登录后立即调用 `POST https://virtual-man.xfyun.cn/zs_web/app/query`,获取你订阅的应用列表,并判断:

- 有没有应用(列表是否为空)
- 应用类型(标准产品 / 接口能力)
- 是否有效(isEffect: true/false,false 表示已过期)
- 授权情况(是否打开大模型对话开关、web对话模板、数字人直播等功能)

**为什么做**:避免后续集成到一半才发现授权不足、应用类型不对,或者根本没订阅应用。

### 三种判断结果

#### 情况 1:没有任何应用(列表为空)

**提示**:"检测到你还没有订阅虚拟人产品。你想做什么?"

- 选项 A:Web 对话模板 / 数字人直播 → 推荐订阅**标准产品**,记得勾选对应授权
- 选项 B:SDK 开发 / WebAPI 接入 → 推荐订阅**接口能力**
- 给订阅链接:[订阅页面](https://virtual-man.xfyun.cn/console/applications/subscribe)

**你要做什么**:去平台订阅产品(回到第 1 步),订阅后回来重新运行。

#### 情况 2:有应用,但授权不足

常见场景:

- 订阅了接口能力,但没打开大模型对话开关,现在想用大模型对话 → 缺大模型对话授权
- 订阅了标准产品,但没勾选数字人直播,现在想做直播 → 缺数字人直播授权

**提示**:"你的应用缺少 XXX 授权,无法使用 YYY 功能。需要重新创建一个应用,订阅时记得勾选 XXX。"

- 给订阅链接,让你去创建新应用

**你要做什么**:去平台创建新应用,这次记得勾选缺的授权。旧应用不影响,可以保留。

#### 情况 3:应用正常,授权齐全

**提示**:"✅ 应用检查通过,appId=xxx,授权包含 [大模型对话 / web对话模板 / ...]"

- 存储 appId/apiKey/apiSecret/sceneId
- 进入下一步(选择接入方式)

---

## 第 4 步:选择接入方式(路由决策)

**在做什么**:根据你的需求(关键词、工程状态)判断该走哪个 skill。

**为什么做**:虚拟人有多种接入方式(模板/SDK/WebAPI),自动路由到最合适的。

### 四大场景

| 你说的关键词                                | 判断为       | 路由到 skill                         |
| ------------------------------------- | --------- | --------------------------------- |
| "Web 模板"、"智能客服"、"H5 对话"、"大屏"          | Web 对话模板  | `avatar-web-template`             |
| "直播"、"虚拟主播"、"带货"、"分镜"                 | 数字人直播     | `avatar-live-streaming`           |
| "SDK"、"集成"、"web/android/ios"          | SDK 开发    | `avatar-brainstorming` → SDK 集成流程 |
| "WebAPI"、"报文"、"不用 SDK"、"直连 WebSocket" | WebAPI 接入 | `avatar-webapi-protocol`          |

路由逻辑在 `avatar-workflow-entry` skill。

---

## 第 5 步:开始集成(进入对应 skill)

根据第 4 步路由结果,进入具体 skill 的工作流:

### 5A. Web 模板 / 数字人直播(零代码)

直接生成可部署的应用代码,配置平台参数即可,无需写代码。

### 5B. SDK 开发(编程接入)

工程文件骨架可以先按 `avatar-executing` 的平台 Playbook 创建；凭据和 SDK 是启动真实链路的门禁，
不是创建空骨架的门禁。Web 场景下先创建 `server.js` 等最小文件，再运行 `web_delivery.py run`。
`web_delivery.py` 不生成工程文件：缺少 `server.js` 时会先返回
`blocked_server_lifecycle` / `server_js_missing`。

1. **环境检查**(`avatar-preflight`):Node/npm 版本、防火墙、依赖安装
2. **下载 SDK**(`avatar-artifact-download`):自动下载对应平台 SDK
3. **工具链验证**(`toolchain`):检查构建工具(Vite/Webpack/Gradle/Xcode)
4. **集成指南**(`integration-guides`):按平台给代码模板
5. **功能集成**:
   - 文本驱动(`text-driver`)
   - 语音交互(`voice-interact`)
   - 全双工(`full-duplex`)
   - 动作控制(`action-control`)
   - 透明背景(`transparent-bg`)
   - ...
6. **调试排障**(`avatar-troubleshoot`):遇到错误时定位原因

### 5C. WebAPI 报文接入(后端直连)

1. **鉴权 URL 生成**:HMAC-SHA256 签名(Python/JS/Java)
2. **构造请求报文**:9 个协议的 JSON 模板 + 字段约束
3. **搭建 demo**:连接 → start → 驱动 → 打印收发 → ping → stop
4. **解读响应**:event_type 判断、vmr_status 播报状态、错误码定位

详细流程见各 skill 的 SKILL.md。

---

## 常见疑问

**Q1:为什么要先订阅产品,不能直接开始?**
A:虚拟人服务涉及算力资源(TTS/ASR/大模型/渲染),平台需要知道你有授权、配额够不够。订阅是获得使用资格的唯一方式。

**Q2:订阅后为什么还要登录?**
A:订阅是在平台网页操作,我(AI)拿不到你的凭据。登录是为了自动获取 appId/apiKey/apiSecret,避免你手动复制粘贴。

**Q3:检查应用授权这步能跳过吗?**
A:不建议。如果跳过,可能集成到一半才发现授权不足(比如调 NLP 接口报 10107),要回头重订阅,浪费时间。提前检查能避免返工。

**Q4:我已经有 appId 了,能不能直接给你,不登录?**
A:可以。如果你不想登录,可以直接告诉我 appId/apiKey/apiSecret/sceneId,我会跳过登录和应用检查,直接进入集成。但这样我无法自动判断你的授权情况。

**Q5:授权不足时,能不能"追加订阅",还是必须重新创建?**
A:平台目前不支持对已有应用追加授权。需要创建一个新应用,订阅时勾选缺的授权。旧应用不影响,可以保留或删除。

**Q6:标准产品和接口能力能同时订阅吗?**
A:可以。一个账号可以订阅多个应用,类型可以不同。比如你可以同时有一个接口能力(用于 SDK 开发)和一个标准产品(用于 Web 对话模板)。

---

## 流程图(文字版)

```
用户提出虚拟人需求
    ↓
我调用 avatar-workflow-entry 识别意图
    ↓
需要凭据? → 是 → 调用 avatar-credentials
    ↓              ↓
    否          1. 调 xfyun_login.py 登录
    ↓           2. POST /app/query 检查应用
    ↓           3. 判断 appType / auths / isEffect
    ↓              ↓
    ↓           无应用? → 问需求 → 推荐订阅哪种产品 → 给链接 → [等用户订阅后回来]
    ↓           授权不足? → 提示缺什么 → 给链接让重新创建 → [等用户订阅后回来]
    ↓           ✓ 正常
    ↓              ↓
    ←──────────────┘
    ↓
路由决策(avatar-workflow-entry)
    ↓
    ├→ Web 模板 / 直播 → avatar-web-template / avatar-live-streaming
    ├→ SDK 开发 → avatar-brainstorming → preflight → artifact-download → toolchain → integration-guides → 功能集成
    ├→ WebAPI 接入 → avatar-webapi-protocol → auth → protocols → demo-build → responses
    └→ 故障排查 → avatar-troubleshoot
```

---

> 本文档解释"为什么要这么做"。具体操作流程见各 skill 的 SKILL.md 和 references。
