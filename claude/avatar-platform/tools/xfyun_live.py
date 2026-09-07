#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
讯飞虚拟人 - 直播项目创建工具

创建虚拟人直播项目（包含默认形象/发音人/商品/分镜），完成后自动跳转浏览器到配置页面。

命令总览
  创建直播项目（写）
    create <appId> <name> [--desc D]
                                        创建直播项目（10 步自动配置 + 跳转浏览器）

  查询直播项目（只读）
    list                                列出账号下的直播场景
    query <sceneId>                     查询直播场景详情
    list-assets <appId>                 列出可用形象/发音人（--type anchor|vcn --name 关键字）

说明
  - 创建完成后自动打开浏览器跳转到配置页面（可手动调整商品/分镜/脚本）
  - 默认形象: 111310001
  - 默认发音人: 灵小琪 x4_lingxiaoqi_oral
  - 默认商品: "商品1"
  - 默认分镜: "分镜1"（空脚本）
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
API_TEMPLATE_UPSERT = "https://virtual-man.xfyun.cn/zs_web/template/createOrUpdate"
API_NLP_UPSERT = "https://virtual-man.xfyun.cn/zs_web/nlp/createOrUpdate"
API_INTERACT_UPSERT = "https://virtual-man.xfyun.cn/zs_web/interact/createOrUpdate"
API_AUTH_ASSET = "https://virtual-man.xfyun.cn/zs_web/app/auth_asset"
API_PRODUCT_ADD = "https://virtual-man.xfyun.cn/zs_web/product/add"
API_STORYBOARD_ADD = "https://virtual-man.xfyun.cn/zs_web/scene/storyboard/add"
API_SCRIPT_ADD = "https://virtual-man.xfyun.cn/zs_web/scene/storyboard/script/add"
API_SCRIPT_UPDATE = "https://virtual-man.xfyun.cn/zs_web/scene/storyboard/script/update"
API_SCENE_QUERY = "https://virtual-man.xfyun.cn/zs_web/scene/query"
API_SCENE_PUBLISH = "https://virtual-man.xfyun.cn/zs_web/scene/publish"
API_ANCHOR_ASSET = "https://virtual-man.xfyun.cn/zs_web/user/anchor_asset"  # 可用形象查询
API_VCN_ASSET = "https://virtual-man.xfyun.cn/zs_web/user/vcn_asset"        # 可用发音人查询

# 直播间访问链接格式
LIVE_URL_TPL = "https://virtual-man.xfyun.cn/marketing/scene/{scene_id}"
CONFIG_URL_TPL = "https://virtual-man.xfyun.cn/console/projects/config/marketing/{app_id}/{scene_id}/explain"

# 资产授权常量
ASSET_TYPE_ANCHOR = 1   # 形象
ASSET_TYPE_VCN = 3      # 发音人
ASSET_SCENE_LIVE = 2    # 直播场景（形象授权用 scene=2）
ASSET_SCENE_VCN = 1     # 发音人授权 scene（控制台实测走 scene=1，非 2）

# ==================== 默认配置常量 ====================
DEFAULT_SCENE_NAME = "直播助手"
DEFAULT_THUMBNAIL = "https://openstorage.xfyousheng.com/asset/asset/20260507/eba80a31-0b8b-4702-af05-a35f8a342263.jpg"
DEFAULT_ANCHOR_ID = "111310001"
DEFAULT_VCN = "x4_lingxiaoqi_oral"
DEFAULT_BG_URL = "https://openstorage.xfyousheng.com/asset/asset/20240606/9dfc4c95-fc23-4461-bc8d-bc52e2bfa134.jpeg"  # 直播默认背景
DEFAULT_LOGO_URL = ""
DEFAULT_GUIDES = "请介绍一下讯飞虚拟人？\n虚拟人有哪些应用场景？\n请问如何制作虚拟人视频？\n请介绍一下智能交互机？"
DEFAULT_PRODUCT_NAME = "商品1"
DEFAULT_STORYBOARD_NAME = "分镜1"
DEFAULT_SCRIPT_CONTENT = "大家好，欢迎来到我的直播间！今天给大家推荐一款非常不错的产品。"

# 默认 anchorMasks（晓姿-蓝色制服的 3 种手势遮罩）
DEFAULT_ANCHOR_MASKS = [
    {"anchorGesture": 0, "anchorLeft": 318, "anchorTop": 183, "anchorRight": 786, "anchorBottom": 1830},
    {"anchorGesture": 1, "anchorLeft": 318, "anchorTop": 183, "anchorRight": 786, "anchorBottom": 903},
    {"anchorGesture": 2, "anchorLeft": 318, "anchorTop": 183, "anchorRight": 786, "anchorBottom": 1227},
]

