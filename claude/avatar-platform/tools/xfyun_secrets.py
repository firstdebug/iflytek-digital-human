"""
讯飞虚拟人 - 密钥安全管理模块
功能：本地加密存储、脱敏显示、交互式输入
"""
import getpass
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet


# ==================== 配置 ====================
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def resolve_secrets_dir():
    """密钥目录默认在插件根目录 .runtime/secrets，可用环境变量覆盖。"""
    override = os.environ.get("XFYUN_AVATAR_SECRETS_DIR")
    if override:
        return Path(os.path.expandvars(os.path.expanduser(override))).resolve()
    return PLUGIN_ROOT / ".runtime" / "secrets"


SECRETS_DIR = resolve_secrets_dir()
MASTER_KEY_FILE = SECRETS_DIR / "master.key"
SECRETS_FILE = SECRETS_DIR / "secrets.enc"

# 需要脱敏的字段名（不区分大小写）
SENSITIVE_FIELDS = {
    "apikey", "apisecret", "apiurl", "api_key", "api_secret",
    "base_url", "baseurl", "token", "password", "secret"
}


# ==================== 脱敏显示 ====================
def mask_secret(value, show_prefix=4, show_suffix=4):
    """
    脱敏显示：sk-1234****abcd
    只显示前后几位，中间打星号

    show_prefix/show_suffix 为 0 时该侧完全不显示，绝不回退成原值。
    """
    if not value:
        return ""
    if not isinstance(show_prefix, int) or not isinstance(show_suffix, int):
        raise TypeError("show_prefix and show_suffix must be integers")
    if show_prefix < 0 or show_suffix < 0:
        raise ValueError("show_prefix and show_suffix must be non-negative")
    value_str = str(value)
    if len(value_str) <= show_prefix + show_suffix:
        return "*" * len(value_str)
    prefix = value_str[:show_prefix] if show_prefix else ""
    suffix = value_str[-show_suffix:] if show_suffix else ""
    return f"{prefix}{'*' * 8}{suffix}"


def mask_dict(data, depth=3):
    """
    递归脱敏字典中的敏感字段
    depth 限制递归深度，防止循环引用
    """
    if depth <= 0 or not isinstance(data, dict):
        return data

    masked = {}
    for key, value in data.items():
        key_lower = str(key).lower()
        if key_lower in SENSITIVE_FIELDS:
            masked[key] = mask_secret(value)
        elif isinstance(value, dict):
            masked[key] = mask_dict(value, depth - 1)
        elif isinstance(value, list):
            masked[key] = [mask_dict(item, depth - 1) if isinstance(item, dict) else item
                          for item in value]
        else:
            masked[key] = value
    return masked


# ==================== 加密存储 ====================
def _ensure_master_key():
    """确保主密钥存在，不存在则生成"""
    if not MASTER_KEY_FILE.exists():
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        MASTER_KEY_FILE.write_bytes(Fernet.generate_key())
        MASTER_KEY_FILE.chmod(0o600)  # 只有所有者可读写


def _get_cipher():
    """获取加密器"""
    _ensure_master_key()
    return Fernet(MASTER_KEY_FILE.read_bytes())


def save_secret(key_id, value):
    """加密保存密钥"""
    cipher = _get_cipher()
    secrets = load_all_secrets()
    secrets[key_id] = cipher.encrypt(str(value).encode()).decode()
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_FILE.write_text(json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8")
    SECRETS_FILE.chmod(0o600)


def load_all_secrets():
    """加载所有加密密钥（仍为加密状态）"""
    if SECRETS_FILE.exists():
        try:
            return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_secret(key_id):
    """解密获取密钥（仅在需要时调用，不打印）"""
    try:
        cipher = _get_cipher()
        secrets = load_all_secrets()
        encrypted = secrets.get(key_id)
        if not encrypted:
            return None
        return cipher.decrypt(encrypted.encode()).decode()
    except Exception as e:
        print(f"[错误] 解密失败: {e}")
        return None


def list_secret_ids():
    """列出所有已存储的密钥ID（不解密）"""
    return list(load_all_secrets().keys())


# ==================== 交互式输入 ====================
def prompt_secret(prompt_text, key_id=None, save_local=True):
    """
    交互式输入密钥，支持两种方式：
    1. 交互式输入（不回显，支持粘贴）
    2. 从文件读取
    """
    print(f"\n{prompt_text}")
    print("\n请选择输入方式：")
    print("  1. 交互式输入（支持粘贴，输入时不显示）")
    print("  2. 从文件读取（密钥保存在文本文件中）")

    choice = input("\n选择 (1/2，默认1): ").strip() or "1"

    if choice == "2":
        # 方式2：从文件读取
        while True:
            file_path_str = input("请输入密钥文件路径（如 temp_key.txt 或拖拽文件到此）: ").strip()
            # 去除可能的引号（拖拽文件时可能带引号）
            file_path_str = file_path_str.strip('"').strip("'")
            file_path = Path(file_path_str)

            if not file_path.exists():
                retry = input(f"[错误] 文件不存在: {file_path}\n重新输入？(y/n): ").strip().lower()
                if retry not in ('y', 'yes', '是', ''):
                    print("[取消] 已取消输入")
                    return None
                continue

            try:
                value = file_path.read_text(encoding='utf-8').strip()
                if not value:
                    print("[错误] 文件为空")
                    continue

                # 显示脱敏版本确认
                masked = mask_secret(value, show_prefix=6, show_suffix=4)
                confirm = input(f"\n读取到密钥: {masked}\n确认正确？(y/n): ").strip().lower()

                if confirm in ('y', 'yes', '是', ''):
                    # 询问是否删除文件
                    del_confirm = input(f"\n是否删除密钥文件 {file_path.name}？(y/n，推荐y): ").strip().lower()
                    if del_confirm in ('y', 'yes', '是', ''):
                        try:
                            file_path.unlink()
                            print(f"[已删除] {file_path}")
                        except Exception as e:
                            print(f"[警告] 删除文件失败: {e}")

                    if save_local and key_id:
                        save_secret(key_id, value)
                        print(f"[已保存] 密钥已加密存储，引用ID: {key_id}")
                    return value
                else:
                    print("[提示] 请重新选择输入方式")
                    return prompt_secret(prompt_text, key_id, save_local)

            except Exception as e:
                print(f"[错误] 读取文件失败: {e}")
                continue

    else:
        # 方式1：交互式输入（不回显）
        while True:
            value = getpass.getpass("请粘贴或输入密钥（输入时不显示）: ")
            if not value:
                retry = input("[错误] 密钥不能为空，重新输入？(y/n): ").strip().lower()
                if retry not in ('y', 'yes', '是', ''):
                    print("[取消] 已取消输入")
                    return None
                continue

            # 显示脱敏版本让用户确认
            masked = mask_secret(value, show_prefix=6, show_suffix=4)
            confirm = input(f"\n密钥已输入: {masked}\n确认正确？(y/n): ").strip().lower()

            if confirm in ('y', 'yes', '是', ''):
                if save_local and key_id:
                    save_secret(key_id, value)
                    print(f"[已保存] 密钥已加密存储，引用ID: {key_id}")
                return value
            else:
                print("[提示] 请重新输入密钥")


# ==================== 工具函数 ====================
def get_or_prompt(key_id, prompt_text):
    """先尝试从本地读，没有则交互式输入"""
    value = get_secret(key_id)
    if value:
        print(f"[使用] 本地存储的密钥: {key_id}")
        return value
    return prompt_secret(prompt_text, key_id, save_local=True)
