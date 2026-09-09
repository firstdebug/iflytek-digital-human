# 问题 1: bitrate 参数验证失败

**错误信息**:
```
ConnectError: '$.parameter.avatar.stream.bitrate' value must be larger or equal than 200
```

**出现场景**: SDK 初始化时 / WebSocket 连接建立时

**根本原因（反编译 SDK v3.2.3.1002 确认）**:

SDK 内部在组装 start 报文时，对**顶层** `stream.bitrate` 执行了 **`Math.floor(bitrate/1024)`**：
```js
// SDK index.js 内部逻辑（简化）
v = globalConfig.stream.bitrate ?? 1000000
parameter.avatar.stream.bitrate = Math.floor(v / 1024)
```
所以最常见的真实原因是：
1. **你在顶层 `stream.bitrate` 写了 `2000`，SDK 发送 `floor(2000/1024)=1`** → 触发 ≥200 校验失败（**头号坑**）
2. `bitrate` 参数类型错误（字符串 vs 数字）
3. 真的把 bitrate 设成了 <200 的小值

> ⚠️ 报错路径是 `avatar.stream.bitrate`，容易误以为"漏了 avatar.stream 字段"。
> 实际上 `avatar.stream` 是 SDK **自动组装**的，问题出在**顶层 bitrate 被 /1024**。
> 干净的规避办法：**显式手写 `avatar.stream`**（值原样发送、不再 /1024，见解决方案）。

**诊断步骤**:
```javascript
// 打印实际会发送的值：顶层 bitrate / 1024
const top = 2000;
console.log('顶层 bitrate=%d → SDK 实际发送=%d', top, Math.floor(top/1024)); // → 1，会报错
```

**解决方案**:
```javascript
// 完整配置（关键：avatar.stream 必须包含 protocol/fps/bitrate/alpha）
this.avatar.setGlobalParams({
    stream: {
        protocol: 'xrtc',
        fps: 25,
        bitrate: 2000  // 必须 >= 200，推荐 2000
    },
    avatar: {
        avatar_id: config.avatarId,
        width: 720,
        height: 1280,
        stream: {
            protocol: 'xrtc',  // 必填
            fps: 25,           // 必填
            bitrate: 2000,     // 必填，>= 200
            alpha: 0           // 必填，0=不透明 1=透明
        }
    },
    tts: {
        vcn: config.vcn,
        speed: 50,
        pitch: 50,
        volume: 50
    }
});
```

**为什么这样写能对**：`avatar.stream` 是 SDK 自动组装的字段，但你在 `avatar` 里手写 `stream` 时，
它会通过 SDK 内部的 `Object.assign` **覆盖**掉自动计算结果——此时你写的 `bitrate:2000` **原样发送、不再 /1024**，
所以平台收到的就是 2000（合法）。这就是"所见即所发"，避开了顶层 bitrate 的 /1024 陷阱。

> 完整的 Web SDK 自建工程标准流程（含字段锁定表）见
> `avatar-executing/references/web-sdk-build-playbook.md`。

**自动修复代码**:
```javascript
function fixBitrateConfig(filePath) {
    let content = fs.readFileSync(filePath, 'utf-8');
    content = content.replace(
        /bitrate:\s*(\d+|'[^']*'|"[^"]*")/g,
        (match, value) => {
            const cleanValue = value.replace(/['"]/g, '');
            const bitrate = parseInt(cleanValue);
            if (isNaN(bitrate) || bitrate < 200) {
                console.log(`⚠️  修复 bitrate: ${value} → 2000`);
                return 'bitrate: 2000';
            }
            return match;
        }
    );
    fs.writeFileSync(filePath, content);
    return true;
}
```

---

# 问题 3: SDK 路径加载失败

**错误信息**:
```
SDK 加载失败: Failed to fetch dynamically imported module
```

**根本原因**: SDK 路径不正确 / ESM 路径错误 / Vite 配置问题

**解决方案**:
```javascript
// SDK 实际路径（注意 esm 子目录）
const sdkPath = '/sdk/avatar-sdk-web_3.2.3.1002/esm/index.js';
// 动态导入加 @vite-ignore 注释
const { default: AvatarPlatform } = await import(/* @vite-ignore */ sdkPath);
```

---

# 问题 4: 浏览器自动播放限制

**错误表现**: 虚拟人有视频但无声音，控制台显示 `playNotAllowed`

**解决方案**:
```javascript
player.on(PlayerEvents.playNotAllowed, () => {
    console.warn('⚠️  浏览器阻止自动播放');
    alert('请点击页面任意位置以开始播放');
    document.addEventListener('click', () => {
        player.resume();
        console.log('▶️  已恢复播放');
    }, { once: true });
});
```
