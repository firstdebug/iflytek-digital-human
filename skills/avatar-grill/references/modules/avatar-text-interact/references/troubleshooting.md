# 常见问题

## 1. NLP 回复不准确

**原因**:
- 大模型训练数据不足
- 问题描述不清晰
- 缺少上下文

**优化**:
```javascript
// 提供更多上下文
await avatar.writeText('它的价格是多少', {
  nlp: true,
  context: {
    last_query: '这款手机怎么样',  // 上一轮问题
    product_id: '12345'             // 当前浏览的商品
  }
});
```

## 2. NLP 回复延迟高

**原因**:
- 大模型推理耗时
- 网络延迟
- 非流式 NLP

**优化**:
```javascript
// 使用流式 NLP
await avatar.writeText(text, {
  nlp: true,
  stream_nlp: true  // 边生成边播报，降低首字延迟
});
```

## 3. 未开通大模型对话能力

**错误**: NLP 事件未触发或返回错误

**解决**:
1. 登录虚拟人交互平台
2. 进入控制台 → 接口服务
3. 开通"大模型对话能力"
4. 保存并发布

## 4. 多轮对话上下文丢失

**原因**: 未维护 session_id 或 history

**解决**:
```javascript
// 维护会话 ID
const sessionId = generateUUID();

// 每次请求都带上 session_id
await avatar.writeText(text, {
  nlp: true,
  context: { session_id: sessionId }
});
```
