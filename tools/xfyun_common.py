"""
讯飞虚拟人 - 公共登录/会话模块
其他脚本 import 本模块获取已登录的 requests.Session
"""
import json
import os
import time
import webbrowser
import requests
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, BrowserContext
from platform_endpoints import LOGIN_URL, PROJECTS_URL, SUBSCRIBE_URL
import xfyun_secrets as xs  # 密钥安全模块

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
LOGIN_TIMEOUT = 300
REQUIRED_COOKIES = ["ssoSessionId", "account_id"]


def resolve_cookie_file(override: Optional[str] = None) -> Path:
    """解析 Cookie 文件路径，默认在插件根目录 .runtime/，可用环境变量覆盖。"""
    configured = override if override is not None else os.environ.get("XFYUN_AVATAR_COOKIE_FILE")
    if configured:
        expanded = os.path.expandvars(os.path.expanduser(configured))
        return Path(expanded).resolve()
    return PLUGIN_ROOT / ".runtime" / "xfyun_cookies.json"


COOKIE_FILE = resolve_cookie_file()


def save_cookies(cookie_dict: dict):
    """保存 Cookie 到本地文件，使用原子写入并设置权限。"""
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = COOKIE_FILE.with_name(f".{COOKIE_FILE.name}.tmp")
    temp_file.write_text(json.dumps(cookie_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_file.replace(COOKIE_FILE)
    try:
        COOKIE_FILE.chmod(0o600)
    except OSError:
        pass
    print(f"[OK] Cookie 已保存: {COOKIE_FILE}")


def load_cookies() -> Optional[dict]:
    if not COOKIE_FILE.exists():
        return None
    try:
        cookie_dict = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
        if all(name in cookie_dict for name in REQUIRED_COOKIES):
            print("[OK] 已加载本地 Cookie")
            return cookie_dict
    except Exception:
        pass
    return None


def build_session(cookie_dict: dict) -> requests.Session:
    """构建带 Cookie 的 requests 会话（域设为 .xfyun.cn）"""
    session = requests.Session()
    # 忽略机器上的 HTTP(S)_PROXY 环境变量，直连平台。
    # 否则系统代理会拦截 zs_web 接口，导致 auth_asset / interact_query 等间歇性
    # ProxyError('Unable to connect to proxy')。
    session.trust_env = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://www.xfyun.cn/"
    })
    for name, value in cookie_dict.items():
        session.cookies.set(name, value, domain=".xfyun.cn")
    # 把 uid（即 account_id）挂到 session 上，方便后续接口取用
    session.uid = cookie_dict.get("account_id", "")
    return session


def _wait_for_login(context: BrowserContext, timeout: int) -> Optional[dict]:
    print(f"[等待] 请在浏览器完成登录，超时 {timeout} 秒...")
    start = time.time()
    while time.time() - start < timeout:
        found = {}
        for c in context.cookies():
            if c["name"] in REQUIRED_COOKIES:
                found[c["name"]] = c["value"]
        if all(name in found for name in REQUIRED_COOKIES):
            print("[OK] 登录成功！")
            return found
        time.sleep(1)
    print("[错误] 登录超时")
    return None


