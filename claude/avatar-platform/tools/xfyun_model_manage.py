"""
讯飞虚拟人 - 模型管理工具

命令：
  python xfyun_model_manage.py probe                探测各接口结构
  python xfyun_model_manage.py list                 列出所有模型（含 modelType）
  python xfyun_model_manage.py scenes               列出所有场景
  python xfyun_model_manage.py create <name> <model> <introduce> <apiUrl>
                                                     创建自有模型（apiKey交互式输入，加密存储）
  python xfyun_model_manage.py update <model_id或name>
                                                     修改自有模型（交互式选择要改的字段）
  python xfyun_model_manage.py caps                 检查所有 app 的大模型对话能力
  python xfyun_model_manage.py check <sceneId>      检查某场景是否有对话能力
  python xfyun_model_manage.py query <sceneId>      查询某场景当前 NLP 配置
  python xfyun_model_manage.py query-interact <sceneId>
                                                     查询某场景的 interact 高级配置
                                                     (IAT识别/交互模式/唤醒词/引导语等)
  python xfyun_model_manage.py bind <sceneId> <modelName> [systemPrompt]
                                                     把某模型绑定到场景并保存配置
                                                     （无对话能力的 app 会被直接拒绝）
  python xfyun_model_manage.py update-interact <sceneId> [key=value ...]
                                                     更新场景的 interact 高级配置
                                                     示例: update-interact 123 iatType=10002 defaultReply="Sorry"
  python xfyun_model_manage.py publish <sceneId>     发布场景配置（让配置生效，必须执行）

说明：
  - 模型区分官方(modelType=1)与自有(modelType=2)
  - 绑定自有模型时 nlpType/value = "openai"，否则 = "xinghuo"
  - nlpExtra 里的 apiKey/baseUrl：自有模型取模型自身的 apiKey/apiUrl；
    官方模型留空（走讯飞内部）
  - 能力判定：app 的 auths 含 LLM_TOKENS_NUM/LLM_DIALOG_NUM/LLM_DOC_NUM
    之一且未过期，才认定有大模型对话能力

安全特性：
  - 所有密钥字段（apiKey/apiSecret/apiUrl）自动脱敏显示
  - 创建模型时密钥交互式输入（不回显）并加密存储到 `<plugin-root>/.runtime/secrets/secrets.enc`
  - debug 输出自动过滤敏感字段
"""
import sys

# Windows 下强制 stdout/stderr 使用 UTF-8，避免中文输出乱码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

import time
import json
import xfyun_common as xc
import xfyun_secrets as xs

# ==================== API 端点 ====================
API_MODEL_CREATE = "https://virtual-man.xfyun.cn/zs_web/model/create"
API_MODEL_LIST = "https://virtual-man.xfyun.cn/zs_web/model/list"
API_MODEL_UPDATE = "https://virtual-man.xfyun.cn/zs_web/model/info"  # 使用 PUT 方法
API_NLP_QUERY = "https://virtual-man.xfyun.cn/zs_web/nlp/query"
API_NLP_UPSERT = "https://virtual-man.xfyun.cn/zs_web/nlp/createOrUpdate"
API_INTERACT_QUERY = "https://virtual-man.xfyun.cn/zs_web/interact/query"
API_INTERACT_UPSERT = "https://virtual-man.xfyun.cn/zs_web/interact/createOrUpdate"
API_SCENE_QUERY = "https://virtual-man.xfyun.cn/zs_web/scene/query"
API_SCENE_PUBLISH = "https://virtual-man.xfyun.cn/zs_web/scene/publish"
API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"

# 大模型对话能力的授权 key：auths 里含其中任一且未过期，才说明有对话能力
LLM_AUTH_KEYS = {"LLM_TOKENS_NUM", "LLM_DIALOG_NUM", "LLM_DOC_NUM"}

# nlpExtra 默认参数（可按需覆盖）
DEFAULT_TEMPERATURE = 0.5   # 0.01 - 1
DEFAULT_MAX_TOKENS = 4000   # 5 - 5000
DEFAULT_HISTORY_TIMES = 20  # 1 - 100
DEFAULT_SYSTEM_PROMPT = (
    "- 角色：知识顾问\n"
    "- 背景：用户需要获取信息或解决特定问题。\n"
    "- 目标：为用户提供准确、有用的信息或解决方案。\n"
    "- 初始化：欢迎咨询，我是您的知识顾问。请告诉我您需要帮助的具体问题。"
)


