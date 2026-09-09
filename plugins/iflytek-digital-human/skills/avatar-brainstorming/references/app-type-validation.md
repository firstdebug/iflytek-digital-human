# 应用类型验证（SDK 集成 vs Web 模板）

## 关键概念区分（HARD-GATE）

### 讯飞虚拟人平台的两种应用类型

| 应用类型       | appType | 用途       | 场景创建方式        | 适用场景                   |
| ---------- | ------- | -------- | ------------- | ---------------------- |
| **接口服务**   | 1       | SDK 集成开发 | 控制台手动创建普通场景   | 需要自己写代码、深度定制 UI、控制交互细节 |
| **Web 对话** | 2       | 零代码快速部署  | 使用 Web 模板工具创建 | 快速演示、智能客服、H5 页面        |

### 判定规则（Phase 2 门禁前置检查）

当用户选择"接 SDK 自建前端项目"路径时，**必须验证应用类型**：

```python
def validate_app_for_sdk_integration(app):
    """
    验证应用是否适合 SDK 集成
    SDK 集成必须使用 appType=1 的应用
    """
    app_type = app.get('appType')
    app_id = app.get('appId')
    app_name = app.get('appName')

    if app_type != 1:
        return {
            'valid': False,
            'reason': f'应用 {app_name} (appId={app_id}) 的类型为 {app_type}，不适合 SDK 集成',
            'detail': 'SDK 集成项目必须使用 appType=1（接口服务）的应用，当前应用为 appType=2（Web对话模板）',
            'action': 'create_new_app_or_select_another'
        }

    # 检查是否有对话能力
    has_llm = check_llm_capability(app)
    if not has_llm:
        return {
            'valid': False,
            'reason': f'应用 {app_name} 没有大模型对话能力',
            'detail': '需要在控制台为应用开通 LLM_DIALOG_NUM / LLM_DOC_NUM / LLM_TOKENS_NUM 授权',
            'action': 'enable_llm_capability'
        }

    return {
        'valid': True,
        'appId': app_id,
        'appName': app_name
    }
```

### 自动化工具的应用类型过滤

使用 `xfyun_query_services.py` 或 `xfyun_model_manage.py caps` 查询应用列表时，需要按 appType 过滤：

```python
# 查询所有应用
all_apps = query_apps(session)

# SDK 集成场景：只显示 appType=1 的应用
sdk_apps = [app for app in all_apps if app.get('appType') == 1]

# Web 模板场景：只显示 appType=2 的应用
template_apps = [app for app in all_apps if app.get('appType') == 2]

# 展示给用户选择
if intent == 'sdk_integration':
    if not sdk_apps:
        print("[错误] 您的账号下没有 appType=1 的应用（接口服务）")
        print("[建议] SDK 集成需要应用，请先在控制台创建应用（应用类型选择【接口服务】）")
        return None

    print(f"[提示] 检测到 {len(sdk_apps)} 个可用于 SDK 集成的应用（appType=1）：")
    for app in sdk_apps:
        has_llm = check_llm_capability(app)
        status = "[有对话能力]" if has_llm else "[无对话能力]"
        print(f"  {status} {app['appName']} (appId={app['appId']})")
```

## Phase 1 扫描增强：应用类型检测

在 `avatar-brainstorming` Phase 1 工程扫描阶段，需要增加应用类型检测：

### 扫描流程

1. **检测用户选择的交付形态**
   
   - 如果用户选择"接 SDK 自建前端项目" → 需要 appType=1
   - 如果用户选择"官方模板快速部署" → 需要 appType=2

2. **查询账号下的应用列表**
   
   ```python
   apps = query_apps(session)
   ```

3. **按 appType 过滤**
   
   ```python
   if delivery_mode == 'sdk_integration':
       valid_apps = [app for app in apps if app.get('appType') == 1 and check_llm_capability(app)]
   elif delivery_mode == 'web_template':
       valid_apps = [app for app in apps if app.get('appType') == 2]
   ```

4. **无可用应用时的处理**
   
   ```python
   if not valid_apps:
       print("[阻塞] 无可用应用")
       print(f"[原因] SDK 集成需要 appType=1 的应用，但您的账号下只有 appType=2 的应用")
       print("[解决方案]")
       print("  方案A: 先在控制台创建应用（应用类型选择【接口服务】），然后继续")
       print("  方案B: 改用 Web 模板快速部署（零代码，但无法深度定制）")
   
       # 询问用户选择
       choice = ask_user_choice(['create_new_app', 'switch_to_template', 'abort'])
   
       if choice == 'create_new_app':
           print("[等待] 请在控制台创建应用后，提供 appId")
           app_id = input("新应用的 appId: ")
           # 继续流程
       elif choice == 'switch_to_template':
           # 路由到 avatar-web-template
           route_to('avatar-web-template')
       else:
           return 'aborted'
   ```