def _do_browser_login() -> Optional[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        try:
            page = context.new_page()
            page.goto(LOGIN_URL)
            print("[浏览器] 已打开登录页面")
            return _wait_for_login(context, LOGIN_TIMEOUT)
        finally:
            time.sleep(1)
            browser.close()


def get_session(force_login: bool = False) -> Optional[requests.Session]:
    """获取已登录的 session。优先用本地 Cookie，失效或强制则重新登录。"""
    cookie_dict = None if force_login else load_cookies()
    if not cookie_dict:
        print("[启动] 需要登录，启动浏览器...")
        cookie_dict = _do_browser_login()
        if not cookie_dict:
            return None
        save_cookies(cookie_dict)
    return build_session(cookie_dict)


def post(session: requests.Session, url: str, payload: dict, debug: bool = False) -> Optional[dict]:
    """统一 POST 请求，返回解析后的 JSON dict；登录失效返回 None"""
    try:
        resp = session.post(url, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[错误] {url} HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if debug:
            print(f"\n[调试] {url} 返回:")
            # 自动脱敏敏感字段
            print(json.dumps(xs.mask_dict(data), ensure_ascii=False, indent=2))
        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {COOKIE_FILE} 后重新运行")
            return None
        return data
    except Exception as e:
        print(f"[错误] 请求 {url} 异常: {e}")
        return None


def get(session: requests.Session, url: str, params: dict = None, debug: bool = False) -> Optional[dict]:
    """统一 GET 请求"""
    try:
        resp = session.get(url, params=params or {}, timeout=15)
        if resp.status_code != 200:
            print(f"[错误] {url} HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if debug:
            print(f"\n[调试] {url} 返回:")
            # 自动脱敏敏感字段
            print(json.dumps(xs.mask_dict(data), ensure_ascii=False, indent=2))
        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {COOKIE_FILE} 后重新运行")
            return None
        return data
    except Exception as e:
        print(f"[错误] 请求 {url} 异常: {e}")
        return None


def put(session: requests.Session, url: str, payload: dict, debug: bool = False) -> Optional[dict]:
    """统一 PUT 请求"""
    try:
        resp = session.put(url, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f"[错误] {url} HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if debug:
            print(f"\n[调试] {url} 返回:")
            # 自动脱敏敏感字段
            print(json.dumps(xs.mask_dict(data), ensure_ascii=False, indent=2))
        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {COOKIE_FILE} 后重新运行")
            return None
        return data
    except Exception as e:
        print(f"[错误] 请求 {url} 异常: {e}")
        return None


def delete(session: requests.Session, url: str, debug: bool = False) -> Optional[dict]:
    """统一 DELETE 请求"""
    try:
        resp = session.delete(url, timeout=15)
        if resp.status_code != 200:
            print(f"[错误] {url} HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if debug:
            print(f"\n[调试] {url} 返回:")
            print(json.dumps(xs.mask_dict(data), ensure_ascii=False, indent=2))
        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {COOKIE_FILE} 后重新运行")
            return None
        return data
    except Exception as e:
        print(f"[错误] 请求 {url} 异常: {e}")
        return None


def check_app_capability(app, capability_type):
    """
    检查应用是否具备指定能力

    Args:
        app: 应用详情对象（包含 auths）
        capability_type: 'web_template' | 'live' | 'sdk'

    Returns:
        (bool, str): (是否具备, 消息)
    """
    auths = app.get('auths', [])
    app_type = app.get('appType')

    capability_requirements = {
        'web_template': {
            'appType': 2,
            'authKeys': ['WEB_CONVERSATION', 'PC_ASSISTANT'],
            'name': 'Web 对话模板',
            'display_name': 'Web 对话系统'
        },
        'live': {
            'appType': 2,
            'authKeys': ['DIGITAL_LIVE'],
            'name': '数字人直播',
            'display_name': '数字人直播'
        },
        'sdk': {
            'appType': 1,
            'authKeys': [],
            'name': 'SDK 集成',
            'display_name': '接口能力'
        }
    }

    req = capability_requirements.get(capability_type)
    if not req:
        return False, f"未知的能力类型: {capability_type}"

    # 检查 appType
    if app_type != req['appType']:
        return False, f"应用类型不匹配：需要 appType={req['appType']}（{req['name']}），当前为 {app_type}"

    # 检查授权
    missing_auths = []
    for auth_key in req['authKeys']:
        has_auth = any(
            auth.get('authKey') == auth_key
            and auth.get('licState') == 'valid'
            for auth in auths
        )
        if not has_auth:
            missing_auths.append(auth_key)

    if missing_auths:
        return False, f"缺少授权: {', '.join(missing_auths)}"

    return True, "权限检查通过"


def open_subscribe_page():
    """打开订阅页面（复用登录态）"""
    print(f"\n[跳转浏览器] 订阅页面")
    print(f"     {SUBSCRIBE_URL}")

    try:
        # 加载已保存的 Cookie
        cookies = load_cookies()
        if not cookies:
            print("[警告] 未找到登录 Cookie，浏览器打开后需要重新登录")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()

            # 注入 Cookie（免登录）
            if cookies:
                pw_cookies = []
                for name, value in cookies.items():
                    pw_cookies.append({
                        "name": name,
                        "value": value,
                        "domain": ".xfyun.cn",
                        "path": "/"
                    })
                context.add_cookies(pw_cookies)

            # 打开订阅页面
            page = context.new_page()
            page.goto(SUBSCRIBE_URL)

            print("[OK] 浏览器已打开，请在浏览器中完成订阅")
            print("提示：需要订阅【标准产品】，并在订阅时勾选对应的产品功能")
            input("\n完成订阅后，按 Enter 继续...")

            browser.close()

    except ImportError:
        print("[错误] 需要安装 playwright: pip install playwright")
        print(f"请手动访问: {SUBSCRIBE_URL}")
    except Exception as e:
        print(f"[错误] 打开浏览器失败: {e}")
        print(f"请手动访问: {SUBSCRIBE_URL}")


def open_projects_page():
    """Use the system browser to open the canonical virtual-man console."""
    print("\n[跳转浏览器] 虚拟人项目控制台")
    print(f"     {PROJECTS_URL}")
    if not webbrowser.open(PROJECTS_URL):
        print(f"[警告] 浏览器未自动打开，请访问: {PROJECTS_URL}")


def _cli(argv) -> int:
    """命令行入口。

    用法:
      python tools/xfyun_common.py [login]   # 拉起浏览器登录，保存到 <plugin-root>/.runtime/xfyun_cookies.json（默认）
      python tools/xfyun_common.py projects  # 打开虚拟人项目控制台
      python tools/xfyun_common.py subscribe # 打开订阅页面（复用登录态）

    Cookie 路径可用环境变量 XFYUN_AVATAR_COOKIE_FILE 覆盖为完整路径。
    """
    cmd = argv[1] if len(argv) > 1 else "login"

    if cmd in ("login", "-h", "--help") and cmd != "login":
        print(_cli.__doc__)
        return 0

    if cmd == "subscribe":
        open_subscribe_page()
        return 0

    if cmd == "projects":
        open_projects_page()
        return 0

    if cmd == "login":
        # 已有有效登录态则直接复用，避免重复弹浏览器
        force = "--force" in argv
        session = get_session(force_login=force)
        if session:
            print(f"[OK] 登录成功！凭据已保存到 {COOKIE_FILE}")
            return 0
        print("[错误] 登录失败或超时")
        return 1

    print(f"[错误] 未知命令: {cmd}")
    print(_cli.__doc__)
    return 2


if __name__ == "__main__":
    import sys
    sys.exit(_cli(sys.argv))

