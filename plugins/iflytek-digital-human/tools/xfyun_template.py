#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞虚拟人 - Web 对话模板应用管理工具

支持创建、配置、发布 Web 对话模板应用（智能客服/H5 通话/大屏交互等）。

命令总览
  只读查询
    list-templates                      列出可用模板
    query <sceneId>                     查询场景完整配置

  创建模板应用（写）
    create <templateId> <appId> <name> [--desc D]
                                        创建模板应用（自动完成 4 步配置）

  更新配置（写）
    update-bg <sceneId> <图片路径>       更新背景图
    update-avatar <sceneId> <anchorId> <vcn>
                                        更新形象和声音
    update-guides <sceneId> <引导词>     更新问题引导词
    update-lang <sceneId> <iatType>     更新识别语言

  发布应用（写）
    publish <sceneId> [--domain D] [--expire TIMESTAMP]
                                        发布并绑定域名（生成访问链接）

说明
  - templateId: 1=大屏交互 3=Web智能客服 4=Web弹窗 7=H5对话 11=H5通话
  - iatType: 1=中文 10002=英文 10003=日语 10004=韩语
  - 发布链接格式: https://virtual-man.xfyun.cn/interact_web/common/web/{sceneId}
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
API_SCENE_UPSERT = "https://virtual-man.xfyun.cn/zs_web/scene/createOrUpdate"
API_TEMPLATE_UPSERT = "https://virtual-man.xfyun.cn/zs_web/template/createOrUpdate"
API_NLP_UPSERT = "https://virtual-man.xfyun.cn/zs_web/nlp/createOrUpdate"
API_INTERACT_UPSERT = "https://virtual-man.xfyun.cn/zs_web/interact/createOrUpdate"
API_SCENE_PUBLISH = "https://virtual-man.xfyun.cn/zs_web/scene/publish"
API_RES_UPLOAD = "https://virtual-man.xfyun.cn/zs_web/user/res/add"
API_TEMPLATE_QUERY = "https://virtual-man.xfyun.cn/zs_web/template/query"
API_AUTH_ASSET = "https://virtual-man.xfyun.cn/zs_web/app/auth_asset"

# 资产类型（assetType）
ASSET_TYPE_ANCHOR = 1   # 形象
ASSET_TYPE_VCN = 3      # 发音人
# 资产场景（assetScene）
ASSET_SCENE_COMMON = 1  # 通用场景
ASSET_SCENE_LIVE = 2    # 数字人直播场景

# ==================== 模板配置常量 ====================
# 模板元数据（templateId -> 名称/缩略图）
TEMPLATES = {
    1: {"name": "大屏交互对话", "thumbnail": "https://openstorage.xfyousheng.com/asset/asset/20260507/70a99db6-447b-4fa8-ad64-9cd60b174d9d.png"},
    3: {"name": "Web智能客服", "thumbnail": "https://openstorage.xfyousheng.com/asset/asset/20260507/41e4dae0-c7b3-497a-9b1f-a76150882d40.png"},
    4: {"name": "Web智能客服-横屏弹窗", "thumbnail": "https://openstorage.xfyousheng.com/asset/asset/20260507/af619b05-e0f4-4630-b63a-b8f2b61e3685.png"},
    7: {"name": "H5-对话模板", "thumbnail": "https://openstorage.xfyousheng.com/asset/asset/20240709/1a99c16a-c898-4498-91fa-8b6ee8b05690.jpg"},
    11: {"name": "H5-通话模板", "thumbnail": "https://openstorage.xfyousheng.com/asset/asset/20250912/11c3114a-8f78-413f-8fdb-04b4d8153c87.jpeg"},
}

# 默认配置值
DEFAULT_GUIDES = "请介绍一下讯飞虚拟人？\n虚拟人有哪些应用场景？\n请问如何制作虚拟人视频？\n请介绍一下智能交互机？"
DEFAULT_WELCOME = "您好，请问有什么可以帮您？"
DEFAULT_TITLE = "虚拟人交互平台演示系统"

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


