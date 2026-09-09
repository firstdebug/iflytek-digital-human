# Step 3: 症状匹配

## 3.1 症状库

**从 references/error-codes.yaml 加载 scenarios**:
```javascript
const scenarios = errorDB.scenarios;

function matchScenario(symptom, platform) {
  for (const [name, scenario] of Object.entries(scenarios)) {
    // 检查症状关键词
    if (scenario.symptoms.some(s => symptom.includes(s))) {
      return {
        name,
        ...scenario,
        platform_filtered: filterByPlatform(scenario.possible_errors, platform)
      };
    }
  }
  
  return null;
}
```

## 3.2 症状匹配示例

**示例 1: 黑屏症状**
```yaml
symptom: "黑屏"
matched_scenario: "no_video"

症状匹配:
  - 黑屏
  - 视频区域空白
  - 页面正常但没有虚拟人

可能错误:
  - 20002: 播放器创建失败
  - 700002: 设备不支持 H.264
  - 700003: 渲染超时
  - 10120: avatarId 未授权

诊断步骤:
  1. 检查控制台是否有错误日志
  2. 确认收到 stream_start 事件
  3. 检查播放器是否创建成功
  4. 检查 avatarId 是否授权
```

**执行诊断步骤**:
```javascript
async function diagnoseNoVideo(info) {
  const steps = [];
  
  // Step 1: 检查错误日志
  if (info.logs) {
    const errorCode = extractErrorCode(info.logs);
    if (errorCode) {
      steps.push(`发现错误码: ${errorCode}`);
      const error = lookupError(errorCode);
      return { root_cause: error, steps };
    }
  }
  
  // Step 2: 检查 stream_start 事件
  steps.push("请确认控制台是否收到 stream_start 事件");
  const hasStreamStart = await askUser("是否收到 stream_start 事件？");
  
  if (!hasStreamStart) {
    steps.push("未收到 stream_start → 连接或推流问题");
    return {
      root_cause: "服务端未推流",
      likely_errors: ["10120", "10121"],  // 资源未授权
      steps
    };
  }
  
  // Step 3: 检查播放器创建
  steps.push("stream_start 已收到，检查播放器");
  
  if (info.platform === 'web') {
    steps.push("Web 平台: 检查播放器分包是否加载");
    return {
      root_cause: "播放器创建失败",
      likely_error: "20002",
      fix: "确认 xrtc-player-*.js 与 SDK 在同一目录",
      steps
    };
  }
  
  if (info.platform === 'android') {
    steps.push("Android 平台: 检查 XRTC SDK 是否引入");
    return {
      root_cause: "播放器依赖缺失",
      likely_error: "20002",
      fix: "确认 app/libs/ 下有 xrtcsdk-*.aar",
      steps
    };
  }
  
  // ... 继续其他检查
}
```
