# 常见应用场景

## 场景 1: 智能客服

```javascript
// 问题库配置（服务端）
const qaBase = {
  '退货流程': '您可以在订单详情页申请退货...',
  '配送时间': '一般3-5个工作日送达...',
  '售后电话': '客服热线400-xxx-xxxx'
};

// 前端调用
await avatar.writeText('我想退货', { nlp: true });

avatar.on(SDKEvents.nlp, (data) => {
  console.log('回复:', data.answer);
  // 回复: "您可以在订单详情页申请退货..."
});
```

## 场景 2: 知识问答

```javascript
// 知识库接入（大模型）
await avatar.writeText('人工智能是什么？', { 
  nlp: true,
  stream_nlp: true
});

avatar.on(SDKEvents.nlp, (data) => {
  // 流式接收 NLP 回复
  displayNLPAnswer(data.answer);
});
```

## 场景 3: 闲聊对话

```javascript
// 闲聊模式
await avatar.writeText('今天天气真好', { 
  nlp: true,
  context: { mode: 'chitchat' }
});

// NLP 可能回复: "是啊，阳光明媚，适合出门游玩"
```

## 场景 4: 任务型对话

```javascript
// 任务导向（如预约、查询）
await avatar.writeText('帮我预约明天下午2点的会议室', {
  nlp: true,
  context: { mode: 'task' }
});

// NLP 识别意图并执行任务
avatar.on(SDKEvents.nlp, (data) => {
  if (data.intent === 'book_meeting_room') {
    // 调用预约 API
    bookMeetingRoom(data.entities);
  }
});
```