def _extract_scene_id(resp):
    """从 scene createOrUpdate 响应提取 sceneId"""
    if not resp or not isinstance(resp, dict):
        return None
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("sceneId") or data.get("id")
    return data if isinstance(data, str) else None



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
            # 不等待，打开后立即退出（浏览器保持运行）
    except ImportError:
        print("[警告] playwright 未安装，请手动访问上述链接")
    except Exception:
        print(f"[提示] 浏览器已关闭，脚本退出")


# ==================== 模板配置生成器 ====================
def get_template_config(template_id, scene_id, app_id, scene_name, scene_desc=""):
    """
    根据 templateId 生成 4 步配置负载（scene/template/nlp/interact）。
    返回 (scene_payload, template_payload, nlp_payload, interact_payload) 或 None。
    """
    if template_id not in TEMPLATES:
        return None
    
    tmpl = TEMPLATES[template_id]
    scene_payload = {
        "sceneName": scene_name,
        "appId": app_id,
        "sceneDesc": scene_desc or scene_name,
        "templateId": template_id,
        "thumbnail": tmpl["thumbnail"],
        "sceneType": 2,
        "sceneProdType": 1,
    }
    
    # templateId 对应的模板配置（从抓包提取的默认值）
    configs = {
        3: {  # Web智能客服
            "bgUrl": "https://openstorage.xfyousheng.com/asset/asset/20240606/4f0b17ca-1a0c-4934-8068-0cba5d79ecc8.jpeg",
            "anchorId": "110592024",
            "vcn": "x4_mingge",
            "width": 1920,
            "height": 1080,
            "widgets": '[{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":100,"left":684.375,"height":980,"width":551.25}}]',
        },
        11: {  # H5-通话模板
            "bgUrl": "https://openstorage.xfyousheng.com/asset/asset/20240708/185242bd-8c88-4f71-bcb6-757742df1840.jpg",
            "anchorId": "110117005",
            "vcn": "x4_lingxiaoqi_oral",
            "width": 1080,
            "height": 1920,
            "widgets": '[{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":0,"left":0,"height":1920,"width":1080}},{"enabled":true,"type":"micphone","name":"语音按钮","rect":{"left":504,"top":1435,"width":110,"height":110}}]',
        },
        1: {  # 大屏交互对话
            "bgUrl": "https://openstorage.xfyousheng.com/asset/asset/20240606/9dfc4c95-fc23-4461-bc8d-bc52e2bfa134.jpeg",
            "anchorId": "110117005",
            "vcn": "x4_lingxiaoqi_oral",
            "width": 1920,
            "height": 1080,
            "widgets": '[{"enabled":true,"type":"guide","name":"交互指引","style":"scrolllist","rect":{"left":115,"top":296,"width":650,"height":360}},{"enabled":true,"type":"asr","name":"识别结果展示","rect":{"top":687,"left":115,"height":80,"width":650}},{"enabled":true,"type":"micphone","name":"语音按钮","rect":{"left":395,"top":800,"width":90,"height":90}},{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":100,"left":684.375,"height":980,"width":551.25}},{"enabled":true,"type":"nlp","name":"理解结果展示","rect":{"top":215,"left":1154,"height":700,"width":712}}]',
        },
        4: {  # Web智能客服-横屏弹窗
            "bgUrl": "https://openstorage.xfyousheng.com/asset/asset/20240606/4f0b17ca-1a0c-4934-8068-0cba5d79ecc8.jpeg",
            "anchorId": "110592024",
            "vcn": "x4_mingge",
            "width": 1920,
            "height": 1080,
            "widgets": '[{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":100,"left":684.375,"height":980,"width":551.25}}]',
        },
        7: {  # H5-对话模板
            "bgUrl": "https://openstorage.xfyousheng.com/asset/asset/20240708/185242bd-8c88-4f71-bcb6-757742df1840.jpg",
            "anchorId": "110117005",
            "vcn": "x4_lingxiaoqi_oral",
            "width": 1080,
            "height": 1920,
            "widgets": '[{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":0,"left":0,"height":1920,"width":1080}}]',
        },
    }
    
    cfg = configs.get(template_id, configs[3])  # 兜底用 template 3
    template_payload = {
        "templateType": 1,
        "sceneId": scene_id,
        "guidesContent": DEFAULT_GUIDES,
        "bgUrl": cfg["bgUrl"],
        "bgFormat": 0,
        "anchorId": cfg["anchorId"],
        "anchorInfo": "{}",
        "vcn": cfg["vcn"],
        "vcnInfo": '{"speed":50,"pitch":50,"volume":100,"vcnBitrate":16}',
        "theme": "common",
        "width": cfg["width"],
        "height": cfg["height"],
        "title": DEFAULT_TITLE,
        "widgets": cfg["widgets"],
    }
    
    nlp_payload = {
        "sceneId": scene_id,
        "nlpType": "xinghuo",
        "nlpStatus": 1,
        "nlpExtra": '{"domain":"generalv3.5","temperature":0.5,"maxTokens":4000,"historyTimes":20}',
    }
    
    interact_payload = {
        "iatType": 1,
        "sceneId": scene_id,
        "welcomeMessage": DEFAULT_WELCOME,
        "bos": 500,
        "eos": 500,
        "nlpAssistantInfo": "xinghuo",
    }
    
    return scene_payload, template_payload, nlp_payload, interact_payload