# ==================== 场景 & 模型查询 ====================
def query_scenes(session):
    data = xc.post(session, API_SCENE_QUERY, {
        "sceneType": 1, "sceneStatus": 1, "sceneTypeList": None, "__times": 0
    })
    return data.get("data", []) if data and data.get("flag") else []


def list_models(session, debug=False):
    uid = getattr(session, "uid", "")
    data = xc.get(session, API_MODEL_LIST, params={"uid": uid}, debug=debug)
    if not data or not data.get("flag"):
        print(f"[失败] {data.get('desc') if data else '无响应'}")
        return []
    payload = data.get("data")
    if isinstance(payload, dict):
        return payload.get("records", [])
    return payload if isinstance(payload, list) else []


def find_model(models, name_or_model):
    """按 name / model / domain 匹配一个模型"""
    for m in models:
        if name_or_model in (m.get("name"), m.get("model"), m.get("domain")):
            return m
    return None


def query_nlp(session, scene_id, debug=False):
    data = xc.post(session, API_NLP_QUERY, {"sceneId": scene_id}, debug=debug)
    if not data or not data.get("flag"):
        return None
    return data.get("data")


def query_interact(session, scene_id, debug=False):
    """查询场景的 interact 配置（IAT识别/交互模式/唤醒词/引导语等）"""
    data = xc.post(session, API_INTERACT_QUERY, {"sceneId": scene_id}, debug=debug)
    if not data or not data.get("flag"):
        return None
    payload = data.get("data")
    # 返回可能是单个 dict 或 list，统一处理
    if isinstance(payload, list) and payload:
        return payload[0]
    return payload if isinstance(payload, dict) else None


def publish_scene(session, scene_id):
    """发布场景配置（让配置生效）"""
    data = xc.post(session, API_SCENE_PUBLISH, {"sceneId": scene_id})
    if data and data.get("flag"):
        return True
    return False


def query_apps(session, debug=False):
    """查询所有 app（含 auths 授权明细）"""
    data = xc.post(session, API_APP_QUERY, {
        "pageSize": 30, "pageNum": 1, "assetName": "", "t": 0
    }, debug=debug)
    if not data or not data.get("flag"):
        return []
    payload = data.get("data") or {}
    return payload.get("records", [])


def get_app_by_id(session, app_id):
    """按 appId 找到对应 app 记录"""
    for app in query_apps(session):
        if app.get("appId") == app_id:
            return app
    return None


def check_llm_capability(app):
    """
    判断 app 是否具备大模型对话能力：
    auths 里含 LLM_TOKENS_NUM / LLM_DIALOG_NUM / LLM_DOC_NUM 之一，
    且该授权未过期（licState=valid 且 effectEtime > 当前时间）。
    返回 (has_capability: bool, valid_auths: list)
    """
    now_ms = int(time.time() * 1000)
    valid = []
    for auth in (app.get("auths") or []):
        key = auth.get("authKey")
        if key not in LLM_AUTH_KEYS:
            continue
        # 未过期判定：licState 不为 invalid，且 effectEtime 在未来（或无限期）
        lic_ok = auth.get("licState") != "invalid"
        etime = auth.get("effectEtime")
        time_ok = (etime is None) or (etime > now_ms)
        status_ok = auth.get("authStatus") == 1
        if lic_ok and time_ok and status_ok:
            valid.append(auth)
    return (len(valid) > 0, valid)


# ==================== 命令实现 ====================
def cmd_list(session):
    models = list_models(session)
    print(f"\n[模型列表] 共 {len(models)} 个：\n")
    print(f"{'id':<8}{'name':<16}{'model/domain':<18}{'type':<8}{'说明'}")
    print("-" * 70)
    for m in models:
        mtype = "自有(2)" if m.get("modelType") == 2 else "官方(1)"
        api_url = m.get('apiUrl', '')
        # 自有模型的 apiUrl 可能是敏感的，脱敏显示
        if m.get("modelType") == 2 and api_url:
            api_url = xs.mask_secret(api_url, show_prefix=8, show_suffix=0)
        print(f"{str(m.get('id')):<8}{str(m.get('name'))[:14]:<16}"
              f"{str(m.get('domain')):<18}{mtype:<8}"
              f"apiUrl={api_url}")


