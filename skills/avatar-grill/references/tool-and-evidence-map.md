# 工具与证据

## 1. 权威顺序

发生冲突时按以下顺序取值：

1. 当前实际 SDK 的类型声明、AAR、framework/header。
2. 当前平台工具的结构化查询结果。
3. 本仓库 `tools/platform_endpoints.py` 和 `config/platform-registry.yaml`。
4. 本 Skill 内置并经过验证的 Playbook。
5. 用户描述，仅用于需求与复现信息，不覆盖平台事实。

模型记忆不在权威来源中。

## 2. 事实查询表

| 事实 | 工具/证据 | 契约来源 |
|---|---|---|
| WS URL、控制台入口 | `tools/platform_endpoints.py` | `avatar-platform-constant` |
| 应用、appType、授权 | `xfyun_query_services.py list-apps` | `platform-query` |
| 场景、归属和 sceneType | `list-scenes`、`xfyun_interface.py query` | `platform-query` |
| 发布和对话能力 | `xfyun_model_manage.py check/query/query-interact` | `platform-query` |
| avatarId/vcn | `xfyun_interface.py auth-avatar` 或资产查询 | `platform-query` |
| 模型 | `xfyun_model_manage.py list/query` | `platform-query` |
| 知识库 | `xfyun_knowledge.py list/status/docs` | `platform-query` |
| SDK API | `index.d.ts`、AAR、framework/header | `sdk-inspection` |
| 工程平台和当前能力 | 文件和依赖扫描 | `project-scan` |
| 构建 | 构建命令退出码和产物 | `runtime-evidence` |
| Web 连接与首帧 | 浏览器自动化证据 | `runtime-evidence` |
| Android/iOS 首帧 | 真机日志与人工视觉确认 | `runtime-evidence` |

## 3. 工具失败

- 未登录：运行登录工具，浏览器打开后让用户只完成扫码或授权。
- 401/会话过期：清理的是当前工具自己的失效会话，不删除其他用户数据，然后重新登录。
- 网络错误：保留同一契约和任务状态，诊断 DNS/TLS/代理后重试。
- 平台返回空列表：不让用户猜 ID；说明账号下未查询到合适资源，询问是否允许创建或订阅。
- 写操作部分成功：先查询实际状态，再补齐缺失步骤；不得无条件重放整条创建链。

## 4. URL 门禁

允许模型展示或打开的控制台 URL 只能由 `platform_endpoints.py` 或平台工具返回。禁止：

- 根据旧页面记忆拼接路径。
- 把通用“我的应用”页面当虚拟人项目入口。
- 从错误信息里的相似域名推导 WS URL。

## 5. 证据新鲜度

完成证据必须晚于本次契约确认时间和影响运行结果的最后一次源码、配置或 SDK 变更。旧构建、旧浏览器日志和手写 JSON 不能作为本次完成证据。

