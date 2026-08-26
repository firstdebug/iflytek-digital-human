# 配置项参数参考

各配置项的合法取值、修改位置、平台差异。平台能力以 `config/platform-registry.yaml` 为准。

---

## 分辨率 (resolution)

**修改位置**: SDK 初始化参数（web/android/ios 均为 avatar 启动配置的 width/height）。

**常用值**:
| 值 | 说明 |
|----|------|
| 720x1280 | 竖屏标清，移动端默认 |
| 1080x1920 | 竖屏高清 |
| 1280x720 | 横屏标清 |
| 1920x1080 | 横屏高清 |

**约束**: 分辨率越高，所需 bitrate 越高。移动端高分辨率注意性能与流量。
以 `platform-registry.yaml` 中各平台 `system_requirements` 为准。

---

## 码率 / 帧率 (stream_params)

**修改位置**: SDK 初始化 `bitrate` / `framerate`。

**约束（HARD）**:
- `bitrate` **必须 ≥ 200**（数字类型），推荐 **2000**。低于 200 报错
  `value must be larger or equal than 200`。
- `framerate` 常用 25。

详见 `avatar-troubleshoot/references/bitrate-and-sdk.md`。

---

## 形象 / 发音人 (avatar_resource)

**修改位置**: `avatarId`（形象）/ `vcn`（发音人），一般在 `.env` 或 SDK 参数。

**约束（HARD）**:
- 只能使用**已授权**的 avatarId/vcn，未授权连接报 **10120**。
- 用 `query-services` 工具或参考 `avatar-credentials` 确认当前账号授权范围。
- 超拟人形象（`cnr` 开头）**不支持透明背景**。

**修改示例（.env）**:
```env
VITE_AVATAR_ID=<已授权的形象ID>
VITE_VCN=<已授权的发音人>
```

---

## TTS 参数 (tts_params)

**修改位置**: 文本驱动 / 语音交互的 TTS 配置。

| 参数 | 常用范围 | 说明 |
|------|---------|------|
| speed | 0-100（默认 50） | 播报速度 |
| volume | 0-100（默认 50） | 音量 |
| pitch | 0-100（默认 50） | 音调 |

详见 `text-driver` / `voice-interact`。

---

## 背景 (background)

**修改位置**: 背景图 URL 或透明背景开关。

**约束**: 透明背景需 **xrtc 协议** 且形象**非超拟人**（cnr 开头不支持）。
详见 `transparent-bg`。