# ==================== 工具函数 ====================
def _ok(resp):
    """判断响应是否成功"""
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


def _extract_id(resp, key="id"):
    """从响应的 data 提取指定 key 的 ID"""
    if not resp or not isinstance(resp, dict):
        return None
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get(key)
    return None


def _build_script_content(text):
    """将纯文本包成平台脚本编辑器所需的 ProseMirror 富文本 JSON 字符串。

    script/add 传纯文本时编辑器无法解析，显示为空导致虚拟人无词可播；
    script/update 需传如下结构（content 字段本身是 JSON 字符串）。
    """
    anchor = len(text)
    doc = {
        "doc": {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        },
        "selection": {"type": "text", "anchor": anchor, "head": anchor},
    }
    return json.dumps(doc, ensure_ascii=False)


# ==================== 核心功能 ====================
def create_live_project(session, app_id, scene_name=DEFAULT_SCENE_NAME, scene_desc="",
                        anchor_id=DEFAULT_ANCHOR_ID, vcn=DEFAULT_VCN):
    """
    创建虚拟人直播项目完整流程（10 步）。
    返回 dict: {scene_id, product_id, storyboard_id, script_id} 或 None。
    """
    print(f"\n[创建直播项目] {scene_name}")
    print(f"     形象: {anchor_id}, 发音人: {vcn}")
    result = {}

    # 步骤 1: 查询应用信息并检查权限
    print("[步骤1/10] 查询应用信息...")
    r_app = xc.post(session, API_APP_QUERY, {"appId": app_id})
    if not _ok(r_app):
        print(f"[失败] appId 无效或查询失败: {_fail_desc(r_app)}")
        return None

    # 【新增】权限检查
    apps = r_app.get("data", {}).get("records", [])
    if not apps:
        print(f"[失败] 未找到 appId: {app_id}")
        return None

    app = apps[0]
    can_create, msg = xc.check_app_capability(app, 'live')

    if not can_create:
        print(f"[失败] {msg}")
        print(f"\n当前应用信息:")
        print(f"  App ID: {app_id}")
        print(f"  应用名称: {app.get('appName')}")
        print(f"  应用类型: appType={app.get('appType')} (1=接口能力, 2=标准产品)")
        print(f"  当前授权: {[a.get('authKey') for a in app.get('auths', [])]}")
        print(f"\n需要满足:")
        print(f"  - 应用类型: appType=2 (标准产品)")
        print(f"  - 网页产品功能: 订阅时需勾选【数字人直播】")
        print(f"\n请访问订阅页面创建新应用:")
        print(f"  https://virtual-man.xfyun.cn/console/applications/subscribe")

        response = input("\n是否打开浏览器访问订阅页面？(y/n): ").strip().lower()
        if response == 'y':
            xc.open_subscribe_page()

        return None

    print(f"[OK] 权限检查通过")

    # 步骤 2: 创建场景
    print("[步骤2/10] 创建场景...")
    scene_payload = {
        "sceneName": scene_name,
        "appId": app_id,
        "sceneDesc": scene_desc or "1",
        "templateId": 17,
        "thumbnail": DEFAULT_THUMBNAIL,
        "sceneType": 6,
        "sceneProdType": 4,
    }
    r_scene = xc.post(session, API_SCENE_UPSERT, scene_payload)
    if not _ok(r_scene):
        print(f"[失败] 场景创建失败: {_fail_desc(r_scene)}")
        return None
    scene_id = _extract_scene_id(r_scene)
    if not scene_id:
        print(f"[失败] 未获取到 sceneId")
        return None
    result['scene_id'] = scene_id
    print(f"[OK] 场景已创建: sceneId={scene_id}")

    # 步骤 3: 创建形象模板
    print("[步骤3/10] 配置模板...")
    tmpl_payload = {
        "templateType": 1,
        "sceneId": scene_id,
        "guidesContent": DEFAULT_GUIDES,
        "bgUrl": DEFAULT_BG_URL,
        "logoUrl": DEFAULT_LOGO_URL,
        "bgFormat": 0,
        "anchorId": anchor_id,
        "anchorInfo": "{}",
        "vcn": vcn,
        "vcnInfo": '{"speed":50,"pitch":50,"volume":100,"vcnBitrate":16}',
        "theme": "common",
        "width": 1080,
        "height": 1920,
        "title": "虚拟人交互平台演示系统",
        "widgets": '[{"enabled":true,"type":"avatar","name":"虚拟人","rect":{"top":0,"left":0,"height":1920,"width":1080}},{"enabled":true,"type":"products","name":"商品卡片","rect":{"top":1070,"left":30,"height":840,"width":520}}]',
        "anchorMasks": json.dumps(DEFAULT_ANCHOR_MASKS, ensure_ascii=False),
    }
    r_tmpl = xc.post(session, API_TEMPLATE_UPSERT, tmpl_payload)
    if not _ok(r_tmpl):
        print(f"[失败] 模板配置失败: {_fail_desc(r_tmpl)}")
        return None
    print("[OK] 模板已配置")

    # 步骤 4: 配置 NLP
    print("[步骤4/10] 配置 NLP...")
    nlp_payload = {
        "sceneId": scene_id,
        "nlpType": "xinghuo",
        "nlpStatus": 1,
        "nlpExtra": '{"domain":"generalv3.5","temperature":0.5,"maxTokens":4000,"historyTimes":20}',
    }
    r_nlp = xc.post(session, API_NLP_UPSERT, nlp_payload)
    if not _ok(r_nlp):
        print(f"[失败] NLP 配置失败: {_fail_desc(r_nlp)}")
        return None
    print("[OK] NLP 已配置")

    # 步骤 5: 配置交互
    print("[步骤5/10] 配置交互...")
    interact_payload = {
        "iatType": 1,
        "sceneId": scene_id,
        "welcomeMessage": "您好，请问有什么可以帮您？",
        "bos": 500,
        "eos": 500,
        "nlpAssistantInfo": "xinghuo",
    }
    r_interact = xc.post(session, API_INTERACT_UPSERT, interact_payload)
    if not _ok(r_interact):
        print(f"[失败] 交互配置失败: {_fail_desc(r_interact)}")
        return None
    print("[OK] 交互已配置")

    # 步骤 6: 授权发音人
    print("[步骤6/10] 授权发音人...")
    r_vcn = xc.post(session, API_AUTH_ASSET, {
        "appId": app_id, "assetKey": vcn,
        "assetType": ASSET_TYPE_VCN, "assetScene": ASSET_SCENE_VCN,
    })
    if _ok(r_vcn):
        print(f"[OK] 发音人 {vcn} 已授权")
    else:
        print(f"[警告] 发音人授权失败: {_fail_desc(r_vcn)}（继续创建）")

    # 步骤 7: 授权形象
    print("[步骤7/10] 授权形象...")
    r_anchor = xc.post(session, API_AUTH_ASSET, {
        "appId": app_id, "assetKey": anchor_id,
        "assetType": ASSET_TYPE_ANCHOR, "assetScene": ASSET_SCENE_LIVE,
    })
    if _ok(r_anchor):
        print(f"[OK] 形象 {anchor_id} 已授权")
    else:
        print(f"[警告] 形象授权失败: {_fail_desc(r_anchor)}（继续创建）")

    # 步骤 8: 创建默认商品
    print("[步骤8/10] 创建商品...")
    r_product = xc.post(session, API_PRODUCT_ADD, {
        "sceneId": scene_id, "productName": DEFAULT_PRODUCT_NAME,
    })
    if not _ok(r_product):
        print(f"[失败] 商品创建失败: {_fail_desc(r_product)}")
        return None
    product_id = _extract_id(r_product, "productId")
    result['product_id'] = product_id
    print(f"[OK] 商品已创建: productId={product_id}")

    # 步骤 9: 创建默认分镜
    print("[步骤9/10] 创建分镜...")
    r_storyboard = xc.post(session, API_STORYBOARD_ADD, {
        "sceneId": scene_id, "productId": product_id,
        "storyboardName": DEFAULT_STORYBOARD_NAME,
        "storyboardIndex": 1,
        "anchorId": anchor_id, "vcn": vcn,
    })
    if not _ok(r_storyboard):
        print(f"[失败] 分镜创建失败: {_fail_desc(r_storyboard)}")
        return None
    storyboard_id = _extract_id(r_storyboard, "storyboardId")
    result['storyboard_id'] = storyboard_id
    print(f"[OK] 分镜已创建: storyboardId={storyboard_id}")

    # 步骤 10: 添加默认脚本（带内容，启用状态）
    print("[步骤10/10] 添加脚本...")
    r_script = xc.post(session, API_SCRIPT_ADD, {
        "storyboardId": storyboard_id,
        "scriptType": 0,
        "content": DEFAULT_SCRIPT_CONTENT,
        "disable": 0,  # 0=启用，1=禁用
    })
    if not _ok(r_script):
        print(f"[失败] 脚本添加失败: {_fail_desc(r_script)}")
        return None
    script_id = _extract_id(r_script, "scriptId") or _extract_id(r_script, "id")
    result['script_id'] = script_id
    print(f"[OK] 脚本已添加: scriptId={script_id}")

    # 步骤 10b: 更新脚本内容为富文本（ProseMirror JSON）
    # add 传的纯文本编辑器无法解析→显示为空→虚拟人无词可播，需 update 回填富文本
    if script_id:
        print("[步骤10b] 回填脚本富文本内容...")
        r_upd = xc.put(session, API_SCRIPT_UPDATE, {
            "id": str(script_id),
            "scriptType": 0,
            "content": _build_script_content(DEFAULT_SCRIPT_CONTENT),
            "disable": 0,
        })
        if _ok(r_upd):
            print("[OK] 脚本内容已回填（富文本）")
        else:
            print(f"[警告] 脚本内容回填失败: {_fail_desc(r_upd)}（虚拟人可能无词可播，需手动编辑脚本）")

    print(f"\n✅ 直播项目创建完成！sceneId={scene_id}")
    return result