def cmd_scenes(session):
    scenes = query_scenes(session)
    print(f"\n[场景列表] 共 {len(scenes)} 个：\n")
    for s in scenes:
        print(f"  {s.get('sceneName')} | sceneId={s.get('sceneId')} | appId={s.get('appId')}")


def cmd_caps(session):
    """检查所有 app 的大模型对话能力"""
    apps = query_apps(session)
    print(f"\n[能力检查] 共 {len(apps)} 个 app：\n")
    for app in apps:
        has_llm, valid_auths = check_llm_capability(app)
        status = "有对话能力" if has_llm else "无对话能力"
        print(f"  [{'YES' if has_llm else 'NO '}] {app.get('appName')} "
              f"(appId={app.get('appId')}) -> {status}")
        all_keys = [a.get("authKey") for a in (app.get("auths") or [])]
        print(f"       全部授权: {all_keys}")
        if has_llm:
            print(f"       命中 LLM 授权: {[a.get('authKey') for a in valid_auths]}")


def cmd_check(session, scene_id):
    """检查指定场景对应 app 是否有对话能力"""
    scenes = query_scenes(session)
    scene = next((s for s in scenes if str(s.get("sceneId")) == str(scene_id)), None)
    if not scene:
        print(f"[错误] 未找到场景：{scene_id}")
        return
    app_id = scene.get("appId")
    app = get_app_by_id(session, app_id)
    if not app:
        print(f"[错误] 未找到 app（appId={app_id}）")
        return
    has_llm, valid_auths = check_llm_capability(app)
    print(f"\n场景「{scene.get('sceneName')}」(sceneId={scene_id})")
    print(f"  -> app「{app.get('appName')}」(appId={app_id})")
    if has_llm:
        print(f"  [结果] 有对话能力，命中授权: {[a.get('authKey') for a in valid_auths]}")
    else:
        all_keys = [a.get("authKey") for a in (app.get("auths") or [])]
        print(f"  [结果] 无对话能力")
        print(f"         现有授权: {all_keys}")
        print(f"         需要以下任一且未过期: {sorted(LLM_AUTH_KEYS)}")


def cmd_create(session, name, model, introduce, api_url):
    """
    创建自有模型（交互式输入密钥，不回显）
    密钥自动加密存储到本地
    """
    print(f"\n[创建模型] name={name}, model={model}")
    print(f"  introduce: {introduce}")
    print(f"  apiUrl:    {api_url}")

    # 交互式输入密钥（不回显）
    key_id = f"model_{name}_{int(time.time())}"
    api_key = xs.prompt_secret(
        f"请输入模型 {name} 的 API Key",
        key_id=key_id,
        save_local=True
    )

    # 调用接口（不打印敏感信息）
    data = xc.post(session, API_MODEL_CREATE, {
        "name": name,
        "model": model,
        "introduce": introduce,
        "apiUrl": api_url,
        "apiKey": api_key,
    }, debug=False)  # 关闭 debug 防止打印请求体

    if data and data.get("flag"):
        print(f"[OK] 模型创建成功，密钥已加密存储（引用ID: {key_id}）")
    else:
        print(f"[失败] {data.get('desc') if data else '无响应'}")