# ==================== 核心功能 ====================
def create_template_app(session, template_id, app_id, scene_name, scene_desc=""):
    """
    创建模板应用完整流程（4 步createOrUpdate）。
    返回 scene_id 或 None。
    """
    print(f"\n[创建模板应用] {TEMPLATES.get(template_id, {}).get('name', template_id)}")

    # 【新增】权限检查
    print("[权限检查] 验证应用权限...")
    API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"
    r_app = xc.post(session, API_APP_QUERY, {"appId": app_id})
    if not r_app or not r_app.get("flag"):
        print(f"[失败] 查询应用失败: {_fail_desc(r_app)}")
        return None

    apps = r_app.get("data", {}).get("records", [])
    if not apps:
        print(f"[失败] 未找到 appId: {app_id}")
        return None

    app = apps[0]
    can_create, msg = xc.check_app_capability(app, 'web_template')

    if not can_create:
        print(f"[失败] {msg}")
        print(f"\n当前应用信息:")
        print(f"  App ID: {app_id}")
        print(f"  应用名称: {app.get('appName')}")
        print(f"  应用类型: appType={app.get('appType')} (1=接口能力, 2=标准产品)")
        print(f"  当前授权: {[a.get('authKey') for a in app.get('auths', [])]}")
        print(f"\n需要满足:")
        print(f"  - 应用类型: appType=2 (标准产品)")
        print(f"  - 网页产品功能: 订阅时需勾选【Web对话系统】")
        print(f"\n请访问订阅页面创建新应用:")
        print(f"  https://virtual-man.xfyun.cn/console/applications/subscribe")

        response = input("\n是否打开浏览器访问订阅页面？(y/n): ").strip().lower()
        if response == 'y':
            xc.open_subscribe_page()

        return None

    print(f"[OK] 权限检查通过")

    # 步骤 1: scene/createOrUpdate
    scene_payload, tmpl_payload, nlp_payload, interact_payload = get_template_config(
        template_id, "", app_id, scene_name, scene_desc
    )
    
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
    
    # 更新后续 payload 的 sceneId
    tmpl_payload["sceneId"] = scene_id
    nlp_payload["sceneId"] = scene_id
    interact_payload["sceneId"] = scene_id

    # 授权资产：模板用到的形象和发音人必须先授权给 appId，否则不生效
    anchor_id = tmpl_payload.get("anchorId")
    vcn = tmpl_payload.get("vcn")
    print("[授权资产] 授权形象和发音人...")
    if anchor_id:
        ok_a = auth_asset(session, app_id, anchor_id, ASSET_TYPE_ANCHOR, ASSET_SCENE_COMMON)
        print(f"  形象 {anchor_id}: {'OK' if ok_a else '失败'}")
    if vcn:
        ok_v = auth_asset(session, app_id, vcn, ASSET_TYPE_VCN, ASSET_SCENE_COMMON)
        print(f"  发音人 {vcn}: {'OK' if ok_v else '失败'}")

    # 步骤 2: template/createOrUpdate
    print("[步骤2/4] 配置模板...")
    r2 = xc.post(session, API_TEMPLATE_UPSERT, tmpl_payload)
    if not _ok(r2):
        print(f"[失败] 模板配置失败: {_fail_desc(r2)}")
        return None
    print("[OK] 模板已配置")
    
    # 步骤 3: nlp/createOrUpdate
    print("[步骤3/4] 配置 NLP...")
    r3 = xc.post(session, API_NLP_UPSERT, nlp_payload)
    if not _ok(r3):
        print(f"[失败] NLP 配置失败: {_fail_desc(r3)}")
        return None
    print("[OK] NLP 已配置")
    
    # 步骤 4: interact/createOrUpdate
    print("[步骤4/4] 配置交互...")
    r4 = xc.post(session, API_INTERACT_UPSERT, interact_payload)
    if not _ok(r4):
        print(f"[失败] 交互配置失败: {_fail_desc(r4)}")
        return None
    print("[OK] 交互已配置")
    
    return scene_id


