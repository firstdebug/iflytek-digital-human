# 客户端字幕渲染

自行根据播报文本渲染，样式完全自定义，兼容透明背景和 3D 形象。

## 基础字幕组件（Web）

```html
<!-- 字幕容器 -->
<div class="subtitle-container">
  <div class="subtitle-text"></div>
</div>

<style>
.subtitle-container {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 80%;
  text-align: center;
}

.subtitle-text {
  background: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 10px 20px;
  border-radius: 8px;
  font-size: 18px;
  line-height: 1.5;
}
</style>

<script>
function displaySubtitle(text) {
  const container = document.querySelector('.subtitle-text');
  container.textContent = text;
  container.style.display = 'block';
  
  // 3秒后自动隐藏
  setTimeout(() => {
    container.style.display = 'none';
  }, 3000);
}
</script>
```

## 逐字高亮字幕

```javascript
// Web - 根据 word_list 实现逐字高亮
function displayWordByWord(subtitleData) {
  const container = document.querySelector('.subtitle-text');
  container.innerHTML = '';
  
  // 渲染所有字
  subtitleData.word_list.forEach((word, index) => {
    const span = document.createElement('span');
    span.textContent = word.word;
    span.className = 'word';
    container.appendChild(span);
  });
  
  // 逐字高亮
  subtitleData.word_list.forEach((word, index) => {
    setTimeout(() => {
      container.children[index].classList.add('highlight');
    }, word.begin_time);
  });
}
```

```css
.word {
  color: white;
  transition: color 0.1s;
}

.word.highlight {
  color: #FFD700;  /* 金色高亮 */
  font-weight: bold;
}
```

## 多语言字幕（同时显示中英文）

```javascript
// 假设服务返回双语字幕
avatar.on(SDKEvents.subtitle_info, (data) => {
  displayBilingualSubtitle(data.text_zh, data.text_en);
});

function displayBilingualSubtitle(zh, en) {
  const container = document.querySelector('.subtitle-container');
  container.innerHTML = `
    <div class="subtitle-zh">${zh}</div>
    <div class="subtitle-en">${en}</div>
  `;
}
```

```css
.subtitle-zh {
  font-size: 20px;
  font-weight: bold;
}

.subtitle-en {
  font-size: 16px;
  color: #CCC;
  margin-top: 5px;
}
```