def cmd_update(session, model_identifier):
    """
    更新自有模型信息（交互式）
    model_identifier: 模型 id 或 name
    """
    # 1. 找到目标模型
    models = list_models(session)
    model = None
    for m in models:
        if str(m.get("id")) == str(model_identifier) or m.get("name") == model_identifier:
            model = m
            break

    if not model:
        print(f"[错误] 未找到模型：{model_identifier}")
        print("可用模型：", [(m.get("id"), m.get("name")) for m in models if m.get("modelType") == 2])
        return

    if model.get("modelType") != 2:
        print(f"[错误] 只能修改自有模型（modelType=2），该模型是官方模型")
        return

    print(f"\n[修改模型] {model.get('name')} (id={model.get('id')})")
    print("当前配置：")
    print(f"  名称:     {model.get('name')}")
    print(f"  标识:     {model.get('model')}")
    print(f"  介绍:     {model.get('introduce')}")
    print(f"  API地址:  {xs.mask_secret(model.get('apiUrl'), show_prefix=20, show_suffix=0)}")
    print(f"  API Key:  {xs.mask_secret(model.get('apiKey'), show_prefix=6, show_suffix=4) if model.get('apiKey') else '(未设置)'}")

    # 2. 交互式选择要修改的字段
    print("\n请选择要修改的字段（多选用逗号分隔，如 1,3,4）：")
    print("  1. 名称 (name)")
    print("  2. 标识 (model)")
    print("  3. 介绍 (introduce)")
    print("  4. API地址 (apiUrl)")
    print("  5. API Key")
    print("  0. 全部保持不变")

    choice = input("\n选择 (如 1,4,5): ").strip()
    if choice == "0" or not choice:
        print("[取消] 未修改任何字段")
        return

    choices = [c.strip() for c in choice.split(',')]

    # 3. 构建更新负载（从现有模型复制所有必需字段）
    payload = {
        "id": model.get("id"),
        "name": model.get("name"),
        "model": model.get("model"),
        "introduce": model.get("introduce"),
        "apiUrl": model.get("apiUrl"),
        "apiKey": model.get("apiKey", ""),
        "domain": model.get("domain"),
        "protocol": model.get("protocol", 2),
        "uid": model.get("uid"),
        "modelType": 2,
        "dataStatus": model.get("dataStatus", 1),
        "createTime": model.get("createTime"),
        "updateTime": model.get("updateTime"),
    }

    # 4. 根据用户选择更新字段
    if "1" in choices:
        new_name = input(f"新名称 (当前: {payload['name']}): ").strip()
        if new_name:
            payload["name"] = new_name

    if "2" in choices:
        new_model = input(f"新标识 (当前: {payload['model']}): ").strip()
        if new_model:
            payload["model"] = new_model
            payload["domain"] = new_model

    if "3" in choices:
        new_intro = input(f"新介绍 (当前: {payload['introduce']}): ").strip()
        if new_intro:
            payload["introduce"] = new_intro

    if "4" in choices:
        new_url = input(f"新API地址 (当前: {payload['apiUrl']}): ").strip()
        if new_url:
            payload["apiUrl"] = new_url

    if "5" in choices:
        print("\n[更新 API Key]")
        key_id = f"model_{payload['name']}_updated_{int(time.time())}"
        new_key = xs.prompt_secret(
            f"请输入模型 {payload['name']} 的新 API Key",
            key_id=key_id,
            save_local=True
        )
        if new_key:
            payload["apiKey"] = new_key

    # 5. 提交更新（使用 PUT 方法）
    print("\n[提交] 更新模型配置...")
    data = xc.put(session, API_MODEL_UPDATE, payload, debug=False)

    if data and data.get("flag"):
        print("[OK] 模型更新成功")
    else:
        print(f"[失败] {data.get('desc') if data else '无响应'}")


def cmd_query(session, scene_id):
    print(f"\n[查询NLP配置] sceneId={scene_id}")
    nlp = query_nlp(session, scene_id, debug=True)
    if not nlp:
        print("[空] 该场景暂无 NLP 配置（首次绑定将创建新配置）")
        return
    # nlp 可能是 list（多条配置）
    items = nlp if isinstance(nlp, list) else [nlp]
    for it in items:
        print(f"\n  id={it.get('id')}, label={it.get('label')}, "
              f"nlpType={it.get('nlpType')}, value={it.get('value')}")
        extra = it.get("nlpExtra")
        if extra:
            try:
                print("  nlpExtra:", json.dumps(json.loads(extra), ensure_ascii=False, indent=2))
            except Exception:
                print("  nlpExtra:", extra)


