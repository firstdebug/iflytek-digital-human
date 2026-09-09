#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞虚拟人 - 接口（SDK/WebAPI）对话应用管理工具

按 scene -> nlp -> interact -> publish 四步流程，创建"接口"类型
（sceneType=1）的虚拟人对话应用，用于 SDK/WebAPI 集成（非 Web 模板 / 直播）。

命令总览
  只读查询
    list                                列出账号下的接口对话场景
    query <sceneId>                     查询场景 NLP 配置

  创建接口应用（写）
    create <appId> <name> [选项]        4 步创建接口对话应用（并探测授权形象/发音人）

  资产授权（写）
    auth-avatar <appId> [--anchor ID] [--vcn V]
                                        探测并授权可用形象+发音人，打印 SDK 可直接用的 avatarId/vcn

  create 选项
    --desc D            场景描述（默认同名称）
    --domain D          星火模型 domain（默认 generalv3.5）
    --temperature T     采样温度（默认 0.5）
    --max-tokens N      最大 token（默认 4000）
    --history N         历史轮数（默认 20）
    --welcome MSG       欢迎语（默认空）
    --bos N             前端点超时 ms（默认 500）
    --eos N             后端点超时 ms（默认 500）
    --iat-type N        识别语言 1=中文 10002=英文（默认 1）
    --no-browser        不自动打开浏览器
    --no-auth-avatar    跳过创建后的形象/发音人授权探测

说明
  - 接口类型 sceneType=1，templateId 为空（区别于 Web 模板 sceneType=2 / 直播 sceneType=6）
  - 接口应用通过 appId 的 apiKey/apiSecret 走 SDK/WebAPI 调用，无 Web 访问链接
  - NLP 默认使用星火大模型（nlpType=xinghuo），可用 --domain 指定 domain
  - 接口场景【不含形象/发音人】：SDK 端必须在 AvatarParams 里传 avatarId+vcn，且这两个资产
    要先授权给 appId（create 会自动探测授权，或用 auth-avatar 单独处理），否则 SDK 连上即断
  - SDK 必须显式 setServerUrl("wss://avatar.cn-huadong-1.xf-yun.com/v1/interact")，
    否则走 AAR 内置测试地址，握手报 600003 "Expected HTTP 101 response but was 200"
