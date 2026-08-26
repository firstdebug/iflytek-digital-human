# 最小可运行 Demo（Python）

目标：跑通一次完整会话，**在控制台直观打印每一条请求和响应报文**，让用户看清 WebAPI 交互全过程。
流程：连接 → start → 文本驱动 → 打印收发 → ping 保活 → 等播报结束 → stop。

## 前置

- Python 3.8+，装依赖：`pip install websocket-client`
- 准备好 app_id / api_key / api_secret / scene_id / avatar_id / vcn（见 avatar-credentials skill）
- **重要**：avatar_id 和 vcn 必须是该场景已授权的，否则报 20016 错误
- 鉴权函数 `build_auth_url` 见 `auth.md`（下面 demo 内联了一份）

> 安全：不要把 api_secret 硬编码提交进 git。demo 用环境变量或本地 .env（.env 需进 .gitignore）。

## 跨平台兼容注意事项

### Windows 控制台编码问题

**问题**：Windows 控制台默认 GBK，打印 emoji（✓ ❌ 🔐）会崩溃：
```
UnicodeEncodeError: 'gbk' codec can't encode character '❌'
```

**解决**：在代码开头强制 UTF-8 输出
```python
import sys
import io

# Windows 控制台 UTF-8 支持
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
```

### .env 文件自动加载

**问题**：每次执行 shell 命令环境变量不保留，手动 `export` 麻烦且不安全

**解决**：demo 自动从 `~/.env` 加载凭据
```python
from pathlib import Path

def load_env():
    """从 .env 文件加载环境变量"""
    env_path = Path.home() / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

load_env()  # 在读取环境变量之前调用
```

**`.env` 格式示例**：
```bash
# 讯飞虚拟人 WebAPI 凭据
XF_APP_ID=YOUR_APP_ID
XF_API_KEY=<完整32位密钥>
XF_API_SECRET=<完整32位密钥>
XF_SCENE_ID=336130030977552384
XF_AVATAR_ID=138805001
XF_VCN=x4_lingxiaoqi_oral
```

**安全**：`.env` 必须加入 `.gitignore`，避免密钥泄露

### 导入顺序

```python
"""
讯飞虚拟人 WebAPI 报文接入 Demo
"""
import sys
import io
import base64, hashlib, hmac, json, os, threading, time, uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
from pathlib import Path
import websocket  # pip install websocket-client

# 1. Windows UTF-8 支持（必须在最前面）
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 2. 加载 .env（必须在读取 os.environ 之前）
def load_env():
    env_path = Path.home() / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip())

load_env()

# 3. 读取配置
WS_URL = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"
APP_ID = os.environ.get("XF_APP_ID", "")
API_KEY = os.environ.get("XF_API_KEY", "")
API_SECRET = os.environ.get("XF_API_SECRET", "")
SCENE_ID = os.environ.get("XF_SCENE_ID", "")
AVATAR_ID = os.environ.get("XF_AVATAR_ID", "111310001")  # 默认形象
VCN = os.environ.get("XF_VCN", "x4_lingxiaoqi_oral")  # 默认发音人
```

## 完整 demo 代码

```python
import base64, hashlib, hmac, json, os, threading, time, uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse
import websocket  # pip install websocket-client

WS_URL = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"
APP_ID     = os.environ["XF_APP_ID"]
API_KEY    = os.environ["XF_API_KEY"]
API_SECRET = os.environ["XF_API_SECRET"]
SCENE_ID   = os.environ["XF_SCENE_ID"]
AVATAR_ID = os.environ.get("XF_AVATAR_ID", "111310001")  # 默认形象
VCN = os.environ.get("XF_VCN", "x4_lingxiaoqi_oral")  # 默认发音人

def build_auth_url(ws_url, api_key, api_secret):
    parsed = urlparse(ws_url)
    host = parsed.hostname
    if parsed.port and parsed.port not in (80, 443):
        host = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature = base64.b64encode(
        hmac.new(api_secret.encode(), origin.encode(), hashlib.sha256).digest()).decode()
    authorization = (f'api_key="{api_key}", algorithm="hmac-sha256", '
                     f'headers="host date request-line", signature="{signature}"')
    auth_base64 = base64.b64encode(authorization.encode()).decode()
    params = {"authorization": auth_base64, "date": date, "host": host}
    return f"{ws_url}?{urlencode(params)}"

def rid():
    return str(uuid.uuid4())

def send(ws, obj, label):
    print(f"\n>>> 发送 [{label}] >>>")
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    ws.send(json.dumps(obj))
```

