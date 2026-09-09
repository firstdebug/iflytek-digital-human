# 高级特性与性能优化

## 高级特性

### 1. 自定义 NLP 响应

**服务端 Webhook**:
```javascript
// 接收 NLP 请求
app.post('/nlp-webhook', (req, res) => {
  const { text, context } = req.body;
  
  // 自定义 NLP 逻辑
  let answer = '';
  if (text.includes('价格')) {
    answer = queryPrice(context.product_id);
  } else if (text.includes('库存')) {
    answer = queryStock(context.product_id);
  } else {
    answer = callLLM(text);  // 调用大模型
  }
  
  res.json({ answer });
});
```

### 2. 意图识别后执行动作

```javascript
avatar.on(SDKEvents.nlp, (data) => {
  switch(data.intent) {
    case 'query_order':
      // 查询订单
      queryOrder(data.entities.order_id);
      break;
    case 'cancel_order':
      // 取消订单
      cancelOrder(data.entities.order_id);
      break;
    case 'contact_service':
      // 转人工客服
      transferToHuman();
      break;
  }
});
```

### 3. 情感分析

```javascript
avatar.on(SDKEvents.nlp, (data) => {
  if (data.emotion) {
    console.log('用户情绪:', data.emotion);
    // positive / negative / neutral
    
    if (data.emotion === 'negative') {
      // 用户不满，触发安抚话术
      showApologyMessage();
    }
  }
});
```

## 性能优化

### 1. 预加载常见问答

```javascript
// 本地缓存常见问题
const faqCache = {
  '营业时间': '我们的营业时间是早9点到晚10点',
  '联系方式': '客服电话400-xxx-xxxx'
};

async function askQuestion(text) {
  // 先查本地缓存
  if (faqCache[text]) {
    await avatar.writeText(faqCache[text], { nlp: false });
    return;
  }
  
  // 缓存未命中，调用 NLP
  await avatar.writeText(text, { nlp: true });
}
```

### 2. 流式播报 + 后台继续生成

```javascript
avatar.on(SDKEvents.nlp, (data) => {
  if (data.stream_nlp && data.index === 1) {
    // 首句到达，虚拟人开始播报
    console.log('首句延迟:', performance.now() - startTime);
  }
  
  // 后续分片持续到达和播报
  appendToConversation(data.answer);
});
```