5. **有多个可用应用时**
   
   ```python
   if len(valid_apps) > 1:
       print(f"[选择] 检测到 {len(valid_apps)} 个可用应用：")
       for i, app in enumerate(valid_apps):
           print(f"  {i+1}. {app['appName']} (appId={app['appId']})")
   
       selected_index = ask_user_select(range(1, len(valid_apps) + 1))
       selected_app = valid_apps[selected_index - 1]
   else:
       selected_app = valid_apps[0]
       print(f"[使用] {selected_app['appName']} (appId={selected_app['appId']})")
   ```

## Phase 2 门禁前置：应用类型校验

在调用 `avatar-preflight` 之前，**必须先完成应用类型校验**：

```python
# Phase 1: 扫描工程现状
scan_result = scan_project()

# Phase 1.5: 应用类型校验（新增）
if scan_result['delivery_mode'] == 'sdk_integration':
    app_validation = validate_app_for_sdk_integration(selected_app)

    if not app_validation['valid']:
        print(f"[错误] {app_validation['reason']}")
        print(f"[详情] {app_validation['detail']}")

        if app_validation['action'] == 'create_new_app_or_select_another':
            # 提示创建新应用或选择其他应用
            handle_invalid_app_type()
        elif app_validation['action'] == 'enable_llm_capability':
            # 提示开通对话能力
            handle_missing_llm_capability()

        return 'blocked_by_app_type_validation'

# Phase 2: 环境门禁（只有通过应用类型校验后才执行）
preflight_result = call_skill('avatar-preflight', {
    'platform': scan_result['platform'],
    'appId': selected_app['appId'],
    'workDir': project_root
})
```

## 错误示例（避免重现）

### ❌ 错误示例 1：未检查 appType 直接选择应用

```python
# 错误：没有过滤 appType
apps = query_apps(session)
selected_app = apps[0]  # 可能是 appType=2 的模板应用！

# 结果：后续创建场景时会失败，因为 appType=2 的应用无法创建普通场景
```

### ❌ 错误示例 2：混淆 SDK 集成和 Web 模板

```python
# 用户说"接 SDK 自建项目"
if user_choice == 'sdk_integration':
    # 错误：路由到了 Web 模板工具
    route_to('avatar-web-template')  # ❌ 错误！

    # 正确：应该走 SDK 集成流程
    route_to('avatar-brainstorming')  # ✅ 正确
```

### ✅ 正确示例：完整的应用选择流程

```python
# 1. 确定交付形态
delivery_mode = ask_delivery_mode()  # 'sdk_integration' or 'web_template'

# 2. 查询应用列表
all_apps = query_apps(session)

# 3. 按 appType 过滤
if delivery_mode == 'sdk_integration':
    valid_apps = [app for app in all_apps 
                  if app.get('appType') == 1 
                  and check_llm_capability(app)]

    if not valid_apps:
        handle_no_valid_app_for_sdk()
        return
else:  # web_template
    valid_apps = [app for app in all_apps if app.get('appType') == 2]

    if not valid_apps:
        handle_no_valid_app_for_template()
        return

# 4. 用户选择应用
selected_app = select_from_apps(valid_apps)

# 5. 继续后续流程
proceed_with_app(selected_app)
```

## 用户友好的错误提示

### 场景 1：SDK 集成但只有 Web 模板应用

```
❌ 应用类型不匹配

您选择了"接 SDK 自建前端项目"，但检测到的应用类型不适合：
  - 当前应用: xxx (appId=YOUR_APP_ID)
  - 应用类型: appType=2 (Web 对话模板)
  - 需要类型: appType=1 (接口服务)

解决方案:
  1. 先在控制台创建应用（应用类型选择【接口服务】），然后继续

  2. 或者改用 Web 模板快速部署（零代码）
     （我可以帮您用现有应用创建 Web 模板应用）

请问您想选择哪个方案？
```

### 场景 2：应用没有对话能力

```
❌ 缺少大模型对话能力

应用 xxx (appId=yyy) 没有大模型对话授权：
  - 当前授权: ['AVATAR_INTERACTION_CONC_NUM', 'video.total', 'SCENE_NUM']
  - 缺少授权: LLM_DIALOG_NUM / LLM_DOC_NUM / LLM_TOKENS_NUM

解决方案:
  1. 联系讯飞平台客服为应用开通大模型对话能力

  2. 或选择其他已有对话能力的应用

请问您想选择哪个方案？
```

## 自动化工具修改清单

需要修改以下工具以支持 appType 过滤：

1. **xfyun_query_services.py**
   
   - 查询结果增加 appType 字段
   - 增加 `--app-type` 参数过滤

2. **xfyun_model_manage.py**
   
   - `caps` 命令增加 appType 显示
   - `check` 命令增加 appType 校验

3. **新增工具方法**
   
   ```python
   def query_apps_by_type(session, app_type):
       """按类型查询应用
   
       Args:
           session: 已登录的会话
           app_type: 1=接口服务, 2=Web对话
   
       Returns:
           list: 过滤后的应用列表
       """
       all_apps = query_apps(session)
       return [app for app in all_apps if app.get('appType') == app_type]
   ```

## 
