# 应用授权检查

登录后立即检查用户订阅的应用,判断应用类型(appType)和授权情况(auths),避免后续集成到一半才发现授权不足或产品类型不对。

## 触发时机

`xfyun_common.py` 登录成功后(cookies 保存到 `xfyun_cookies.json`),**立即**调用此检查,**先于** `xfyun_query_services.py` 查询场景。

---

## 检查接口

**POST** `https://virtual-man.xfyun.cn/zs_web/app/query`

**请求头**:
```
Cookie: 从 xfyun_cookies.json 读取
Content-Type: application/json
```

**请求体**(空或分页参数):
```json
{
  "pageNum": 1,
  "pageSize": 100
}
```

**响应示例**(成功):
```json
{
  "code": "0",
  "data": {
    "list": [
      {
        "appId": "YOUR_APP_ID",
        "appName": "虚拟人接口能力-测试",
        "appType": 1,
        "isEffect": true,
        "auths": [
          {
            "authResource": "nlp",
            "authKey": "LLM_DIALOG_NUM",
            "licState": "valid",
            "leftValue": 1000
          },
          {
            "authResource": "nlp",
            "authKey": "LLM_DOC_NUM",
            "licState": "valid"
          }
        ]
      },
      {
        "appId": "a123b456",
        "appName": "虚拟人标准产品-直播",
        "appType": 2,
        "isEffect": true,
        "auths": [
          {
            "authResource": "product",
            "authKey": "WEB_CONVERSATION",
            "licState": "valid"
          },
          {
            "authResource": "product",
            "authKey": "DIGITAL_LIVE",
            "licState": "valid"
          }
        ]
      }
    ],
    "total": 2
  }
}
```

---

## 判断逻辑

### 1. 无应用(list 为空)

**判断**:`data.list` 为空数组 `[]` 或 `data.total === 0`

**处理**:
1. 提示:"检测到你还没有订阅虚拟人产品。你想做什么?"
2. 询问需求(多选或单选):
   - Web 对话模板 / 智能客服 / H5 / 大屏
   - 数字人直播 / 虚拟主播 / 带货
   - SDK 开发(Web/Android/iOS)
   - WebAPI 报文接入(后端直连)
3. 根据选择推荐订阅类型:
   - 选了 Web 模板/H5/大屏 → **标准产品**(appType=2),订阅时勾选【Web对话系统】
   - 选了数字人直播 → **标准产品**(appType=2),订阅时勾选【数字人直播】
   - 选了 SDK/WebAPI → **接口能力**(appType=1)
   - 需要大模型对话功能 → 打开 **大模型对话开关**(`LLM_DIALOG_NUM` / `LLM_DOC_NUM` / `LLM_TOKENS_NUM`)
