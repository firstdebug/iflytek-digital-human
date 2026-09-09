# 进阶配置

## 1. 配置 NLP 参数

```javascript
// Web
await avatar.writeText('北京的天气怎么样', {
  nlp: true,
  stream_nlp: true,  // 流式 NLP（边理解边播报）
  context: {         // 上下文参数（可选）
    user_id: 'user123',
    session_id: 'session456'
  }
});

// Android
TextParams params = new TextParams();
params.setNlp(true);
params.setStreamNlp(true);  // 流式 NLP
params.setContext("{\"user_id\":\"user123\"}");  // 上下文 JSON
controller.writeText("北京的天气怎么样", params);

// iOS
TextParams *params = [TextParams new];
params.nlp = YES;
params.streamNlp = YES;
params.context = @"{\"user_id\":\"user123\"}";
[controller writeText:@"北京的天气怎么样" textParams:params];
```

## 2. 流式 NLP vs 非流式 NLP

**非流式 NLP**:
```
用户输入 → NLP完整理解 → 生成完整回复 → 虚拟人播报
延迟: 2-5 秒
```

**流式 NLP**:
```
用户输入 → NLP逐句理解 → 逐句生成回复 → 虚拟人逐句播报
延迟: 1-2 秒（首句）
体验: 更流畅，像真人对话
```

**推荐**: 使用流式 NLP (`stream_nlp: true`)

## 3. 多轮对话上下文管理

```javascript
// Web - 维护对话上下文
class ConversationManager {
  constructor() {
    this.sessionId = generateUUID();
    this.history = [];
  }
  
  async sendMessage(text) {
    // 添加到历史
    this.history.push({ role: 'user', content: text });
    
    // 发送带上下文的请求
    await avatar.writeText(text, {
      nlp: true,
      stream_nlp: true,
      context: {
        session_id: this.sessionId,
        history: this.history.slice(-10)  // 最近 10 轮对话
      }
    });
  }
  
  onNLPReply(answer) {
    // 添加回复到历史
    this.history.push({ role: 'assistant', content: answer });
  }
}

// 使用
const manager = new ConversationManager();
await manager.sendMessage('你好');
await manager.sendMessage('刚才我说了什么？');  // 带上下文
```

## NLP 回复数据结构

### Web / Android / iOS 通用格式

```json
{
  "answer": "我是虚拟数字人小助手，很高兴为您服务",
  "answerText": "我是虚拟数字人小助手，很高兴为您服务",
  "intent": "self_introduction",
  "confidence": 0.95,
  "sid": "cht000xxxxx",
  "cid": "cht000xxxxx@dx19f410xxxxx",
  "stream_nlp": true,
  "index": 1
}
```

**字段说明**:
- `answer`: NLP 生成的回复文本（虚拟人会播报此内容）
- `answerText`: 同 answer
- `intent`: 识别的意图（如 self_introduction）
- `confidence`: 置信度 (0-1)
- `sid`: 会话 ID
- `cid`: 对话 ID
- `stream_nlp`: 是否为流式 NLP
- `index`: 流式 NLP 分片索引
