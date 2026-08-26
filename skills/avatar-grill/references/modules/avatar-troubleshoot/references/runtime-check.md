# 完整的运行时检查函数

```javascript
async function runtimeCheck() {
    console.log('🔍 运行时检查...');
    const issues = [];

    // 1. 检查 bitrate 配置
    try {
        const params = avatar.getGlobalParams();
        if (params?.stream?.bitrate < 200) {
            issues.push({
                type: 'config', severity: 'critical',
                message: 'bitrate < 200', fix: '设置为 2000'
            });
        }
    } catch (e) {
        console.warn('无法获取全局参数');
    }

    // 2. 检查事件监听
    const requiredEvents = ['connected', 'error', 'disconnected', 'nlp'];
    for (const event of requiredEvents) {
        if (!avatar.listeners(event).length) {
            issues.push({
                type: 'event', severity: 'high',
                message: `缺少 ${event} 事件监听`, fix: '添加事件监听'
            });
        }
    }

    // 3. 检查 NLP 数据处理
    const nlpHandlers = avatar.listeners('nlp');
    if (nlpHandlers.length > 0) {
        const handler = nlpHandlers[0].toString();
        if (!handler.includes('answer') && !handler.includes('text')) {
            issues.push({
                type: 'nlp', severity: 'medium',
                message: 'NLP 处理可能不正确', fix: '检查 answer 字段提取'
            });
        }
    }

    return issues;
}
```

## 集成到 avatar-verification Layer 7

```yaml
Layer 7: 运行时验证
  Step 1: 启动开发服务器
  Step 2: 等待服务器就绪
  Step 3: 检查运行时错误
    → 检查 bitrate 配置
    → 检查 NLP 数据处理
    → 检查事件监听
  Step 4: 自动修复发现的问题
  Step 5: 重启服务器验证修复
```