"""
import sys

# Windows 下强制 stdout/stderr 使用 UTF-8，避免中文输出乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import json
import xfyun_common as xc

# ==================== API 端点 ====================
API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"
API_SCENE_UPSERT = "https://virtual-man.xfyun.cn/zs_web/scene/createOrUpdate"
API_NLP_UPSERT = "https://virtual-man.xfyun.cn/zs_web/nlp/createOrUpdate"
API_INTERACT_UPSERT = "https://virtual-man.xfyun.cn/zs_web/interact/createOrUpdate"
API_SCENE_PUBLISH = "https://virtual-man.xfyun.cn/zs_web/scene/publish"
API_SCENE_QUERY = "https://virtual-man.xfyun.cn/zs_web/scene/query"
API_NLP_QUERY = "https://virtual-man.xfyun.cn/zs_web/nlp/query"
API_AUTH_ASSET = "https://virtual-man.xfyun.cn/zs_web/app/auth_asset"

# 资产类型 / 场景
ASSET_TYPE_ANCHOR = 1   # 形象
ASSET_TYPE_VCN = 3      # 发音人
ASSET_SCENE_COMMON = 1  # 通用（SDK/接口）

# 候选形象/发音人（用于授权探测，取第一个授权成功的）。
# 注意：可授权资产因账号而异，这里只是探测候选，绝不硬编码为“默认必用值”。
CANDIDATE_ANCHORS = ["118801001", "110117026", "110026010", "118801002"]
CANDIDATE_VCNS = ["x4_lingxiaoqi_oral", "x4_yezi", "x4_mingge", "x4_yiting"]

# SDK/WebAPI 生产接入地址（三端一致；不设会走 AAR 内置测试地址导致 600003）
SERVER_URL = "wss://avatar.cn-huadong-1.xf-yun.com/v1/interact"

# 场景类型：接口（SDK/WebAPI）对话
SCENE_TYPE_INTERFACE = 1

# 控制台配置页面（接口类型）
CONFIG_URL_TPL = "https://virtual-man.xfyun.cn/console/projects/config/{app_id}/{scene_id}/view"

# ==================== 默认配置常量 ====================
DEFAULT_NLP_TYPE = "xinghuo"
DEFAULT_DOMAIN = "generalv3.5"
DEFAULT_TEMPERATURE = 0.5
DEFAULT_MAX_TOKENS = 4000
DEFAULT_HISTORY_TIMES = 20
DEFAULT_WELCOME = ""
DEFAULT_BOS = 500
DEFAULT_EOS = 500
DEFAULT_IAT_TYPE = 1


# ==================== 工具函数 ====================
def _ok(resp):
    """判断响应是否成功（flag=True 或 retcode=200）"""
    if not isinstance(resp, dict):
        return False
    return resp.get("flag") is True or resp.get("retcode") == 200


def _fail_desc(resp):
    """提取失败描述"""
    if not resp:
        return "无响应"
    return resp.get("desc") or resp.get("message") or str(resp.get("code", ""))


def auth_asset(session, app_id, asset_key, asset_type):
    """授权单个资产给 appId。asset_type: 1=形象 3=发音人。返回 True/False。"""
    r = xc.post(session, API_AUTH_ASSET, {
        "appId": app_id, "assetKey": asset_key,
        "assetType": asset_type, "assetScene": ASSET_SCENE_COMMON,
    })
    return _ok(r)


def probe_first_authorizable(session, app_id, candidates, asset_type):
    """依次尝试授权候选资产，返回第一个授权成功的 assetKey；都失败返回 None。

    可授权资产因账号而异，接口场景不含形象/发音人，客户端 SDK 必须传 avatarId+vcn，
    且必须先授权给 appId，否则连上即断。用探测代替硬编码默认值。
    """
    for key in candidates:
        if auth_asset(session, app_id, key, asset_type):
            return key
    return None


def cmd_auth_avatar(session, argv):
    """探测并授权可用的形象+发音人给 appId，打印可直接用于 SDK 的 avatarId/vcn。

    用法: auth-avatar <appId> [--anchor ID] [--vcn V]
    不传 --anchor/--vcn 时自动探测候选并取第一个授权成功的。
    """
    pos, opts = _parse_opts(argv)
    if not pos:
        print("用法: auth-avatar <appId> [--anchor ID] [--vcn V]")
        return
    app_id = pos[0]

    anchor = opts.get("anchor")
    if anchor:
        anchor = anchor if auth_asset(session, app_id, anchor, ASSET_TYPE_ANCHOR) else None
    else:
        anchor = probe_first_authorizable(session, app_id, CANDIDATE_ANCHORS, ASSET_TYPE_ANCHOR)

    vcn = opts.get("vcn")
    if vcn:
        vcn = vcn if auth_asset(session, app_id, vcn, ASSET_TYPE_VCN) else None
    else:
        vcn = probe_first_authorizable(session, app_id, CANDIDATE_VCNS, ASSET_TYPE_VCN)

    print(f"\n[资产授权结果] appId={app_id}")
    print(f"  形象 avatarId: {anchor or '（无可授权形象，请到控制台开通）'}")
    print(f"  发音人 vcn:    {vcn or '（无可授权发音人，请到控制台开通）'}")
    print(f"\n[SDK 使用] AvatarParams 里设置：")
    print(f"  avatar.setAvatarId(\"{anchor or 'YOUR_AVATAR_ID'}\")")
    print(f"  tts.setVcn(\"{vcn or 'YOUR_VCN'}\")")
    print(f"  config.setServerUrl(\"{SERVER_URL}\")  # 必须，否则 600003")
    return anchor, vcn


def _extract_scene_id(resp):
    """从 scene createOrUpdate 响应提取 sceneId"""
    if not resp or not isinstance(resp, dict):
        return None
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("sceneId") or data.get("id")
    return data if isinstance(data, str) else None


def _parse_opts(argv):
    """解析命令行参数（同 template/live 工具的格式）"""
    pos, opts = [], {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                opts[key] = argv[i + 1]
                i += 2
            else:
                opts[key] = True
                i += 1
        else:
            pos.append(a)
            i += 1
    return pos, opts


def open_urls(urls, hint=""):
    """打开浏览器，在多个标签页中依次打开链接（复用登录态免登录）。
    urls: [(label, url), ...]
    """
    print(f"\n[跳转浏览器] {hint}")
    for label, url in urls:
        print(f"     {label}: {url}")

    try:
        from playwright.sync_api import sync_playwright
        cookies = xc.load_cookies()
        if not cookies:
            print("[警告] 未找到登录 Cookie，浏览器打开后需要重新登录")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()

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

            for _, url in urls:
                page = context.new_page()
                page.goto(url)

            print(f"[OK] 浏览器已打开 {len(urls)} 个标签页（已注入登录态）")
            print("     浏览器将保持打开，脚本立即退出")
    except ImportError:
        print("[警告] playwright 未安装，请手动访问上述链接")
    except Exception:
        print(f"[提示] 浏览器已关闭，脚本退出")

# ==================== 配置生成器 ====================
def get_interface_config(app_id, scene_name, scene_desc="", **opts):
    """
    生成接口对话应用的配置负载（scene / nlp / interact）。
    opts 支持: domain / temperature / max_tokens / history_times /
              welcome / bos / eos / iat_type
    返回 (scene_payload, nlp_payload, interact_payload)。
    """
    scene_payload = {
        "sceneName": scene_name,
        "appId": app_id,
        "sceneDesc": scene_desc or scene_name,
        "templateId": "",
        "thumbnail": "",
        "sceneType": SCENE_TYPE_INTERFACE,
    }

    nlp_extra = {
        "domain": opts.get("domain", DEFAULT_DOMAIN),
        "temperature": opts.get("temperature", DEFAULT_TEMPERATURE),
        "maxTokens": opts.get("max_tokens", DEFAULT_MAX_TOKENS),
        "historyTimes": opts.get("history_times", DEFAULT_HISTORY_TIMES),
    }
    nlp_payload = {
        "sceneId": "",
        "nlpType": DEFAULT_NLP_TYPE,
        "nlpStatus": 1,
        "nlpExtra": json.dumps(nlp_extra, ensure_ascii=False),
    }

    interact_payload = {
        "iatType": opts.get("iat_type", DEFAULT_IAT_TYPE),
        "sceneId": "",
        "welcomeMessage": opts.get("welcome", DEFAULT_WELCOME),
        "bos": opts.get("bos", DEFAULT_BOS),
        "eos": opts.get("eos", DEFAULT_EOS),
        "nlpAssistantInfo": DEFAULT_NLP_TYPE,
    }

    return scene_payload, nlp_payload, interact_payload


# ==================== 核心功能 ====================
def publish_scene(session, scene_id):
    """发布接口场景。返回 True/False。"""
    r = xc.post(session, API_SCENE_PUBLISH, {"sceneId": scene_id})
    return _ok(r)


def create_interface_app(session, app_id, scene_name, scene_desc="", **opts):
    """
    创建接口对话应用完整流程（scene -> nlp -> interact -> publish）。
    返回 scene_id 或 None。
    """
    print(f"\n[创建接口对话应用] {scene_name}")

    # 权限检查：接口能力为 appType=1（SDK/WebAPI）
    print("[权限检查] 验证应用...")
    r_app = xc.post(session, API_APP_QUERY, {"appId": app_id})
    if not r_app or not r_app.get("flag"):
        print(f"[失败] 查询应用失败: {_fail_desc(r_app)}")
        return None

    apps = r_app.get("data", {}).get("records", [])
    if not apps:
        print(f"[失败] 未找到 appId: {app_id}")
        return None
    app = apps[0]
    print(f"[OK] 应用: {app.get('appName')} (appType={app.get('appType')})")

    scene_payload, nlp_payload, interact_payload = get_interface_config(
        app_id, scene_name, scene_desc, **opts
    )

    # 步骤 1: scene/createOrUpdate
    print("[步骤1/4] 创建场景...")
    r1 = xc.post(session, API_SCENE_UPSERT, scene_payload)
    if not _ok(r1):
        print(f"[失败] 场景创建失败: {_fail_desc(r1)}")
        return None
    scene_id = _extract_scene_id(r1)
    if not scene_id:
        print(f"[失败] 未获取到 sceneId: {r1}")
        return None
    print(f"[OK] 场景已创建: sceneId={scene_id}")

    nlp_payload["sceneId"] = scene_id
    interact_payload["sceneId"] = scene_id

    # 步骤 2: nlp/createOrUpdate
    print("[步骤2/4] 配置 NLP...")
    r2 = xc.post(session, API_NLP_UPSERT, nlp_payload)
    if not _ok(r2):
        print(f"[失败] NLP 配置失败: {_fail_desc(r2)}")
        return None
    print("[OK] NLP 已配置")

    # 步骤 3: interact/createOrUpdate
    print("[步骤3/4] 配置交互...")
    r3 = xc.post(session, API_INTERACT_UPSERT, interact_payload)
    if not _ok(r3):
        print(f"[失败] 交互配置失败: {_fail_desc(r3)}")
        return None
    print("[OK] 交互已配置")

    # 步骤 4: scene/publish
    print("[步骤4/4] 发布场景...")
    if not publish_scene(session, scene_id):
        print(f"[失败] 发布失败（场景已创建，可稍后手动发布）")
        return scene_id
    print("[OK] 场景已发布")

    return scene_id


def query_nlp(session, scene_id):
    """查询场景 NLP 配置。返回 data 或 None。"""
    r = xc.post(session, API_NLP_QUERY, {"sceneId": scene_id})
    return r.get("data") if _ok(r) else None


def list_scenes(session):
    """列出账号下的接口对话场景（sceneType=1）。返回场景列表。"""
    r = xc.post(session, API_SCENE_QUERY, {
        "sceneType": SCENE_TYPE_INTERFACE,
        "sceneStatus": 1,
        "sceneTypeList": None,
        "__times": 0,
    })
    return r.get("data", []) if _ok(r) else []


# ==================== CLI 命令 ====================
def cmd_list(session, argv):
    """列出接口对话场景"""
    scenes = list_scenes(session)
    if not scenes:
        print("\n[空] 未找到接口对话场景")
        return
    print(f"\n[接口对话场景] 共 {len(scenes)} 个\n")
    for sc in scenes:
        print(f"  {sc.get('sceneId')} - {sc.get('sceneName')} (appId={sc.get('appId')})")


def cmd_query(session, argv):
    """查询场景 NLP 配置"""
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: query <sceneId>")
        return
    data = query_nlp(session, pos[0])
    if data:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print("[失败] 查询失败")


def cmd_create(session, argv):
    """创建接口对话应用（scene -> nlp -> interact -> publish）"""
    pos, opts = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: create <appId> <name> [选项]")
        print("示例: create YOUR_APP_ID 健身虚拟人会话-1 --desc 测试")
        print("选项: --desc --domain --temperature --max-tokens --history")
        print("      --welcome --bos --eos --iat-type --no-browser")
        return

    app_id = pos[0]
    scene_name = pos[1]

    # 收集可选 NLP/交互参数
    kwargs = {}
    if "domain" in opts:
        kwargs["domain"] = opts["domain"]
    if "temperature" in opts:
        kwargs["temperature"] = float(opts["temperature"])
    if "max-tokens" in opts:
        kwargs["max_tokens"] = int(opts["max-tokens"])
    if "history" in opts:
        kwargs["history_times"] = int(opts["history"])
    if "welcome" in opts:
        kwargs["welcome"] = opts["welcome"]
    if "bos" in opts:
        kwargs["bos"] = int(opts["bos"])
    if "eos" in opts:
        kwargs["eos"] = int(opts["eos"])
    if "iat-type" in opts:
        kwargs["iat_type"] = int(opts["iat-type"])

    scene_id = create_interface_app(
        session, app_id, scene_name, opts.get("desc", ""), **kwargs
    )
    if not scene_id:
        print("\n[失败] 创建失败")
        return

    print(f"\n[完成] 接口对话应用已创建")
    print(f"     sceneId: {scene_id}")
    print(f"     appId:   {app_id}")
    print(f"     说明: 接口类型通过 appId 的 apiKey/apiSecret 走 SDK/WebAPI 调用")

    # 接口场景不含形象/发音人：探测并授权可用资产，给出 SDK 端直接可用的 avatarId/vcn。
    # 不授权/不设的话，SDK 会“连上即断”（server_connect_success 后立刻 disconnect）。
    if not opts.get("no-auth-avatar"):
        anchor = probe_first_authorizable(session, app_id, CANDIDATE_ANCHORS, ASSET_TYPE_ANCHOR)
        vcn = probe_first_authorizable(session, app_id, CANDIDATE_VCNS, ASSET_TYPE_VCN)
        print(f"\n[形象/发音人] 接口场景需 SDK 端在 AvatarParams 里显式传入：")
        print(f"     avatarId: {anchor or '（探测无可授权形象，请到控制台开通后用 auth-avatar 重试）'}")
        print(f"     vcn:      {vcn or '（探测无可授权发音人，请到控制台开通）'}")
        print(f"     serverUrl: {SERVER_URL}  # SDK 必须显式 setServerUrl，否则握手报 600003")

    config_url = CONFIG_URL_TPL.format(app_id=app_id, scene_id=scene_id)
    print(f"     配置页面: {config_url}")

    if not opts.get("no-browser"):
        open_urls([("配置页面", config_url)], hint="打开配置页面")


# ==================== 入口 ====================
_COMMANDS = {
    "list": cmd_list,
    "query": cmd_query,
    "create": cmd_create,
    "auth-avatar": cmd_auth_avatar,
}

USAGE = __doc__


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(USAGE)
        return
    cmd = sys.argv[1]
    handler = _COMMANDS.get(cmd)
    if not handler:
        print(f"未知命令: {cmd}\n")
        print(USAGE)
        sys.exit(1)

    session = xc.get_session()
    if not session:
        print("[错误] 登录失败")
        sys.exit(1)

    handler(session, sys.argv[2:])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
