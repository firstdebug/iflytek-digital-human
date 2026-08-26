"""
讯飞虚拟人服务查询工具
功能：登录后查询所有场景和对应的 appID、APIKey、APISecret（脱敏显示）
"""
import sys

# Windows 下强制 stdout/stderr 使用 UTF-8，避免中文输出乱码（GBK 默认）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Python < 3.7 无 reconfigure，忽略

import json
import requests
from pathlib import Path
from typing import Optional
import xfyun_common as xc
import xfyun_secrets as xs


# ==================== 密钥脱敏工具 ====================
def mask_secret(value, show_prefix=4, show_suffix=4):
    """脱敏显示：只显示前后几位"""
    if value == "未找到":
        return value
    return xs.mask_secret(value, show_prefix=show_prefix, show_suffix=show_suffix)


def mask_dict(data, depth=3):
    """递归脱敏字典中的敏感字段（apiKey/apiSecret/apiUrl）"""
    return xs.mask_dict(data, depth=depth)

# API 端点
API_SCENE_QUERY = "https://virtual-man.xfyun.cn/zs_web/scene/query"
API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"

def ensure_login() -> Optional[requests.Session]:
    """确保已登录，返回带 Cookie 的 session"""
    return xc.get_session()


# ==================== 业务接口查询 ====================
def query_scenes(session: requests.Session):
    """查询所有场景列表"""
    print("\n" + "="*60)
    print("[查询] 场景列表...")
    print("="*60)

    try:
        resp = session.post(API_SCENE_QUERY, json={
            "sceneType": 1,
            "sceneStatus": 1,
            "sceneTypeList": None,
            "__times": 0
        }, timeout=10)

        print(f"[HTTP] 状态码: {resp.status_code}")

        if resp.status_code != 200:
            print(f"[错误] 请求失败: {resp.text}")
            return None

        data = resp.json()

        # 检查是否登录失效
        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {xc.COOKIE_FILE} 后重新运行")
            return None

        if data.get("flag") != True:
            print(f"[警告] 接口返回异常: {data.get('desc', '未知错误')}")
            return None

        scenes = data.get("data", [])
        print(f"[OK] 查询成功，共找到 {len(scenes)} 个场景\n")

        return scenes

    except Exception as e:
        print(f"[错误] 请求异常: {e}")
        return None


def query_app_detail(session: requests.Session, app_id: str, debug=False):
    """查询指定 appId 的详细信息"""
    try:
        resp = session.post(API_APP_QUERY, json={
            "appId": app_id
        }, timeout=10)

        if resp.status_code != 200:
            return None

        data = resp.json()

        # 调试模式：打印脱敏后的返回
        if debug:
            print(f"\n[调试] app/query 返回数据:")
            print(json.dumps(mask_dict(data), ensure_ascii=False, indent=2))

        if data.get("flag") == True:
            # 数据在 data.records 数组里
            records = data.get("data", {}).get("records", [])
            if records:
                return records[0]  # 返回第一条记录
        return None

    except Exception as e:
        print(f"[警告] 查询 {app_id} 失败: {e}")
        return None


def display_scenes(scenes: list, session: requests.Session):
    """格式化显示所有场景和对应的密钥信息"""
    if not scenes:
        print("[空] 没有找到任何场景")
        return

    print("[列表] 场景详情:\n")
    print("="*80)

    for idx, scene in enumerate(scenes, 1):
        scene_id = scene.get("sceneId", "N/A")
        scene_name = scene.get("sceneName", "未命名")
        app_id = scene.get("appId", "")
        scene_type = scene.get("sceneType", "")

        print(f"\n[场景 {idx}]")
        print(f"  场景名称: {scene_name}")
        print(f"  场景 ID:  {scene_id}")
        print(f"  场景类型: {scene_type}")
        print(f"  App ID:   {app_id}")

        # 如果有 appId，查询详细信息获取密钥
        if app_id:
            print(f"  [查询] 密钥信息...", end=" ")
            # 第一次查询时开启调试模式
            app_detail = query_app_detail(session, app_id, debug=(idx == 1))

            if app_detail:
                api_key = app_detail.get("apiKey", "未找到")
                api_secret = app_detail.get("apiSecret", "未找到")
                print("[OK]")
                print(f"  API Key:    {mask_secret(api_key)}")
                print(f"  API Secret: {mask_secret(api_secret)}")
            else:
                print("[失败]")

        # 显示其他可能有用的信息
        if scene.get("modelName"):
            print(f"  模型名称: {scene.get('modelName')}")
        if scene.get("modelId"):
            print(f"  模型 ID:  {scene.get('modelId')}")

        print("-" * 80)


def export_to_json(scenes: list, session: requests.Session):
    """导出数据到 JSON 文件（密钥脱敏）"""
    output_file = Path("xfyun_scenes_export.json")

    export_data = []
    for scene in scenes:
        app_id = scene.get("appId", "")
        scene_data = {
            "sceneName": scene.get("sceneName"),
            "sceneId": scene.get("sceneId"),
            "appId": app_id,
            "sceneType": scene.get("sceneType"),
        }

        # 查询密钥（导出时脱敏）
        if app_id:
            app_detail = query_app_detail(session, app_id)
            if app_detail:
                scene_data["apiKey"] = mask_secret(app_detail.get("apiKey"))
                scene_data["apiSecret"] = mask_secret(app_detail.get("apiSecret"))

        export_data.append(scene_data)

    output_file.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[导出] 数据已导出（密钥已脱敏）: {output_file.absolute()}")