def publish_scene(session, scene_id):
    """发布直播场景。返回 True/False。"""
    r = xc.post(session, API_SCENE_PUBLISH, {
        "sceneId": scene_id, "useType": 1, "verifyMethod": 0,
        "effectEtime": 0, "captcha": "",
    })
    return _ok(r)


def open_urls(urls, hint=""):
    """打开浏览器，在多个标签页中依次打开链接（复用登录态免登录）。
    urls: [(label, url), ...]
    """
    print(f"\n[跳转浏览器] {hint}")
    for label, url in urls:
        print(f"     {label}: {url}")

    try:
        from playwright.sync_api import sync_playwright
        # 加载已保存的 Cookie（从登录时保存的）
        cookies = xc.load_cookies()
        if not cookies:
            print("[警告] 未找到登录 Cookie，浏览器打开后需要重新登录")

        p = sync_playwright().start()
        browser = p.chromium.launch(headless=False, channel="msedge")
        context = browser.new_context()

        # 注入 Cookie（如果有）
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

        # 每个链接开一个标签页
        for _, url in urls:
            page = context.new_page()
            page.goto(url)

        print(f"[OK] 浏览器已打开 {len(urls)} 个标签页（已注入登录态）")
        print("     关闭浏览器窗口后脚本自动退出")
        # 保持浏览器开启，直到用户手动关闭（原始版本行为，非交互式等待）
        try:
            context.pages[-1].wait_for_timeout(600000)  # 最多等 10 分钟
        except Exception:
            pass  # 用户手动关闭浏览器属正常退出
        try:
            browser.close()
        except Exception:
            pass
        p.stop()
    except ImportError:
        print("[警告] playwright 未安装，请手动访问上述链接")
        print("        安装命令: pip install playwright && playwright install chromium")
    except Exception as e:
        print(f"[错误] 浏览器操作失败: {e}")


