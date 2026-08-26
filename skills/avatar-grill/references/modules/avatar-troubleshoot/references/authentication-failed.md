# `avatar authentication failed` 确定性恢复流程

## 适用范围

命中以下任一信号时读取并执行本流程：

- SDK 返回 `avatar authentication failed`、`authorization invalid`；
- WebSocket 关闭码 `1008`；
- 平台返回 `10110`、`10113`、`10114`、`10120`、`10121`；
- 本地 `/api/avatar-auth` 正常，但 SDK 初始化后立即断开。

通用错误文案不是根因。不得仅凭 `avatar authentication failed` 宣称“场景未发布”或
“密钥错误”，也不得反复重试同一配置碰运气。必须取得下面至少一种区分性证据：

- 平台错误码及其同一响应中的错误说明；
- WebSocket 关闭码和 reason；
- 平台接口返回的 app、scene、发布状态或资源授权关系；
- canonical 签名校验的具体失败项。

错误码含义以本次平台响应的说明为准。不同 SDK/平台版本的编号可能有差异，不要只按历史表格猜测。

## 安全和权限边界

- 不读取、打印或要求用户粘贴完整 `apiKey`、`apiSecret`、Cookie、authorization 或 signed URL。
- 禁止通过终端读取或回显整个 `.env`；凭据只能由平台脚本直接写入项目文件。
- 不手写 WebSocket 或控制台 URL。Web SDK 固定端点和控制台跳转由插件工具持有。
- 查询 app/scene/授权状态属于只读诊断，可直接执行。
- `create`、`publish`、`auth-avatar` 会修改平台资源。只有用户已要求修复且该变更处于任务范围内时执行；
  否则先说明即将修改的 app/scene 和动作，等待确认。
- 只管理 `web_delivery.py` 为当前项目记录的 Node PID，不结束全部 Node 进程。

## 阶段 A：保留真实错误证据

记录平台、SDK 版本、复现时间和原始错误码/说明。Web 项目还应记录浏览器控制台中的 SDK 错误、
WebSocket close code/reason，以及失败发生在以下哪个阶段：

1. `/api/config` 或 `/api/avatar-auth` HTTP 失败；
2. WebSocket 未握手；
3. 握手后立即断开；
4. 已 `connected`，但 start/首帧失败。

没有 code/reason 时明确标记 `generic_auth_error`，继续阶段 B；不要补造错误码。

## 阶段 B：验证本地 canonical 鉴权链路

Web SDK 项目统一执行状态机，不允许另写签名代码：

```bash
python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" status --project "<project>"
python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" run --project "<project>" --interaction "<text|voice|audio>" --no-browser
```

检查结果必须满足：

- `WS_URL` 为插件固定端点；
- `xfyun-auth.mjs` 与 `.runtime/websocket-auth.json` 哈希一致；
- `/api/config` 与项目凭据指纹一致；
- `/api/avatar-auth` 每次生成新 signed URL；
- date 为当前 UTC GMT，签名包含 `host`、`date`、`GET /v1/interact HTTP/1.1`。

状态机返回签名、配置或服务生命周期问题时，先修该确定问题，再进入平台资源检查。
本地 canonical 校验通过仅表示签名结构自洽，不能证明平台接受当前 app/scene/资产组合。

## 阶段 C：查询平台真实资源关系

所有命令从插件根目录执行。先确保登录，再做只读查询：

```bash
python tools/xfyun_common.py login
python tools/xfyun_query_services.py list-apps
python tools/xfyun_query_services.py list-scenes
python tools/xfyun_model_manage.py scenes
python tools/xfyun_model_manage.py check <sceneId>
python tools/xfyun_model_manage.py query-interact <sceneId>
```

根据结构化输出逐项确认，不能从旧导出文件推断：

- app 存在，且 `appType=1`，适用于 SDK/WebAPI；
- scene 出现在当前账号的接口场景列表中；
- scene 返回的 `appId` 与目标 app 完全一致；
- scene 已发布且仍有效；
- 当前 app 具有任务所需能力；
- 项目所用 avatarId 和 vcn 已授权给该 app。

若平台查询和本地 `.env` 指向不同 app/scene，平台实时查询为准。不要把能查询到 NLP 草稿当成场景可连接
或已发布的证据。

## 阶段 D：按已确认根因修复

每次只修已被证据确认的一项，修后重新查询验证。

### D1. 本地凭据不是平台当前配对值

用平台返回的精确 appId/sceneId 重新写入，不手工复制密钥：

```bash
python tools/write_env_safe.py <appId> <sceneId> "<project>/.env" --profile web-sdk
```

### D2. scene 存在但未发布

```bash
python tools/xfyun_model_manage.py publish <sceneId>
python tools/xfyun_model_manage.py scenes
```

只有发布命令成功且重新查询可见，才能进入复验。不得把“已执行 publish 命令”当成发布成功。

### D3. scene 不存在、归属错误或不是接口场景

不要继续复用旧 sceneId。创建新的 `sceneType=1` 接口场景；工具会配置 NLP、交互并发布：

```bash
python tools/xfyun_interface.py create <appId> <sceneName> --desc <description> --welcome <welcome>
python tools/xfyun_interface.py list
```

取得新 sceneId 后，用 `write_env_safe.py` 或 `web_delivery.py --refresh-credentials` 回写项目。

### D4. avatarId 或 vcn 未授权

优先让工具探测当前账号实际可授权资产，不复用历史硬编码 ID：

```bash
python tools/xfyun_interface.py auth-avatar <appId>
```

若用户明确指定资产，可带 `--anchor` 或 `--vcn`。授权成功后使用工具实际返回的 avatarId/vcn 更新项目。

### D5. 签名被平台拒绝

当平台响应明确指向 authorization/signature/date 时：

1. 校准系统时间和时区；
2. 重新运行 `web_delivery.py`，确保每次连接生成新 signed URL；
3. 恢复 canonical `xfyun-auth.mjs`，删除项目中重复的 HMAC 实现；
4. 若 canonical 自检通过仍被拒绝，重新从平台获取同一 app 的完整密钥对，不混用不同 app 的 Key/Secret。

### D6. 并发、额度、订阅或平台状态阻塞

只关闭本工作流已知连接。额度耗尽、订阅缺失、账号冻结或平台异常不能通过改代码解决，输出平台返回的
脱敏证据和所需用户/平台动作，保持门禁未完成。

## 阶段 E：真实复验与停止条件

修复后回到同一个项目执行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/tools/web_delivery.py" run --project "<project>" --interaction "<text|voice|audio>"
```

成功必须同时有本轮新鲜的浏览器证据：

- `connected=true`；
- `stream_start=true`；
- `first_frame=true`；
- 目标交互通过；
- `errors=[]`；
- 状态机最终返回 `ready_to_deliver=true`。

以下均不算修复成功：HTTP 200、签名 URL 能生成、WebSocket 101、场景查询有数据、构建成功、执行过
publish/auth 命令。任何一项真实证据缺失，都保持 `needs_runtime_verification` 或对应 blocked 状态，禁止
调用 telemetry complete。

连续两次复验得到相同的平台明确拒绝且本地与平台资源检查均通过时停止重试，保留 request time、错误码、
close reason 和脱敏资源关系，交由平台支持处理。
