# 路由流程实现

三步路由流程的完整代码实现。

## Step 1: 快速扫描工程

```javascript
// 检测 SDK 集成状态
const sdkStatus = detectSDK();
// not_integrated | partially_integrated | fully_integrated

// 检测平台
const platform = detectPlatform();
// web | android | ios | unknown
```

## Step 2: 意图识别

```javascript
const intent = analyzeIntent(userRequest, sdkStatus, platform);

// 输出
{
  type: 'troubleshooting' | 'config_adjustment' | 'first_integration' | 
        'feature_extension' | 'docs_query' | 'permission_issue' | 'network_issue',
  confidence: 0.0 - 1.0,
  evidence: [...],
  suggested_route: 'avatar-troubleshoot'
}
```

## Step 3: 路由决策

```javascript
// 高置信度（> 0.8）直接路由
if (intent.confidence > 0.8) {
  console.log(`路由到: ${intent.suggested_route}`);
  return routeTo(intent.suggested_route, context);
}

// 中置信度（0.5 - 0.8）询问确认
if (intent.confidence > 0.5) {
  const confirmed = await askUserConfirm(intent);
  if (confirmed) {
    return routeTo(intent.suggested_route, context);
  } else {
    return fallbackToFullWorkflow();
  }
}

// 低置信度（< 0.5）使用完整工作流
return routeTo('avatar-brainstorming', context);
```
