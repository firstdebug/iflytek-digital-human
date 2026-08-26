# Step 1: 收集信息

## 1.1 必需信息

**基础信息**:
```yaml
platform: web | android | ios
sdk_version: "3.2.3"
error_code: "10113"  # 如果有
error_message: "apiSecret 错误"
```

**上下文信息**:
```yaml
sdk_status: not_integrated | partially_integrated | fully_integrated
last_working_version: "v1.2.0"  # 如果曾工作过
recent_changes: [...]  # 最近的代码变更
```

**症状描述**:
```yaml
symptom: "黑屏" | "无声音" | "连接失败" | "录音无反应"
when: "启动时" | "播报时" | "录音时"
frequency: "必现" | "偶现"
```

## 1.2 可选信息

**日志片段**:
```yaml
console_log: "..."
logcat: "..."  # Android
xcode_log: "..."  # iOS
```

**网络信息**:
```yaml
network_type: "wifi" | "4g" | "5g"
proxy_enabled: true | false
firewall: "..."
```

## 1.3 信息收集方法

```javascript
// 从当前用户请求、工程扫描和运行证据收集；不要在执行阶段重新访谈。
const info = {};

// 1. 错误码（如果有）
if (userMessage.includes('错误码') || /\d{5}/.test(userMessage)) {
  info.error_code = extractErrorCode(userMessage);
}

// 2. 平台
info.platform = detectPlatform() || contract.platform.value;

// 3. 症状
info.symptom = identifySymptom(userMessage) || contract.task.goal;

// 4. 日志（可选）
info.logs = readRedactedRuntimeEvidence() || null;

if (!info.platform || !info.symptom) {
  return { status: "blocked", reason: "契约或真实运行证据不足，回到 Grill 补充后重新确认" };
}

return info;
```