## 请求报文构造

```python
def start_req():
    return {
        "header": {"app_id": APP_ID, "request_id": rid(),
                   "ctrl": "start", "scene_id": SCENE_ID},
        "parameter": {"avatar": {
            "stream": {"protocol": "xrtc", "fps": 25, "bitrate": 2000, "alpha": 0},
            "avatar_id": AVATAR_ID, "width": 720, "height": 1280},
            "tts": {"vcn": VCN, "speed": 50, "pitch": 50, "volume": 50}},
        "payload": {}}

def text_driver_req(text):
    return {
        "header": {"app_id": APP_ID, "request_id": rid(), "ctrl": "text_driver"},
        "parameter": {"avatar_dispatch": {"interactive_mode": 1}},
        "payload": {"text": {"content": text}}}

def ping_req():
    return {"header": {"app_id": APP_ID, "request_id": rid(), "ctrl": "ping"}}

def stop_req():
    return {"header": {"app_id": APP_ID, "request_id": rid(), "ctrl": "stop"}}
```

## 回调 + 主流程

```python
driver_done = threading.Event()

def on_message(ws, message):
    msg = json.loads(message)
    print("\n<<< 收到响应 <<<")
    print(json.dumps(msg, ensure_ascii=False, indent=2))
    header = msg.get("header", {})
    avatar = msg.get("payload", {}).get("avatar", {})
    et = avatar.get("event_type")
    # 错误判断
    if header.get("code", 0) != 0 or avatar.get("error_code", 0) != 0:
        print(f"[!] 异常 code={header.get('code')} "
              f"err={avatar.get('error_code')} {avatar.get('error_message')}")
    # 关键事件解读
    if et in ("stream_info", "stream_start"):
        print("[√] 推流就绪 / 会话启动成功")
    elif et == "driver_status":
        vmr = avatar.get("vmr_status")
        print(f"[i] 驱动状态 vmr_status={vmr}（0开始/1中间/2结束）")
        if vmr == 2:
            driver_done.set()   # 播报结束信号
    elif et == "pong":
        print("[i] 心跳 pong")
    elif et == "stop":
        print("[√] 会话已停止")

def on_error(ws, error):
    print(f"[!] WebSocket 错误: {error}")

def on_close(ws, code, reason):
    print(f"[i] 连接关闭 code={code} reason={reason}")

def on_open(ws):
    def run():
        send(ws, start_req(), "start")
        time.sleep(2)                          # 等 start 就绪
        send(ws, text_driver_req("你好，我是通过 WebAPI 驱动的数字人"), "text_driver")
        # 保活：驱动期间每 5 秒 ping 一次
        for _ in range(12):
            if driver_done.wait(timeout=5):
                break
            send(ws, ping_req(), "ping")
        time.sleep(1)                          # 确认 vmr_status=2 后无新驱动
        send(ws, stop_req(), "stop")
        time.sleep(1)
        ws.close()
    threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    url = build_auth_url(WS_URL, API_KEY, API_SECRET)
    ws = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message,
                                on_error=on_error, on_close=on_close)
    ws.run_forever()
```

## 运行

```bash
export XF_APP_ID=... XF_API_KEY=... XF_API_SECRET=... XF_SCENE_ID=...
python avatar_webapi_demo.py
```

控制台会交替打印 `>>> 发送` 与 `<<< 收到响应`，可清楚看到：
start → stream_info/stream_start → text_driver → audit_result → tts_duration →
driver_status(vmr=0) → driver_status(vmr=2) → stop。

## 想扩展时

- 换协议：把 `text_driver_req` 换成 `protocols.md` 里其它协议的模板（text_interact/audio_driver/cmd 等）
- 看视频流：本 demo 只看报文；要在 web 页面渲染 xrtc 视频流是另一回事（走播放器/SDK，不在本 skill）
- 逐条解读收到的响应：见 `responses.md` 的事件表与状态判断逻辑