def cmd_query_interact(session, scene_id):
    """查询场景的 interact 高级配置"""
    print(f"\n[查询 interact 配置] sceneId={scene_id}")
    interact = query_interact(session, scene_id, debug=True)
    if not interact:
        print("[空] 该场景暂无 interact 配置")
        return

    print("\n关键字段摘要：")
    print(f"  id:                  {interact.get('id')}")
    print(f"  nlpAssistantInfo:    {interact.get('nlpAssistantInfo')}")
    print(f"  defaultReply:        {interact.get('defaultReply')}")
    print(f"  iatType:             {interact.get('iatType')} (识别语言)")
    print(f"  iatHotWord:          {interact.get('iatHotWord')}")
    print(f"  interactionMode:     {interact.get('interactionMode')} (交互模式)")
    print(f"  nicknameQualifier:   {interact.get('nicknameQualifier')} (唤醒词)")
    print(f"  nicknameResponse:    {interact.get('nicknameResponse')}")
    print(f"  welcomeMessage:      {interact.get('welcomeMessage')}")
    print(f"  guideQuestionInfo:   {interact.get('guideQuestionInfo')}")
    print(f"  interactStatus:      {interact.get('interactStatus')} (0=草稿,1=已发布)")


def cmd_update_interact(session, scene_id, **kwargs):
    """
    更新场景的 interact 高级配置（完整字段版）
    kwargs 支持：iatType, iatHotWord, interactionMode, nicknameQualifier,
                welcomeMessage, defaultReply, guideQuestionInfo 等
    """
    # 先查现有配置，作为基础
    existing = query_interact(session, scene_id)
    if not existing:
        print("[错误] 场景无 interact 配置，请先用 bind 创建基础配置")
        return

    # 用 kwargs 覆盖现有值
    payload = {
        "id": existing.get("id"),
        "sceneId": scene_id,
        "dataStatus": existing.get("dataStatus", 1),
        "interactStatus": existing.get("interactStatus", 0),
        "createTime": existing.get("createTime"),
        "updateTime": existing.get("updateTime"),

        "iatType": kwargs.get("iatType", existing.get("iatType")),
        "iatHotWord": kwargs.get("iatHotWord", existing.get("iatHotWord")),
        "correctWordStr": kwargs.get("correctWordStr", existing.get("correctWordStr")),
        "bos": kwargs.get("bos", existing.get("bos", 500)),
        "eos": kwargs.get("eos", existing.get("eos", 500)),
        "iatResId": kwargs.get("iatResId", existing.get("iatResId", "")),

        "interactionMode": kwargs.get("interactionMode", existing.get("interactionMode")),
        "nicknameQualifier": kwargs.get("nicknameQualifier", existing.get("nicknameQualifier")),
        "nicknameResponse": kwargs.get("nicknameResponse", existing.get("nicknameResponse")),
        "wakeupQualifier": kwargs.get("wakeupQualifier", existing.get("wakeupQualifier")),

        "nlpAssistantInfo": kwargs.get("nlpAssistantInfo", existing.get("nlpAssistantInfo")),
        "nlpDetail": existing.get("nlpDetail"),
        "xinghuoAppId": kwargs.get("xinghuoAppId", existing.get("xinghuoAppId", "")),
        "appLlmInfo": existing.get("appLlmInfo", ""),

        "welcomeMessage": kwargs.get("welcomeMessage", existing.get("welcomeMessage", "")),
        "guideQuestionInfo": kwargs.get("guideQuestionInfo", existing.get("guideQuestionInfo", "")),
        "defaultReply": kwargs.get("defaultReply", existing.get("defaultReply", "")),
        "hibernationInfo": existing.get("hibernationInfo", ""),

        "ttsHotWord": kwargs.get("ttsHotWord", existing.get("ttsHotWord")),
        "semanticGate": existing.get("semanticGate"),
        "isMultimodal": existing.get("isMultimodal", 0),
        "multimodalDetail": existing.get("multimodalDetail", ""),
        "appStatus": existing.get("appStatus"),
        "noSwitchType": existing.get("noSwitchType", 0),
        "relationSceneTemplateId": existing.get("relationSceneTemplateId", 1),
    }

    print(f"\n[更新 interact 配置] 提交完整字段...")
    print("  修改的参数:", {k: v for k, v in kwargs.items()})
    r = xc.post(session, API_INTERACT_UPSERT, payload, debug=True)
    if r and r.get("flag"):
        print("[OK] interact 配置已更新")
    else:
        print(f"[失败] {r.get('desc') if r else '无响应'}")


