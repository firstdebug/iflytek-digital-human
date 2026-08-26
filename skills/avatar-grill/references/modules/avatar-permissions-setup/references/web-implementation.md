# Web 平台权限实现

## 平台权限要求

**要求**: HTTPS 或 localhost 环境

**权限类型**:
```yaml
麦克风权限:
  API: navigator.mediaDevices.getUserMedia({ audio: true })
  环境要求: HTTPS 或 localhost
  触发时机: 用户首次使用录音功能
  
摄像头权限（可选）:
  API: navigator.mediaDevices.getUserMedia({ video: true })
  用途: 视频通话等场景
```

**检查方法**:
```javascript
// 1. 检查浏览器支持
if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
  console.error('浏览器不支持 MediaDevices API');
  return { supported: false, fix: '升级浏览器到最新版本' };
}

// 2. 检查 HTTPS 环境
const isSecure = location.protocol === 'https:' || 
                 location.hostname === 'localhost' || 
                 location.hostname === '127.0.0.1';

if (!isSecure) {
  return { 
    secure: false, 
    fix: '录音功能需要 HTTPS 或 localhost 环境' 
  };
}

// 3. 检查权限状态（仅 Chrome/Edge）
if (navigator.permissions) {
  const permission = await navigator.permissions.query({ name: 'microphone' });
  console.log('麦克风权限:', permission.state);
  // state: "granted" | "denied" | "prompt"
}

return { supported: true, secure: true };
```

## 监听权限变化（Web）

```javascript
// Chrome/Edge 支持
navigator.permissions.query({ name: 'microphone' })
  .then(permission => {
    permission.onchange = () => {
      console.log('麦克风权限变化:', permission.state);
      if (permission.state === 'denied') {
        stopRecording();
        showPermissionDeniedMessage();
      }
    };
  });
```

## 问题诊断: 浏览器提示"不安全"无法使用麦克风

**原因**: HTTP 环境

**解决**:
1. 配置本地 HTTPS 开发环境
2. 或使用 localhost 域名

**验证**:
```javascript
console.log('协议:', location.protocol);
console.log('主机名:', location.hostname);

if (location.protocol !== 'https:' && 
    location.hostname !== 'localhost' && 
    location.hostname !== '127.0.0.1') {
  console.error('录音需要 HTTPS 或 localhost');
}
```
