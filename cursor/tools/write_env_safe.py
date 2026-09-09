#!/usr/bin/env python3
"""
安全写入 .env 文件工具
从平台 API 获取完整凭据并写入指定路径的 .env，密钥不打印到控制台
"""
import os
import sys
from pathlib import Path
from platform_endpoints import CANONICAL_WS_URL
import xfyun_common as xc
from xfyun_secrets import mask_secret


DEFAULT_AVATAR_ID = "111310001"
DEFAULT_VCN = "x4_lingxiaoqi_oral"
DEFAULT_WS_URL = CANONICAL_WS_URL


def find_app_record(records, app_id):
    """只返回与请求 appId 精确匹配的记录，避免误用其他应用的密钥。"""
    return next(
        (record for record in records if str(record.get("appId")) == str(app_id)),
        None,
    )


def resolve_output_path(output_path):
    """展开 ~ 和环境变量标记，同时保留相对路径语义。"""
    expanded = os.path.expandvars(os.path.expanduser(str(output_path)))
    return Path(expanded)


def build_env_content(
    app_id,
    api_key,
    api_secret,
    scene_id,
    avatar_id=DEFAULT_AVATAR_ID,
    vcn=DEFAULT_VCN,
    ws_url=DEFAULT_WS_URL,
    profile="xfyun",
):
    """按平台默认形象和发音人生成 .env 内容。

    Web SDK 使用未加前缀的变量名；其它历史工具继续使用 XF_*。
    """
    if profile not in ("xfyun", "web-sdk"):
        raise ValueError("profile must be xfyun or web-sdk")
    prefix = "" if profile == "web-sdk" else "XF_"
    lines = [
        "# 讯飞虚拟人 WebAPI 凭据",
        "# 自动生成，请勿提交到版本库",
        "",
        f"{prefix}APP_ID={app_id}",
        f"{prefix}API_KEY={api_key}",
        f"{prefix}API_SECRET={api_secret}",
        f"{prefix}SCENE_ID={scene_id}",
        f"{prefix}AVATAR_ID={avatar_id}",
        f"{prefix}VCN={vcn}",
        f"{prefix}WS_URL={ws_url}",
    ]
    return "\n".join(lines) + "\n"


def write_env(app_id, scene_id, output_path, profile="xfyun", ws_url=DEFAULT_WS_URL):
    """获取完整凭据并写入 .env"""
    print(f"[查询] 应用 {app_id} 的完整凭据...")

    # 获取已登录的会话
    session = xc.get_session()
    if not session:
        print("[错误] 无法获取登录会话")
        return False

    payload = {"current": 1, "size": 100, "appId": app_id}
    data = xc.post(
        session,
        "https://virtual-man.xfyun.cn/zs_web/app/query",
        payload,
    )
    if not data or not data.get("flag") or not data.get("data", {}).get("records"):
        print("[错误] 查询失败或无应用记录")
        return False

    records = data["data"]["records"]
    record = find_app_record(records, app_id)
    if not record:
        print(f"[错误] 返回结果中未找到 appId={app_id} 的精确匹配")
        return False

    api_key = record.get("apiKey")
    api_secret = record.get("apiSecret")
    if not api_key or not api_secret:
        print("[错误] 应用记录缺少 apiKey 或 apiSecret")
        return False

    # 脱敏显示确认
    print(f"[OK] API Key:    {mask_secret(api_key)}")
    print(f"[OK] API Secret: {mask_secret(api_secret)}")

    # 写入 .env（先建父目录，再原子替换，避免半写入文件）
    output_file = resolve_output_path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    env_content = build_env_content(
        app_id, api_key, api_secret, scene_id,
        ws_url=ws_url,
        profile=profile,
    )

    temp_file = output_file.with_name(f".{output_file.name}.tmp")
    temp_file.write_text(env_content, encoding="utf-8")
    temp_file.replace(output_file)
    try:
        output_file.chmod(0o600)
    except OSError:
        pass
    print(f"\n[完成] 凭据已写入: {output_file.absolute()}")
    print(f"[安全] 密钥未打印到控制台，仅存储在本地文件")
    return True

if __name__ == "__main__":
    if len(sys.argv) not in (4, 6):
        print("用法: python write_env_safe.py <app_id> <scene_id> <output_path> [--profile web-sdk|xfyun]")
        print("示例: python write_env_safe.py YOUR_APP_ID YOUR_SCENE_ID ~/.env --profile web-sdk")
        sys.exit(1)

    app_id = sys.argv[1]
    scene_id = sys.argv[2]
    output_path = sys.argv[3]
    profile = "xfyun"
    if len(sys.argv) == 6:
        if sys.argv[4] != "--profile" or sys.argv[5] not in ("web-sdk", "xfyun"):
            print("[错误] profile 参数必须是 web-sdk 或 xfyun")
            sys.exit(1)
        profile = sys.argv[5]

    if write_env(app_id, scene_id, output_path, profile=profile):
        sys.exit(0)
    else:
        sys.exit(1)
