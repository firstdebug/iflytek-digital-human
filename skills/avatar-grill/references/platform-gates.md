# 平台门禁

## 1. 共通门禁

- 契约有效且用户已确认需要的写操作。
- appId/sceneId 配对、资源授权和发布状态在线验证通过。
- 密钥未进入前端、源码、日志、契约或版本库。
- 使用实际 SDK API，没有命中已知虚构调用。
- 构建或语法检查通过。
- 启动、连接、首帧和目标交互有本轮证据。
- 错误、断线、打断和资源释放路径存在。

## 2. Web SDK

唯一编排命令：

```bash
python tools/web_delivery.py run \
  --project "<project>" --app-id "<appId>" --scene-id "<sceneId>" \
  --interaction "<text|voice|audio>"
```

- 退出码 0：`ready_to_deliver`，可以交付。
- 退出码 2：静态或生命周期阻断。读取 JSON 的 `next_action`，修复后重复同一命令。
- 退出码 3：缺运行时证据。完成浏览器验证后重复同一命令。

不得直接运行最终 reporter 改写状态，不得手写运行证据，不得全局结束所有 Node 进程。只处理工具返回的当前项目进程和端口。

## 3. Android

- AAR 完整、ABI 正确、XRTC 依赖齐全。
- Manifest 只包含本需求需要的权限。
- 使用实际 SDK 中存在的初始化、控制器、播放器和监听接口。
- 同一工程同一时间只有一个 Gradle 调用。
- 在线依赖预热成功后执行离线复验。
- 超时先检查原 Gradle/daemon 状态，不立即重复启动。
- 构建成功只证明工程可编译；首帧和交互必须在真机或目标设备验证。

## 4. iOS

- Framework 架构和 Embed & Sign 正确。
- Bundle ID、Team、系统库和最低系统版本满足要求。
- 语音启用时存在权限说明并验证授权拒绝路径。
- Xcode 构建、安装、连接、首帧和目标交互分别留证。

## 5. Web 模板、直播、模型和知识库

写操作完成后必须用查询命令验证：

- 对象 ID 存在且属于契约中的应用。
- 配置字段与契约一致。
- 需要发布的变更已经发布。
- 访问链接由平台工具返回，不由模型拼接。
- 知识库文档处理完成，调用链和模型 nlpType 匹配。

将产物写入 `.runtime/artifacts.json`，只包含 ID、平台返回链接、类型和验证时间，不包含密钥。

## 6. 故障修复

修复完成至少满足：

- 原错误可以稳定复现或有足够原始证据。
- 修复后同一复现步骤不再出现原错误。
- 目标主链路通过。
- 相关回归项通过。
- 如果根因是外部能力、账号授权或客户端解码器限制，明确记录为外部阻塞，不伪装成代码完成。

## 7. 完成文件

SDK 工程的 `.runtime/verification-result.json` 最少包含：

```json
{
  "ready_to_deliver": true,
  "source": "deterministic-gate",
  "verified_at": "2026-08-26T00:00:00Z",
  "checks": {
    "build": true,
    "connected": true,
    "first_frame": true,
    "target_interaction": true,
    "secret_scan": true
  },
  "remaining_issues": []
}
```

存在剩余阻断时 `ready_to_deliver` 必须为 false。普通失败仍允许同一任务修复和产生新证据；只有确定无法继续时才加入 `terminal_failure: true`。