def list_live_scenes(session):
    """列出账号下的直播场景"""
    r = xc.post(session, API_SCENE_QUERY, {
        "sceneType": 6, "sceneStatus": 1, "sceneTypeList": None, "__times": 0,
    })
    scenes = r.get("data", []) if r else []
    return scenes


def _extract_records(resp):
    """从资源查询响应中提取 records 列表，兼容 data 为 dict 或 list。"""
    if not isinstance(resp, dict):
        return None
    data = resp.get("data")
    if isinstance(data, dict):
        return data.get("records")
    if isinstance(data, list):
        return data
    return None


def list_anchor_assets(session, app_id):
    """查询指定 appId 的可用形象列表。返回 records 或 None。"""
    r = xc.post(session, API_ANCHOR_ASSET, {
        "pageSize": 999, "pageNum": 1, "assetName": "",
        "assetScene": 1, "assetType": 1, "assetLabel": 1,
        "__time": 0, "appId": app_id,
    })
    return _extract_records(r)


def list_vcn_assets(session, app_id):
    """查询指定 appId 的可用发音人列表。返回 records 或 None。"""
    r = xc.post(session, API_VCN_ASSET, {
        "pageSize": 999, "pageNum": 1, "assetName": "",
        "__time": 0, "appId": app_id,
    })
    return _extract_records(r)


# ==================== CLI 命令 ====================
def _parse_opts(argv):
    """解析命令行参数"""
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


