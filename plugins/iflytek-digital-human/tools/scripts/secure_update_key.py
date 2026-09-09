"""
安全更新模型密钥脚本

用法:
    python secure_update_key.py <模型名或ID> [密钥文件路径]

流程:
    1. 从密钥文件读取新 apiKey（默认读同目录上级的 密钥待填写.txt）
    2. 只显示脱敏版本，不打印完整密钥
    3. 用 PUT 方法更新模型
    4. 成功后立即删除密钥文件

密钥文件格式（任选其一）:
    API_KEY=sk-xxxxxx          # 带前缀
    sk-xxxxxx                  # 纯密钥
"""
import sys
from pathlib import Path

# 把工具包根目录（本文件的上级）加入 import 路径
TOOLS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS_DIR))

import xfyun_model_manage as xmm
import xfyun_common as xc
import xfyun_secrets as xs

# ---- 参数解析 ----
if len(sys.argv) < 2:
    print("用法: python secure_update_key.py <模型名或ID> [密钥文件路径]")
    sys.exit(1)

target = sys.argv[1]
key_file = Path(sys.argv[2]) if len(sys.argv) > 2 else (TOOLS_DIR / "密钥待填写.txt")

# ---- 读取密钥 ----
if not key_file.exists():
    print(f"[错误] 密钥文件不存在: {key_file}")
    sys.exit(1)

content = key_file.read_text(encoding='utf-8').strip()
new_api_key = content.split('API_KEY=')[1].strip() if 'API_KEY=' in content else content.strip()

if not new_api_key or '请在这里粘贴' in new_api_key:
    print("[错误] 密钥未填写或格式不正确")
    sys.exit(1)

# ---- 找到目标模型 ----
session = xc.get_session()
models = xmm.list_models(session)
model = next((m for m in models
             if str(m.get('id')) == str(target) or m.get('name') == target), None)

if not model:
    print(f"[错误] 未找到模型: {target}")
    print("可用自有模型:", [(m.get('id'), m.get('name'))
                          for m in models if m.get('modelType') == 2])
    sys.exit(1)

if model.get('modelType') != 2:
    print("[错误] 只能更新自有模型（modelType=2）")
    sys.exit(1)

print(f"[修改模型] {model.get('name')} (id={model.get('id')})")
print(f"[新密钥] {xs.mask_secret(new_api_key, show_prefix=6, show_suffix=4)}")

# ---- 构建更新负载并提交（PUT）----
payload = {
    "id": model.get("id"),
    "name": model.get("name"),
    "model": model.get("model"),
    "introduce": model.get("introduce"),
    "apiUrl": model.get("apiUrl"),
    "apiKey": new_api_key,          # 真实密钥，不打印
    "domain": model.get("domain"),
    "protocol": model.get("protocol", 2),
    "uid": model.get("uid"),
    "modelType": 2,
    "dataStatus": model.get("dataStatus", 1),
    "createTime": model.get("createTime"),
    "updateTime": model.get("updateTime"),
}

data = xc.put(session, xmm.API_MODEL_UPDATE, payload, debug=False)

if data and data.get("flag"):
    print("[OK] 模型更新成功")
    try:
        key_file.unlink()
        print("[安全] 密钥文件已删除")
    except Exception as e:
        print(f"[警告] 删除文件失败: {e}，请手动删除")
else:
    print(f"[失败] {data.get('desc') if data else '无响应'}")
    print("[提示] 密钥文件未删除，请检查后手动删除")
