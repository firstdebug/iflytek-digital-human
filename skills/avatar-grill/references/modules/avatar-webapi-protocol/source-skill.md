> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。


# avatar-webapi-protocol: WebAPI 报文接入

## 定位

帮用户用 **WebAPI 方式**(不依赖任何客户端 SDK)对接讯飞虚拟人:自己写 WebSocket 连接、
手工拼 JSON 请求报文、解析 JSON 响应报文。核心目标是**搭出一个能跑通、能直观看到每一条
请求/响应报文的 demo**,并据此校验报文、解读响应状态。

**与客户端 SDK 接入的本质区别**:

| | SDK 接入（文本/语音驱动等） | WebAPI |
|---|---|---|
| 接入 | 调 SDK 方法 `writeText()` | 手拼 JSON + WebSocket 收发 |
| 关注 | 播放器/录音器/SDK API | 报文字段、event_type、错误码 |
| 鉴权 | SDK 内部处理 | 自己做 HMAC-SHA256 拼 URL |

> Web 页面渲染和官方客户端 SDK 集成不使用本报文方案；本资料只覆盖 WebAPI 报文层接入与判断。

## 凭据前置检查（HARD-GATE：必须先完成）

WebAPI 报文接入需要 **6 项完整凭据**，且所有参数必须是该场景已授权的：

| 凭据项 | 说明 | 常见错误 |
|--------|------|----------|
| `app_id` | 应用 ID（8位） | 10108 session is invalid |
| `api_key` | API 密钥（32位） | 10113 签名错误 |
| `api_secret` | API 密钥对 | 10113 签名错误 |
| `scene_id` | 场景 ID（必须已发布） | 10121 未发布 |
| `avatar_id` | 形象 ID（**必须该场景已授权**） | 10120 / 20016 未授权 |
| `vcn` | 发音人 ID（**必须该场景已授权**） | 10163 为空 / 20016 未授权 |

### 凭据获取优先级

**推荐方式**：通过平台工具获取
```bash
cd "${CLAUDE_PLUGIN_ROOT}"
python tools/xfyun_query_services.py  # 查询场景列表
python tools/write_env_safe.py <app_id> <scene_id> <output_path>
# 工具会自动设置默认形象（111310001）和发音人（x4_lingxiaoqi_oral）
```

**凭据恢复方式**：使用根目录平台工具完成登录、查询和安全写入；形象与发音人必须来自实际资产查询或授权结果。

### 参数验证清单（发送 start 之前必查）

- [ ] `app_id` / `api_key` / `api_secret` / `scene_id` 非空
- [ ] `avatar_id` 和 `vcn` 非空（工具会自动设置默认值）
- [ ] 如果报 20016 错误，检查场景授权列表

不得使用账号无关的默认形象或发音人 ID；每次以平台工具返回的授权资产为准。

## 适用范围

- 用户明确说"用 WebAPI / 不用 SDK / 直连 WebSocket / 手写报文"对接虚拟人
- 用户想搭一个能打印/查看请求响应报文的 demo
- 用户拿着一段请求或响应 JSON,问"这样对不对 / 这个响应什么意思 / 报了什么错"
- 用户要生成鉴权 URL、构造某个协议的请求报文

## 核心工作流(以"搭出可看报文的 demo"为目标)

```
1. 明确接入语言与目标协议(默认 Python;至少 start + text_driver 跑通)
2. 生成鉴权 URL(HMAC-SHA256)          → 见 references/auth.md
3. 构造请求报文(按协议填字段)          → 见 references/protocols.md
4. 建最小 demo:连接→start→驱动→收发打印→ping→stop → 见 references/demo-build.md
5. 解读每条响应,判断会话状态/播报进度/错误 → 见 references/responses.md
```

## 决策分支(场景 → 应读哪个 reference)

| 场景 | 应读 reference |
|------|----------------|
| 凭据不全或参数错误(10163/20016) | `references/troubleshooting.md` 快速定位 |
| 生成/校验 HMAC-SHA256 鉴权 URL(Python/JS/Java) | `references/auth.md` |
| 构造某协议请求报文、校验请求字段是否合规 | `references/protocols.md` |
| 解读响应报文、判断 event_type/vmr_status/会话状态 | `references/responses.md` |
| 搭一个能跑通并打印收发报文的最小 demo | `references/demo-build.md` |

**执行顺序（HARD-GATE）**：
1. **凭据前置检查** → 确保 6 项参数齐全且已授权（见本页"凭据前置检查"章节）
2. **demo 构建** → 按 `demo-build.md` 搭建可运行代码
3. **报文调试** → 出错时查 `troubleshooting.md` 快速定位
4. **协议扩展** → 跑通后参考 `protocols.md` 添加其他协议

---

## 关键约束 / Red Flags

### 会话时序(硬性)
- 连接建立后**第一个**发送的必须是 `start`,否则报 10108 session is invalid
- 一个会话只能发一次 `start`
- start 之后必须**每 5 秒**发一次 `ping` 保活,否则 10104 over time(60 秒无任何消息即断开)
- 单会话同时只能 1 个驱动在执行;发下一条驱动前,等当前驱动 `vmr_status=2`
- 优雅关闭:发 `stop` → 等 stop 响应 → 关 WebSocket(断连务必 stop,否则占用授权路数)

### 报文字段(高频错)
- ctrl 每个协议用**各自独立值**(start/text_driver/text_interact/audio_driver/audio_interact/cmd/reset/ping/stop)
- `app_id`/`request_id`/`ctrl` 全协议必带;`scene_id` 仅 start 需要
- `stream.bitrate` 范围 200-20000,不能 <200
- `width`/`height` 必须是 4 的倍数,否则 20009
- 音频类 payload 为 PCM 16kHz/16bit/单声道,base64 编码
- 文本 `content` 不超过 2000 字符,不能传空(10106)

### 文档已知错误(照抄会踩雷)
- `avatar_ready`、`avatar_end` 是**不存在的幽灵事件**——start 成功看 `stream_info`/`stream_start`,播报结束看 `vmr_status=2`
- 文档多处 JSON 示例畸形(`"audio_mode":1,0` 等注释混入值)——产出的报文必须是合法 JSON
- ctrl 值每个协议用**各自独立值**(start/text_driver/text_interact/audio_driver/audio_interact/cmd/reset/ping/stop)

### 安全
- `apiSecret` 绝不硬编码进前端、不落入进版本库的文件;签名建议在服务端完成
- 鉴权 URL 一次生成会话期持续有效;响应中不含签名

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/auth.md` | HMAC-SHA256 鉴权 URL 生成(Python/JS/Java 三语言 + 6 步拆解) |
| `references/protocols.md` | 9 个协议的请求报文模板 + 字段约束表(构造/校验请求用) |
| `references/responses.md` | 响应结构 + event_type 全表 + 会话状态判断逻辑(解读响应用) |
| `references/demo-build.md` | Python 最小可运行 demo:连接→start→驱动→打印收发→ping→stop + 跨平台兼容 |
| `references/troubleshooting.md` | 实战错误码排查(10163/20016/10113 等)+ 快速定位方案 + 凭据来源决策树 |