def cmd_create(session, argv):
    """创建直播项目（支持自定义形象和发音人）"""
    pos, opts = _parse_opts(argv)
    if len(pos) < 2:
        print("用法: create <appId> <name> [--desc 描述] [--anchor anchorId] [--vcn vcn] [--no-browser]")
        print("示例: create YOUR_APP_ID 我的直播间 --anchor 110026010 --vcn x4_yiting")
        print("说明: 未指定 --anchor/--vcn 时使用默认值（晓姿/灵小琪）")
        return

    app_id = pos[0]
    scene_name = pos[1]
    scene_desc = opts.get("desc", "")
    anchor_id = opts.get("anchor", DEFAULT_ANCHOR_ID)
    vcn = opts.get("vcn", DEFAULT_VCN)

    result = create_live_project(session, app_id, scene_name, scene_desc,
                                  anchor_id=anchor_id, vcn=vcn)
    if result:
        scene_id = result['scene_id']
        print(f"\n[完成] 直播项目已创建")
        print(f"     sceneId: {scene_id}")
        print(f"     商品ID: {result.get('product_id')}")
        print(f"     分镜ID: {result.get('storyboard_id')}")

        # 发布场景（发布接口同步返回，成功即已发布）
        print(f"\n[发布场景] 发布直播项目...")
        if publish_scene(session, scene_id):
            print(f"[OK] 直播项目已发布")
        else:
            print(f"[警告] 发布失败（可在配置页面手动发布）")

        # 生成链接
        live_url = LIVE_URL_TPL.format(scene_id=scene_id)
        config_url = CONFIG_URL_TPL.format(app_id=app_id, scene_id=scene_id)
        print(f"\n[链接]")
        print(f"     直播间链接: {live_url}")
        print(f"     配置页面: {config_url}")

        # 所有操作完成后，一次性打开两个链接
        if not opts.get("no-browser"):
            open_urls([
                ("直播间", live_url),
                ("配置页面", config_url),
            ], "打开直播间和配置页面...")
    else:
        print("\n[失败] 创建失败")


def cmd_list(session, argv):
    """列出直播场景"""
    scenes = list_live_scenes(session)
    print(f"\n[直播场景] 共 {len(scenes)} 个\n")
    for sc in scenes:
        print(f"  {sc.get('sceneName')}")
        print(f"     sceneId: {sc.get('sceneId')}")
        print(f"     appId: {sc.get('appId')}")
        print(f"     创建时间: {sc.get('createTime')}")
        print()


def cmd_query(session, argv):
    """查询直播场景详情（通过 scene/query 遍历匹配）"""
    pos, _ = _parse_opts(argv)
    if not pos:
        print("用法: query <sceneId>")
        return
    scene_id = pos[0]
    scenes = list_live_scenes(session)
    for sc in scenes:
        if str(sc.get("sceneId")) == str(scene_id):
            print(json.dumps(sc, ensure_ascii=False, indent=2))
            return
    print(f"[未找到] sceneId={scene_id}")


def cmd_list_assets(session, argv):
    """列出指定 appId 可用的形象和发音人资源。"""
    pos, opts = _parse_opts(argv)
    if not pos:
        print("用法: list-assets <appId> [--type anchor|vcn] [--name 关键字]")
        print("示例: list-assets YOUR_APP_ID")
        print("      list-assets YOUR_APP_ID --type vcn --name 小露")
        return
    app_id = pos[0]
    only = opts.get("type")           # anchor / vcn，缺省两者都列
    kw = opts.get("name")             # 名称过滤关键字
    if isinstance(kw, bool):
        kw = None

    def _show(title, records, default_key):
        print(f"\n[{title}]")
        if not records:
            print("  （未查询到资源或响应异常）")
            return
        shown = 0
        for it in records:
            key = it.get("assetKey") or it.get("id")
            name = it.get("assetName") or it.get("name") or ""
            if kw and kw not in str(name) and kw not in str(key):
                continue
            mark = "  ★默认" if str(key) == str(default_key) else ""
            print(f"    - {name}  (key={key}){mark}")
            shown += 1
        print(f"  共 {shown} 个" + ("（已按关键字过滤）" if kw else f" / 总 {len(records)}"))

    if only != "vcn":
        _show("可用形象 anchor", list_anchor_assets(session, app_id), DEFAULT_ANCHOR_ID)
    if only != "anchor":
        _show("可用发音人 vcn", list_vcn_assets(session, app_id), DEFAULT_VCN)


# ==================== 入口 ====================
_COMMANDS = {
    "create": cmd_create,
    "list": cmd_list,
    "query": cmd_query,
    "list-assets": cmd_list_assets,
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