def cmd_publish(session, scene_id):
    """发布场景配置，让配置生效"""
    scenes = query_scenes(session)
    scene = next((s for s in scenes if str(s.get("sceneId")) == str(scene_id)), None)
    if not scene:
        print(f"[错误] 未找到场景：{scene_id}")
        return

    print(f"\n[发布] 场景「{scene.get('sceneName')}」(sceneId={scene_id})")
    if publish_scene(session, scene_id):
        print("[OK] 场景配置已发布，配置现已生效！")
    else:
        print("[失败] 发布失败，配置未生效")


def cmd_bind(session, scene_id, model_name, system_prompt=None):
    """把指定模型绑定到场景，写入 nlp 配置并保存交互配置"""
    # 0. 【能力闸门】先确认该场景对应的 app 具备大模型对话能力，否则直接拒绝
    scenes = query_scenes(session)
    scene = next((s for s in scenes if str(s.get("sceneId")) == str(scene_id)), None)
    if not scene:
        print(f"[错误] 未找到场景：{scene_id}")
        return
    app_id = scene.get("appId")
    app = get_app_by_id(session, app_id)
    if not app:
        print(f"[错误] 未找到场景对应的 app（appId={app_id}）")
        return

    has_llm, valid_auths = check_llm_capability(app)
    if not has_llm:
        auth_keys = [a.get("authKey") for a in (app.get("auths") or [])]
        print(f"\n[拒绝] 场景「{scene.get('sceneName')}」对应的 app（{app.get('appName')}, "
              f"appId={app_id}）不具备大模型对话能力，不会修改任何配置。")
        print(f"       现有授权: {auth_keys}")
        print(f"       需要以下任一且未过期: {sorted(LLM_AUTH_KEYS)}")
        return
    print(f"[能力检查] 通过 - app「{app.get('appName')}」具备对话能力: "
          f"{[a.get('authKey') for a in valid_auths]}")

    # 1. 找到目标模型
    models = list_models(session)
    model = find_model(models, model_name)
    if not model:
        print(f"[错误] 未找到模型：{model_name}")
        print("可用模型：", [m.get("name") for m in models])
        return

    is_custom = model.get("modelType") == 2
    nlp_type = "openai" if is_custom else "xinghuo"
    domain = model.get("domain") or model.get("model")
    # 自有模型带自己的 apiKey/apiUrl，官方模型留空
    api_key = model.get("apiKey", "") if is_custom else ""
    base_url = model.get("apiUrl", "") if is_custom else ""

    print(f"\n[绑定] 场景 {scene_id} <- 模型 {model.get('name')} "
          f"({'自有' if is_custom else '官方'}, nlpType={nlp_type})")

    # 2. 查询现有配置，决定 create 还是 update
    existing = query_nlp(session, scene_id)
    existing_id = None
    if existing:
        items = existing if isinstance(existing, list) else [existing]
        # 找“大模型”那条
        for it in items:
            if it.get("label") == "大模型" or it.get("value"):
                existing_id = it.get("id")
                break
    print(f"[信息] 现有配置 id = {existing_id}（None 表示新建）")

    # 3. 构建 nlpExtra
    nlp_extra = {
        "domain": domain,
        "temperature": DEFAULT_TEMPERATURE,
        "maxTokens": DEFAULT_MAX_TOKENS,
        "historyTimes": DEFAULT_HISTORY_TIMES,
        "apiKey": api_key,
        "baseUrl": base_url,
        "model": domain,
        "systemPrompt": system_prompt or DEFAULT_SYSTEM_PROMPT,
    }

    # 4. nlp/createOrUpdate 负载
    nlp_payload = {
        "sceneId": scene_id,
        "label": "大模型",
        "value": nlp_type,
        "collapsed": False,
        "nlpExtra": json.dumps(nlp_extra, ensure_ascii=False),
        "nlpStatus": 1,
        "nlpType": nlp_type,
    }
    if existing_id is not None:
        nlp_payload["id"] = existing_id

    print("\n[步骤1] 提交 nlp/createOrUpdate ...")
    print("  payload:", json.dumps(nlp_payload, ensure_ascii=False, indent=2))
    r1 = xc.post(session, API_NLP_UPSERT, nlp_payload, debug=True)
    if not (r1 and r1.get("flag")):
        print(f"[失败] nlp 配置未保存：{r1.get('desc') if r1 else '无响应'}")
        return
    print("[OK] nlp 配置已保存")

    # 5. interact/createOrUpdate 负载（最小版本：只改模型和兜底回复）
    # 注：完整版包含 IAT识别/交互模式/唤醒词/引导语等高级参数，见 cmd_config
    interact_payload = {
        "sceneId": scene_id,
        "defaultReply": "",  # 兜底回复，可根据需要改成自定义文案
        "nlpAssistantInfo": nlp_type,
    }
    print("\n[步骤2] 提交 interact/createOrUpdate ...")
    print("  payload:", json.dumps(interact_payload, ensure_ascii=False, indent=2))
    r2 = xc.post(session, API_INTERACT_UPSERT, interact_payload, debug=True)
    if not (r2 and r2.get("flag")):
        print(f"[失败] interact 配置未保存：{r2.get('desc') if r2 else '无响应'}")
        return
    print("[OK] interact 配置已保存")
    print("\n[完成] 模型绑定 & 配置保存成功！")
    print(f"\n[下一步] 配置已保存为草稿，运行以下命令发布生效:")
    print(f"        python xfyun_model_manage.py publish {scene_id}")


