# 字幕样式定制

## 1. 基础样式

```css
/* 黑底白字（经典） */
.subtitle-basic {
  background: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 8px 16px;
  border-radius: 4px;
}

/* 白底黑字（明亮） */
.subtitle-light {
  background: rgba(255, 255, 255, 0.9);
  color: #333;
  padding: 8px 16px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

/* 描边字（视频风格） */
.subtitle-stroke {
  color: white;
  text-shadow: 
    -1px -1px 0 #000,
     1px -1px 0 #000,
    -1px  1px 0 #000,
     1px  1px 0 #000;
  font-weight: bold;
  font-size: 24px;
}
```

## 2. 动画效果

```css
/* 淡入淡出 */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.subtitle-text {
  animation: fadeIn 0.3s ease-out;
}

/* 打字机效果 */
@keyframes typing {
  from { width: 0; }
  to { width: 100%; }
}

.subtitle-typing {
  overflow: hidden;
  white-space: nowrap;
  animation: typing 2s steps(20);
}
```
