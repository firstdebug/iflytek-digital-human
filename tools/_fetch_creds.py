"""
拉取指定讯飞应用的 appId/apiKey/apiSecret 到文件（密钥不回显）。
用法: python _fetch_creds.py <输出json路径> [appId]
  appId 省略时默认 YOUR_APP_ID。
凭据写入指定文件, 供 Android/Web 工程的 credentials.json 使用。
"""
import json, sys
# 复用 query_services 的正确登录与查询函数（ensure_login 已弃用，见 get_session/query_app_detail）
import xfyun_query_services as q

out_path = sys.argv[1] if len(sys.argv) > 1 else "app_creds.json"
app_id = sys.argv[2] if len(sys.argv) > 2 else "YOUR_APP_ID"

session = q.ensure_login()
if not session:
    print("LOGIN_FAILED"); sys.exit(1)

app = q.query_app_detail(session, app_id)
if not app:
    print("APP_NOT_FOUND"); sys.exit(1)

out = {
    "appId": app.get("appId"),
    "apiKey": app.get("apiKey"),
    "apiSecret": app.get("apiSecret"),
}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
# 仅打印脱敏确认，不回显完整密钥
print("OK appId=%s apiKey=%s... apiSecret=%s... -> %s" % (
    out["appId"], (out["apiKey"] or "")[:4], (out["apiSecret"] or "")[:3], out_path))
