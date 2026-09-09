# 问题 2: NLP 回复显示 [object Object]

**错误表现**:
```
用户: "你是谁"
虚拟人: 回复: [object Object]
```

**根本原因**:
1. `data.answer` 是对象而不是字符串
2. 直接拼接对象到字符串导致 `[object Object]`

**诊断步骤**:
```javascript
avatar.on(SDKEvents.nlp, (data) => {
    console.log('🤖 NLP 原始数据:', data);
    console.log('🤖 数据结构:', JSON.stringify(data, null, 2));
});
```

**数据结构示例**（实际验证）:

NLP 回复的 `answer` 是一个对象，正确内容在 `displayContent` 字段：
```json
{
  "answer": {
    "displayContent": "我是虚拟数字人，很高兴为您服务",
    "text": "..."
  }
}
```

**字段提取优先级**:
```
1. data.displayContent          (顶层)
2. data.answer.displayContent   (嵌套，最常见)
3. data.answer.text
4. data.answer (字符串)
5. data.text
```

**解决方案**（已验证）:
```javascript
// avatar-service.js 中
avatar.on(SDKEvents.nlp, (data) => {
    let answer;
    if (data?.displayContent) {
        answer = data.displayContent;
    } else if (data?.answer?.displayContent) {
        answer = data.answer.displayContent;   // ⭐ 最常见
    } else if (data?.answer?.text) {
        answer = data.answer.text;
    } else if (typeof data?.answer === 'string') {
        answer = data.answer;
    } else if (data?.text) {
        answer = data.text;
    } else {
        answer = JSON.stringify(data);
    }
    this.emit('nlp', { answer: answer, raw: data });
});
```

---

# 问题 5: 流式 NLP 每帧都新建消息框

**错误表现**:
```
虚拟人: 回复: 你好！我是讯飞星火大模型，
虚拟人: 回复: 你好！我是讯飞星火大模型，由科大讯飞自主研发，
虚拟人: 回复: 你好！我是讯飞星火大模型，由科大讯飞自主研发，致力于...
```
同一句话产生多个消息框。

**根本原因**:
流式 NLP 每次推送的是**累积内容**（不是增量），前端每收到一帧就 `addMessage` 新建框。

**解决方案**（累积更新同一个框）:
```javascript
// 全局：当前 NLP 回复的消息框引用
let currentNlpMessage = null;

// addMessage 返回元素引用
function addMessage(text, sender = 'avatar') {
    const message = document.createElement('div');
    message.className = `message ${sender}`;
    message.innerHTML = `
        <div class="message-label">${sender === 'user' ? '用户' : '虚拟人'}</div>
        <div class="message-content">${text}</div>
    `;
    elements.conversation.appendChild(message);
    return message;  // ⭐ 返回引用
}

function updateMessageContent(messageEl, text) {
    const contentEl = messageEl.querySelector('.message-content');
    if (contentEl) contentEl.textContent = text;
}

// NLP 事件：复用同一个框
avatarService.on('nlp', (data) => {
    const answer = data?.answer || '';
    if (currentNlpMessage) {
        updateMessageContent(currentNlpMessage, answer);  // ⭐ 更新
    } else {
        currentNlpMessage = addMessage(answer, 'avatar');  // 首帧新建
    }
});

// 每次新提问时重置引用
async function sendText() {
    currentNlpMessage = null;  // ⭐ 重置，下一轮用新框
    await avatarService.writeText(text, true);
}
```

**关键点**:
1. 流式内容是**累积的**，直接替换即可（不用拼接）
2. `addMessage` 返回元素引用
3. 首帧新建框，后续帧更新同一框
4. 每轮新提问前重置 `currentNlpMessage = null`