def upload_resource(session, file_path, file_type=1, file_format=0):
    """
    上传资源（背景图/Logo）。
    file_type: 1=图片
    file_format: 0=PNG/JPG 等
    返回 fileUrl 或 None。
    """
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        print(f"[错误] 文件不存在: {file_path}")
        return None
    
    # 猜测 MIME 类型
    import mimetypes
    format_str = mimetypes.guess_type(p.name)[0] or "image/png"
    
    # multipart 上传（同知识库工具的模式）
    headers = {"Content-Type": None}
    files = {"file": (p.name, p.open("rb"), format_str)}
    data = {"fileType": file_type, "fileFormat": file_format, "formatStr": format_str}
    
    try:
        resp = session.post(API_RES_UPLOAD, files=files, data=data, headers=headers, timeout=60)
        if resp.status_code != 200:
            print(f"[错误] 上传 HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        j = resp.json()
        if not _ok(j):
            print(f"[失败] 上传返回: {_fail_desc(j)}")
            return None
        file_url = j.get("data", {}).get("fileUrl")
        return file_url
    except Exception as e:
        print(f"[错误] 上传异常: {e}")
        return None
    finally:
        try:
            files["file"][1].close()
        except Exception:
            pass


def query_template(session, scene_id):
    """查询场景的模板配置。返回 data dict 或 None。"""
    r = xc.post(session, API_TEMPLATE_QUERY, {"sceneId": scene_id})
    return r.get("data") if _ok(r) else None


def get_app_id_by_scene(session, scene_id):
    """按 sceneId 反查 appId（遍历对话/直播场景）。返回 appId 或 None。"""
    for stype in (2, 6):  # 2=对话场景 6=直播场景
        r = xc.post(session, "https://virtual-man.xfyun.cn/zs_web/scene/query",
                    {"sceneType": stype, "sceneStatus": 1, "sceneTypeList": None, "__times": 0})
        for sc in (r.get("data", []) if r else []):
            if str(sc.get("sceneId")) == str(scene_id):
                return sc.get("appId")
    return None


def auth_asset(session, app_id, asset_key, asset_type, asset_scene=ASSET_SCENE_COMMON):
    """
    授权资产给应用。发音人/形象在使用前必须先授权给对应 appId，否则不生效。
    asset_type: 1=形象 3=发音人
    asset_scene: 1=通用场景 2=直播场景
    返回 True/False。
    """
    r = xc.post(session, API_AUTH_ASSET, {
        "appId": app_id, "assetKey": asset_key,
        "assetType": asset_type, "assetScene": asset_scene,
    })
    return _ok(r)


def publish_scene(session, scene_id, domain="", expire_time=0, use_type=1, verify_method=0):
    """
    发布场景并绑定域名。
    domain: 授权域名（可空，不限制域名时传空串）
    expire_time: 有效期时间戳（毫秒，0=永久）
    返回 True/False。
    """
    payload = {
        "sceneId": scene_id,
        "useType": use_type,
        "verifyMethod": verify_method,
        "effectEtime": expire_time,
        "captcha": "",
    }
    if domain:
        payload["authDomain"] = domain
    
    r = xc.post(session, API_SCENE_PUBLISH, payload)
    return _ok(r)


# ==================== CLI 命令 ====================
def _parse_opts(argv):
    """解析命令行参数（同知识库工具的格式）"""
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


def cmd_list_templates(session, argv):
    """列出可用模板"""
    print("\n[可用模板]\n")
    for tid, info in sorted(TEMPLATES.items()):
        print(f"  {tid} - {info['name']}")
    print(f"\n共 {len(TEMPLATES)} 个模板")


def cmd_create(session, argv):
    """创建模板应用（完成后自动跳转浏览器）"""
    pos, opts = _parse_opts(argv)
    if len(pos) < 3:
        print("用法: create <templateId> <appId> <name> [--desc 描述] [--no-browser]")
        print("示例: create 3 YOUR_APP_ID 我的智能客服 --desc 测试应用")
        print("说明: 创建完成后自动打开浏览器配置页面，--no-browser 跳过")
        return

    template_id = int(pos[0])
    app_id = pos[1]
    scene_name = pos[2]
    scene_desc = opts.get("desc", "")

    if template_id not in TEMPLATES:
        print(f"[错误] 不支持的 templateId: {template_id}")
        print("可用模板:")
        for tid, info in TEMPLATES.items():
            print(f"  {tid} - {info['name']}")
        return

    scene_id = create_template_app(session, template_id, app_id, scene_name, scene_desc)
    if scene_id:
        print(f"\n[完成] 模板应用已创建")
        print(f"     sceneId: {scene_id}")

        # 自动发布
        print(f"\n[自动发布] 发布场景...")
        if publish_scene(session, scene_id):
            print(f"[OK] 场景已发布")
            access_url = f"https://virtual-man.xfyun.cn/interact_web/common/web/{scene_id}"
            config_url = f"https://virtual-man.xfyun.cn/console/projects/config/{app_id}/{scene_id}/view"

            print(f"     访问链接: {access_url}")
            print(f"     配置链接: {config_url}")

            # 跳转浏览器：同时打开访问链接 + 配置页面两个标签页
            if not opts.get("no-browser"):
                open_urls([
                    ("访问链接", access_url),
                    ("配置页面", config_url),
                ], hint="打开访问链接和配置页面")
        else:
            print(f"[失败] 发布失败")
    else:
        print("\n[失败] 创建失败")


def cmd_update_bg(session, argv):
    """更新背景图"""
    pos, _ = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: update-bg <sceneId> <图片路径>")
        return
    scene_id, img_path = pos[0], pos[1]

    # 先查询场景配置，获取必填字段 guidesContent 和 widgets
    print(f"\n[查询场景配置] sceneId={scene_id}...")
    tmpl = query_template(session, scene_id)
    if not tmpl:
        print("[失败] 查询场景配置失败")
        return

    print(f"[上传背景图] {img_path}...")
    file_url = upload_resource(session, img_path)
    if not file_url:
        print("[失败] 上传失败")
        return
    print(f"[OK] 已上传: {file_url}")

    print(f"\n[更新场景背景]...")
    payload = {
        "templateType": 1,
        "sceneId": scene_id,
        "bgUrl": file_url,
        "bgFormat": 0,
        "guidesContent": tmpl.get("guidesContent", ""),
        "widgets": tmpl.get("widgets", "[]"),
    }
    r = xc.post(session, API_TEMPLATE_UPSERT, payload)
    if _ok(r):
        print("[OK] 背景已更新")
    else:
        print(f"[失败] 更新失败: {_fail_desc(r)}")


def cmd_update_avatar(session, argv):
    """更新形象和声音（自动授权新资产）"""
    pos, opts = _parse_opts(argv)
    if len(pos) < 3:
        print("用法: update-avatar <sceneId> <anchorId> <vcn> [--app appId]")
        print("示例: update-avatar 336442969701879808 111322001 x4_yuexiaoni_assist")
        print("说明: 换形象/发音人前需授权资产，未传 --app 时自动按 sceneId 反查 appId")
        return
    scene_id, anchor_id, vcn = pos[0], pos[1], pos[2]

    # 先查询场景配置，获取必填字段
    print(f"\n[查询场景配置] sceneId={scene_id}...")
    tmpl = query_template(session, scene_id)
    if not tmpl:
        print("[失败] 查询场景配置失败")
        return

    # 换形象/发音人前必须先授权资产，否则不生效
    app_id = opts.get("app") or get_app_id_by_scene(session, scene_id)
    if app_id:
        print(f"[授权资产] appId={app_id}...")
        ok_a = auth_asset(session, app_id, anchor_id, ASSET_TYPE_ANCHOR, ASSET_SCENE_COMMON)
        print(f"  形象 {anchor_id}: {'OK' if ok_a else '失败'}")
        ok_v = auth_asset(session, app_id, vcn, ASSET_TYPE_VCN, ASSET_SCENE_COMMON)
        print(f"  发音人 {vcn}: {'OK' if ok_v else '失败'}")
    else:
        print(f"[警告] 未能确定 appId，跳过资产授权。若更新后不生效，请用 --app 指定 appId 重试")

    print(f"\n[更新形象和声音]...")
    payload = {
        "templateType": 1,
        "sceneId": scene_id,
        "anchorId": anchor_id,
        "vcn": vcn,
        "vcnInfo": '{"speed":50,"pitch":50,"volume":100,"vcnBitrate":16}',
        "anchorInfo": "{}",
        "guidesContent": tmpl.get("guidesContent", ""),
        "widgets": tmpl.get("widgets", "[]"),
    }
    r = xc.post(session, API_TEMPLATE_UPSERT, payload)
    if _ok(r):
        print(f"[OK] 形象和声音已更新")
        print(f"     anchorId={anchor_id}, vcn={vcn}")
    else:
        print(f"[失败] 更新失败: {_fail_desc(r)}")


def cmd_publish(session, argv):
    """发布场景（发布后自动跳转浏览器）"""
    pos, opts = _parse_opts(argv)
    if not pos:
        print("用法: publish <sceneId> [--domain D] [--expire TIMESTAMP] [--app appId] [--no-browser]")
        print("示例: publish 336442969701879808 --domain 124.221. --expire 1785513599999")
        print("说明: 发布后自动打开浏览器配置页面，--no-browser 跳过")
        return
    scene_id = pos[0]
    domain = opts.get("domain", "")
    expire = int(opts.get("expire", 0))

    print(f"\n[发布场景] sceneId={scene_id}")
    if domain:
        print(f"     授权域名: {domain}")
    if expire:
        import time
        exp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expire / 1000))
        print(f"     有效期: {exp_str}")
    else:
        print(f"     有效期: 永久")

    if publish_scene(session, scene_id, domain=domain, expire_time=expire):
        print(f"[OK] 场景已发布")
        access_url = f"https://virtual-man.xfyun.cn/interact_web/common/web/{scene_id}"
        print(f"     访问链接: {access_url}")

        # 跳转浏览器到配置页面
        if not opts.get("no-browser"):
            app_id = opts.get("app") or get_app_id_by_scene(session, scene_id)
            if app_id:
                config_url = f"https://virtual-man.xfyun.cn/console/projects/config/{app_id}/{scene_id}/view"
                open_urls([
                    ("访问链接", access_url),
                    ("配置页面", config_url),
                ], hint="打开访问链接和配置页面")
            else:
                print(f"[警告] 未能确定 appId，跳过浏览器跳转。使用 --app 指定 appId 可自动打开")
        else:
            print(f"     提示: 可用浏览器访问配置页面调整设置")
    else:
        print(f"[失败] 发布失败")


def cmd_query(session, argv):
    """查询场景配置"""
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: query <sceneId>")
        return
    scene_id = pos[0]
    tmpl = query_template(session, scene_id)
    if tmpl:
        import json
        print(json.dumps(tmpl, ensure_ascii=False, indent=2))
    else:
        print("[失败] 查询失败")


# ==================== 入口 ====================
_COMMANDS = {
    "list-templates": cmd_list_templates,
    "create": cmd_create,
    "query": cmd_query,
    "update-bg": cmd_update_bg,
    "update-avatar": cmd_update_avatar,
    "publish": cmd_publish,
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