4. 给订阅链接:[订阅页面](https://virtual-man.xfyun.cn/console/applications/subscribe)
5. **等待用户操作**:告诉他订阅后回来重新运行,任务暂停

---

### 2. 有应用,但过期或授权不足

#### 2.1 应用过期

**判断**:`isEffect === false`

**处理**:
- 提示:"应用「{appName}」已过期(isEffect=false),无法使用。"
- "需要重新订阅或续费。访问[订阅页面](https://virtual-man.xfyun.cn/console/applications/subscribe)处理。"
- 如果有其他有效应用,继续用其他的;全部过期则停止任务

#### 2.2 授权不足

**判断**:根据用户需求(从对话上下文推断或询问),检查 `auths` 数组:

| 用户需求 | 必需授权 | 判断方法 |
|---------|---------|---------|
| 大模型对话 / 知识库 / NLP | `nlp` | `auths` 里存在 `authResource="nlp"` 且 `licState="valid"` |
| Web 对话模板 | `WEB_CONVERSATION` + `PC_ASSISTANT` | `auths` 里存在 `authResource="product"` 且 `authKey` 分别为这两个,`licState="valid"` (网页显示为【Web对话系统】) |
| 数字人直播 | `DIGITAL_LIVE` | `auths` 里存在 `authResource="product"` 且 `authKey="DIGITAL_LIVE"`,`licState="valid"` (网页显示为【数字人直播】) |
| SDK/WebAPI(基础驱动) | 无额外授权 | appType=1 即可 |

**处理**(以缺 nlp 为例):
- 提示:"你的应用「{appName}」(appId={appId})缺少大模型对话授权,无法使用大模型对话功能。"
- "当前授权列表:{列出 auths 里的 authKey}"
- "需要重新创建一个应用,订阅时记得打开 **大模型对话开关**(LLM_DIALOG_NUM / LLM_DOC_NUM / LLM_TOKENS_NUM)。"
- 给订阅链接:[订阅页面](https://virtual-man.xfyun.cn/console/applications/subscribe)
- **等待用户操作**:订阅新应用后回来重新运行

---

### 3. 应用正常,授权齐全

**判断**:
- `isEffect === true`
- `appType` 与需求匹配(1=接口能力 / 2=标准产品)
- 必需的 `auths` 都存在且 `licState="valid"`

**处理**:
1. 提示:"✅ 应用检查通过"
   - appId: {appId}
   - appName: {appName}
   - appType: {1=接口能力 / 2=标准产品}
   - 授权: {列出关键的 authKey,如 nlp / WEB_CONVERSATION / DIGITAL_LIVE}
2. **存储到上下文或文件**:
   - `appId` / `appType` / `auths`(后续流程可能用到)
3. 继续下一步:调用 `xfyun_query_services.py` 查询场景

---

## 实现建议(Python 伪代码)

```python
import requests, json

def check_app_authorization(cookies_path="xfyun_cookies.json"):
    # 1. 读 cookies
    with open(cookies_path) as f:
        cookies = json.load(f)
    
    # 2. 调接口
    resp = requests.post(
        "https://virtual-man.xfyun.cn/zs_web/app/query",
        json={"pageNum": 1, "pageSize": 100},
        cookies=cookies
    )
    data = resp.json()
    
    if data["code"] != "0":
        print(f"查询应用失败: {data}")
        return None
    
    apps = data["data"]["list"]
    
    # 3. 无应用
    if not apps:
        print("❌ 未检测到任何应用")
        # 询问需求 → 推荐订阅类型 → 给链接
        return None
    
    # 4. 过滤有效应用
    valid_apps = [a for a in apps if a["isEffect"]]
    if not valid_apps:
        print("❌ 所有应用均已过期")
        return None
    
    # 5. 判断授权(假设需求是"大模型对话")
    for app in valid_apps:
        has_nlp = any(
            auth["authResource"] == "nlp" and auth["licState"] == "valid"
            for auth in app.get("auths", [])
        )
        if has_nlp:
            print(f"✅ 应用检查通过: {app['appName']} (appId={app['appId']})")
            print(f"   授权: nlp(大模型对话)")
            return app  # 返回第一个匹配的应用
    
    # 6. 授权不足
    print(f"❌ 应用「{valid_apps[0]['appName']}」缺少大模型对话授权")
    print("当前授权:", [a["authKey"] for a in valid_apps[0].get("auths", [])])
    print("请重新订阅,记得打开大模型对话开关")
    return None

# 调用
app = check_app_authorization()
if app:
    # 继续查询场景
    pass
else:
    # 停止,等用户订阅
    pass
```

---

## 关键字段说明

| 字段 | 含义 | 取值 |
|------|------|------|
| `appType` | 产品类型 | 1=接口能力(API),2=标准产品(Web模板/直播) |
| `isEffect` | 是否有效(未过期) | true/false |
| `authResource` | 授权资源类型 | `nlp`(大模型) / `product`(标准产品功能) |
| `authKey` | 具体授权项 | `LLM_DIALOG_NUM` / `WEB_CONVERSATION` / `DIGITAL_LIVE` 等 |
| `licState` | 授权状态 | `valid`(有效) / `invalid`(过期) |
| `leftValue` | 剩余配额(可选) | 数字,如剩余对话轮次 |

---

## 常见授权组合

| 场景 | appType | 必需 authKey |
|------|---------|-------------|
| Web 对话模板 | 2 | `WEB_CONVERSATION` + `PC_ASSISTANT` |
| 数字人直播 | 2 | `DIGITAL_LIVE` |
| SDK 基础驱动(文本/音频) | 1 | 无(基础功能) |
| SDK + 大模型对话 | 1 | `nlp`(LLM_DIALOG_NUM) |
| SDK + 知识库 | 1 | `nlp`(LLM_DOC_NUM) |
| WebAPI 报文接入 | 1 | 无(基础功能) |

---

> 本文档是 avatar-credentials skill 新增的核心逻辑。凭据获取流程见 `console-setup-guide.md`,格式验证见 `validation.md`。