# ==================== 应用查询（直接查所有应用，不通过场景）====================
def query_all_apps(session: requests.Session):
    """直接查询所有应用（不通过场景），返回应用列表"""
    print("\n" + "="*60)
    print("[查询] 所有应用列表...")
    print("="*60)

    try:
        resp = session.post(API_APP_QUERY, json={
            "current": 1,
            "size": 100
        }, timeout=10)

        if resp.status_code != 200:
            print(f"[错误] 请求失败: {resp.text}")
            return None

        data = resp.json()

        if data.get("code") == 80000:
            print(f"[警告] 登录已失效，请删除 {xc.COOKIE_FILE} 后重新运行")
            return None

        if data.get("flag") != True:
            print(f"[警告] 接口返回异常: {data.get('desc', '未知错误')}")
            return None

        apps = data.get("data", {}).get("records", [])
        print(f"[OK] 查询成功，共找到 {len(apps)} 个应用\n")
        return apps

    except Exception as e:
        print(f"[错误] 请求异常: {e}")
        return None


# 能力判断（authKey → 网页产品名）
CAPABILITY_LABELS = {
    "WEB_CONVERSATION": "Web对话系统",
    "DIGITAL_LIVE": "数字人直播",
    "PC_ASSISTANT": "PC智能助手",
}


def _app_capabilities(app):
    """根据 auths 判断应用具备哪些标准产品能力（返回网页产品名列表）"""
    caps = []
    for auth in app.get("auths", []):
        key = auth.get("authKey")
        if key in CAPABILITY_LABELS and auth.get("licState") == "valid":
            caps.append(CAPABILITY_LABELS[key])
    return caps


def display_apps(apps: list):
    """格式化显示所有应用（含能力判断）"""
    if not apps:
        print("[空] 没有找到任何应用")
        return

    print("="*80)
    print("[应用列表]\n")

    APP_TYPE_LABEL = {1: "接口能力(SDK/WebAPI)", 2: "标准产品(Web模板/直播)"}

    for idx, app in enumerate(apps, 1):
        app_type = app.get("appType")
        is_effect = app.get("isEffect")
        caps = _app_capabilities(app)

        print(f"[应用 {idx}]")
        print(f"  应用名称: {app.get('appName', '未命名')}")
        print(f"  App ID:   {app.get('appId', 'N/A')}")
        print(f"  应用类型: {app_type} - {APP_TYPE_LABEL.get(app_type, '未知')}")
        print(f"  是否有效: {'是' if is_effect else '否（已过期）'}")
        print(f"  API Key:    {mask_secret(app.get('apiKey'))}")
        print(f"  API Secret: {mask_secret(app.get('apiSecret'))}")
        if caps:
            print(f"  标准产品能力: {', '.join(caps)}")
        else:
            print(f"  标准产品能力: 无（仅接口能力）")
        print("-" * 80)


# ==================== 主流程 ====================
def main():
    import sys

    print("="*60)
    print("讯飞虚拟人服务查询工具")
    print("="*60)

    # 解析命令：list-apps（查所有应用，默认） / list-scenes（查场景）
    command = sys.argv[1] if len(sys.argv) > 1 else "list-apps"

    # --help / -h：只打印用法，不触发登录和查询（避免误 dump 凭据）
    if command in ("--help", "-h", "help"):
        print("\n用法: python xfyun_query_services.py [command]")
        print("\n可用命令:")
        print("  list-apps     查询账号下所有应用（含 appId/APIKey，脱敏显示）【默认】")
        print("  list-scenes   查询场景列表并导出")
        print("  --help/-h     显示本帮助")
        print("\n注意: 命令会输出脱敏后的凭据信息，请勿在公开场合运行。")
        return

    # 1. 确保登录
    session = ensure_login()
    if not session:
        print("\n[错误] 登录失败，退出")
        return

    if command == "list-scenes":
        # 查询场景列表
        scenes = query_scenes(session)
        if not scenes:
            print("\n[提示] 没有找到场景。场景是基于应用创建的具体业务实例。")
            print("       若要查看应用列表，请运行: python tools/xfyun_query_services.py list-apps")
            return
        display_scenes(scenes, session)
        export_to_json(scenes, session)
    else:
        # 默认：查询所有应用
        apps = query_all_apps(session)
        if apps:
            display_apps(apps)
        else:
            print("\n[提示] 没有找到任何应用。请先在控制台创建应用：")
            print("       https://virtual-man.xfyun.cn/console/applications/subscribe")

    print("\n[完成] 查询完成！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户中断")
    except Exception as e:
        print(f"\n[错误] 发生错误: {e}")
        import traceback
        traceback.print_exc()
