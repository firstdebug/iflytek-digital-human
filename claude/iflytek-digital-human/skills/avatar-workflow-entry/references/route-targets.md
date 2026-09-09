# 路由目标说明

各路由目标的适用场景、输入、输出说明。

## 1. avatar-troubleshoot (故障排查)

**适用场景**:
- 虚拟人黑屏/无声音
- 错误码诊断
- 日志分析

**输入**:
```yaml
error_code: "10113"
error_message: "apiSecret 错误"
platform: "web"
logs: "..."
```

**输出**: 诊断结果 + 修复建议

---

## 2. avatar-config-authoring (配置调整)

**适用场景**:
- 修改分辨率、码率、帧率
- 更换形象或声音
- 调整播报速度、音量

**输入**:
```yaml
config_type: "resolution" | "avatar_resource" | "tts_params"
current_value: "720x1280"
target_value: "1080x1920"
```

**输出**: 配置文件修改 + 影响说明

---

## 3. avatar-brainstorming (完整工作流)

**适用场景**:
- 首次接入
- 功能扩展
- 复杂需求

**输入**:
```yaml
task_type: "first_integration" | "feature_extension"
platform: "web" | "android" | "ios"
user_requirements: "..."
```

**输出**: 设计文档 → 实现计划 → 代码实现

---

## 4. avatar-permissions-setup (权限配置)

**适用场景**:
- 麦克风权限拒绝
- 运行时权限申请
- Info.plist / AndroidManifest 配置

**输入**:
```yaml
platform: "android" | "ios" | "web"
permission_type: "microphone" | "camera"
error_info: "..."
```

**输出**: 权限配置代码 + 引导流程

---

## 5. avatar-network-debug (网络诊断)

**适用场景**:
- WebSocket 连接失败
- 流媒体不可达
- 网络超时

**输入**:
```yaml
error_code: "10200" | "10201"
network_info: "..."
```

**输出**: 网络诊断结果 + 修复建议

---

## 6. provide_docs (文档提供)

**适用场景**:
- 仅需查阅文档
- 无明确实施意图

**输出**: 相关文档链接 + 简要说明