# ==================== 探测 ====================
def probe(session):
    print("\n" + "=" * 70 + "\n探测: 场景\n" + "=" * 70)
    cmd_scenes(session)
    print("\n" + "=" * 70 + "\n探测: 模型\n" + "=" * 70)
    list_models(session, debug=True)


# ==================== 入口 ====================
def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    session = xc.get_session()
    if not session:
        print("[错误] 登录失败")
        return

    if cmd == "probe":
        probe(session)
    elif cmd == "list":
        cmd_list(session)
    elif cmd == "scenes":
        cmd_scenes(session)
    elif cmd == "caps":
        cmd_caps(session)
    elif cmd == "check":
        if len(sys.argv) < 3:
            print("用法: check <sceneId>")
            return
        cmd_check(session, sys.argv[2])
    elif cmd == "create":
        if len(sys.argv) < 6:
            print("用法: create <name> <model> <introduce> <apiUrl>")
            print("      apiKey 将通过交互式输入（不回显）并加密存储")
            return
        cmd_create(session, *sys.argv[2:6])
    elif cmd == "update":
        if len(sys.argv) < 3:
            print("用法: update <model_id或name>")
            print("      交互式修改模型配置")
            return
        cmd_update(session, sys.argv[2])
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("用法: query <sceneId>")
            return
        cmd_query(session, sys.argv[2])
    elif cmd == "query-interact":
        if len(sys.argv) < 3:
            print("用法: query-interact <sceneId>")
            return
        cmd_query_interact(session, sys.argv[2])
    elif cmd == "update-interact":
        if len(sys.argv) < 3:
            print("用法: update-interact <sceneId> [key=value ...]")
            print("示例: update-interact 123 iatType=10002 defaultReply='Sorry'")
            return
        scene_id = sys.argv[2]
        # 解析 key=value 参数
        kwargs = {}
        for arg in sys.argv[3:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                # 尝试转数字
                try:
                    v = int(v)
                except ValueError:
                    pass
                kwargs[k] = v
        cmd_update_interact(session, scene_id, **kwargs)
    elif cmd == "publish":
        if len(sys.argv) < 3:
            print("用法: publish <sceneId>")
            return
        cmd_publish(session, sys.argv[2])
    elif cmd == "bind":
        if len(sys.argv) < 4:
            print("用法: bind <sceneId> <modelName> [systemPrompt]")
            return
        prompt = sys.argv[4] if len(sys.argv) > 4 else None
        cmd_bind(session, sys.argv[2], sys.argv[3], prompt)
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户中断")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
