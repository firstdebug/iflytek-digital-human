# 讯飞虚拟人平台管理工具包

一套用于管理讯飞虚拟人平台（virtual-man.xfyun.cn）的 Python 脚本工具集。支持登录、查询服务、模型管理、场景配置、密钥安全管理等功能。

## 目录结构

```
xfyun-tools/
├── README.md                  # 本文档
├── xfyun_common.py            # 【核心】登录会话 + HTTP 请求封装
├── xfyun_secrets.py           # 【核心】密钥安全管理（脱敏/加密/输入）
├── xfyun_query_services.py    # 查询服务：场景 + API 密钥
├── xfyun_model_manage.py      # 模型管理：创建/修改/绑定/发布
├── xfyun_knowledge.py         # 知识库：建库/上传/拆分向量化/关联场景对话
├── xfyun_template.py          # Web 对话模板：创建应用/配置/发布
├── xfyun_live.py              # 直播项目：创建直播间/商品/分镜（含资产授权）
└── scripts/
    └── secure_update_key.py   # 安全更新密钥示例脚本
```

## 依赖安装

```bash
pip install -r tools/requirements.txt
playwright install chromium
```

- `playwright` - 浏览器自动化（登录用）
- `requests` - HTTP 请求
- `cryptography` - 密钥加密存储

## 快速开始

```bash
# 1. 查询账号下的所有服务
python xfyun_query_services.py

# 2. 列出可用模型
python xfyun_model_manage.py list

# 3. 绑定模型到场景并发布
python xfyun_model_manage.py bind <sceneId> <modelName>
python xfyun_model_manage.py publish <sceneId>

# 4. 建知识库 -> 传文档 -> 打开场景的知识库对话
python xfyun_knowledge.py create-kb "我的知识库" --label <labelId>
python xfyun_knowledge.py upload <libId> ./doc.md --wait
python xfyun_knowledge.py enable <sceneId> <libId>

# 5. 创建 Web 对话模板应用并发布
python xfyun_template.py list-templates
python xfyun_template.py create <templateId> <appId> "应用名称"
python xfyun_template.py publish <sceneId>

# 6. 创建直播项目（自动配置商品/分镜，完成后跳转浏览器）
python xfyun_live.py create <appId> "直播间名称"
```

---

## 认证机制说明

### 登录流程

工具使用 **Playwright 拉起真实浏览器**让用户登录，然后提取 Cookie：

1. 打开 `https://passport.xfyun.cn/login`
2. 用户扫码/密码登录
3. 轮询检测 `ssoSessionId` 和 `account_id` 两个 Cookie
4. 提取后保存到 `xfyun_cookies.json`

### Cookie 关键点

| Cookie | 作用 | 说明 |
|--------|------|------|
| `ssoSessionId` | 会话标识 | SSO 登录凭证 |
| `account_id` | 账号 ID | 同时作为 uid 用于 model/list 接口 |

**重要：** 请求业务接口时，Cookie 必须设置到 `.xfyun.cn` 父域（而非 `passport.xfyun.cn`），否则不会发送给 `virtual-man.xfyun.cn`，导致返回 80000 登录异常。

### 切换账号

删除 Cookie 文件即可，下次运行会重新登录：

```bash
rm xfyun_cookies.json
```

---

## 脚本详解

### 1. xfyun_common.py（核心模块）

登录会话管理和统一 HTTP 请求封装。其他脚本都 `import` 它。

#### 提供的函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `get_session()` | `get_session(force_login=False) -> Session` | 获取已登录会话，优先用本地 Cookie |
| `post()` | `post(session, url, payload, debug=False) -> dict` | POST 请求，自动脱敏 debug 输出 |
| `get()` | `get(session, url, params=None, debug=False) -> dict` | GET 请求 |
| `put()` | `put(session, url, payload, debug=False) -> dict` | PUT 请求（模型更新用） |
| `save_cookies()` | `save_cookies(cookie_dict)` | 保存 Cookie 到本地 |
| `load_cookies()` | `load_cookies() -> dict` | 加载本地 Cookie |
| `build_session()` | `build_session(cookie_dict) -> Session` | 构建带 Cookie 的会话 |

#### 使用示例

```python
import xfyun_common as xc

# 获取已登录会话（没有 Cookie 会自动拉浏览器登录）
session = xc.get_session()

# session.uid 可直接取到账号 ID（account_id）
print(session.uid)

# 发起请求
data = xc.post(session, "https://virtual-man.xfyun.cn/zs_web/scene/query", {
    "sceneType": 1, "sceneStatus": 1, "sceneTypeList": None, "__times": 0
})
```

#### 关键配置常量

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `LOGIN_URL` | passport.xfyun.cn/login | 登录页地址 |
| `COOKIE_FILE` | xfyun_cookies.json | Cookie 存储文件 |
| `LOGIN_TIMEOUT` | 300 | 登录超时（秒） |
| `REQUIRED_COOKIES` | [ssoSessionId, account_id] | 必需的 Cookie |

#### 注意事项

- **80000 错误处理**：`post`/`get`/`put` 检测到 `code=80000` 会提示登录失效并返回 None
- **debug 脱敏**：`debug=True` 时会自动脱敏 apiKey/apiSecret/apiUrl 等字段
- **超时**：所有请求默认 15 秒超时

---

### 2. xfyun_secrets.py（密钥安全模块）

处理所有密钥相关的安全操作：脱敏显示、加密存储、交互式输入。

#### 提供的函数

| 函数 | 签名 | 说明 |
|------|------|------|
| `mask_secret()` | `mask_secret(value, show_prefix=4, show_suffix=4) -> str` | 脱敏单个值 |
| `mask_dict()` | `mask_dict(data, depth=3) -> dict` | 递归脱敏字典中的敏感字段 |
| `save_secret()` | `save_secret(key_id, value)` | 加密保存密钥 |
| `get_secret()` | `get_secret(key_id) -> str` | 解密读取密钥 |
| `list_secret_ids()` | `list_secret_ids() -> list` | 列出已存储的密钥 ID |
| `prompt_secret()` | `prompt_secret(prompt_text, key_id=None, save_local=True) -> str` | 交互式输入密钥 |

#### 脱敏规则

```python
mask_secret("0602b7ad925c47d952005e2080eb56a3")
# 输出: "0602********56a3"  (前4 + 8星号 + 后4)

# 长度 <= 前后位数之和时全部星号
mask_secret("123")  # 输出: "***"
```

#### 自动脱敏的字段名（不区分大小写）

```
apikey, apisecret, apiurl, api_key, api_secret,
base_url, baseurl, token, password, secret
```

#### 加密存储位置

| 文件 | 权限 | 说明 |
|------|------|------|
| `<plugin-root>/.runtime/secrets/master.key` | 600 | 主密钥（Fernet），解密用 |
| `<plugin-root>/.runtime/secrets/secrets.enc` | 600 | 加密的密钥数据（JSON） |

**警告：** `master.key` 是解密所有密钥的万能钥匙，不要泄露或上传。丢失后加密的密钥无法恢复。

#### 交互式输入的两种方式

`prompt_secret()` 会让用户选择：

1. **交互式输入**（getpass 不回显，支持粘贴）
   - 输入后显示脱敏版确认
2. **从文件读取**
   - 输入文件路径，读取内容
   - 确认后可自动删除文件

#### 使用示例

```python
import xfyun_secrets as xs

# 脱敏显示
print(xs.mask_secret("sk-1234567890"))  # sk-12********7890

# 加密存储
xs.save_secret("my_key", "sk-real-key-value")

# 读取（不打印）
key = xs.get_secret("my_key")

# 递归脱敏整个响应
safe = xs.mask_dict(api_response)
```

---

### 3. xfyun_query_services.py（服务查询）

查询账号下所有场景及对应的 API 密钥。**独立脚本**，自带登录和脱敏逻辑。

#### 运行方式

```bash
python xfyun_query_services.py
```

#### 功能流程

1. 登录（或用本地 Cookie）
2. 查询场景列表（`scene/query`）
3. 对每个场景查询 app 详情（`app/query`）获取密钥
4. 脱敏显示 + 导出到 `xfyun_scenes_export.json`

#### 输出字段

| 字段 | 说明 |
|------|------|
| sceneName | 场景名称 |
| sceneId | 场景 ID（后续绑定用） |
| appId | 应用 ID |
| apiKey | 应用密钥（脱敏） |
| apiSecret | 应用密钥（脱敏） |

#### 注意事项

- 导出文件中的密钥**也已脱敏**，完整值不落盘
- 同一个 appId 可能对应多个场景

---

### 4. xfyun_model_manage.py（模型管理·主工具）

最核心的管理工具，支持模型的完整生命周期。

#### 命令总览

| 命令 | 用法 | 类型 |
|------|------|------|
| `list` | `list` | 只读 |
| `scenes` | `scenes` | 只读 |
| `caps` | `caps` | 只读 |
| `check` | `check <sceneId>` | 只读 |
| `query` | `query <sceneId>` | 只读 |
| `query-interact` | `query-interact <sceneId>` | 只读 |
| `create` | `create <name> <model> <introduce> <apiUrl>` | 写 |
| `update` | `update <model_id或name>` | 写 |
| `bind` | `bind <sceneId> <modelName> [systemPrompt]` | 写 |
| `update-interact` | `update-interact <sceneId> [key=value ...]` | 写 |
| `publish` | `publish <sceneId>` | 写 |

#### 命令详解

**`list` - 列出所有模型**
```bash
python xfyun_model_manage.py list
```
显示 id、name、model/domain、type（官方/自有）、apiUrl（自有模型脱敏）

**`bind` - 绑定模型到场景**
```bash
python xfyun_model_manage.py bind 335668583902351360 "Spark V4.0"
python xfyun_model_manage.py bind 335668583902351360 "我的模型" "你是一个助手"
```
- 先做**能力检查**（无对话能力直接拒绝，不写库）
- 自动区分官方/自有模型，设置正确的 nlpType
- 依次调用 nlp/createOrUpdate + interact/createOrUpdate
- **完成后需要 publish 才生效**

**`publish` - 发布配置**
```bash
python xfyun_model_manage.py publish 335668583902351360
```
调用 scene/publish，让草稿配置正式生效。**bind/update-interact 后必须执行。**

**`create` - 创建自有模型**
```bash
python xfyun_model_manage.py create "我的模型" "my_model" "模型描述" "https://api.example.com/chat"
```
- 4 个参数：名称、标识、介绍、API地址
- apiKey 通过交互式安全输入（不在命令行传）
- 密钥自动加密存储

**`update` - 修改自有模型**
```bash
python xfyun_model_manage.py update "我的模型"
python xfyun_model_manage.py update 2093
```
- 交互式选择要改的字段（名称/标识/介绍/地址/密钥）
- 只能改自有模型（modelType=2）
- **内部使用 PUT 方法**调用 model/info

**`update-interact` - 修改高级参数**
```bash
python xfyun_model_manage.py update-interact 335668583902351360 iatType=10001 nicknameQualifier='你好' defaultReply='抱歉没听懂'
```
- key=value 形式传参，数字自动转换
- 只更新指定字段，其他保持不变

---

### 5. xfyun_knowledge.py（知识库管理）

管理 docqa 知识库全流程：建库、上传文档、拆分向量化、关联到场景让虚拟人对话时能检索知识库。接口走 `flames-docqa` 网关（文档相关）和 `zs_web`（场景配置相关）。

#### 命令一览

| 命令 | 用法 | 类型 |
|------|------|------|
| `list` | `list` | 只读 |
| `labels` | `labels` | 只读 |
| `models` | `models` | 只读 |
| `versions` | `versions <libId>` | 只读 |
| `categories` | `categories <libId>` | 只读 |
| `docs` | `docs <libId>` | 只读 |
| `status` | `status <sceneId>` | 只读 |
| `create-label` | `create-label <name>` | 写 |
| `create-kb` | `create-kb <name> --label <labelId> [--desc ...]` | 写 |
| `upload` | `upload <libId> <文件...> [--category id] [--split 7] [--wait]` | 写 |
| `enable` | `enable <sceneId> [libId...] [--chain docqa,xinghuo]` | 写 |
| `disable` | `disable <sceneId>` | 写 |
| `chain` | `chain <sceneId> <order>` | 写 |
| `publish` | `publish <sceneId>` | 写 |

#### 标准流程

```bash
# 1. 建库（需先有标签，可用 labels 查或 create-label 建）
python xfyun_knowledge.py create-kb "咖啡馆知识库" --label 4751ebaf... --desc "可删"

# 2. 上传文档并等待向量化就绪（--wait 阻塞轮询文档状态）
python xfyun_knowledge.py upload <libId> ./手册.md --wait

# 3. 打开场景的知识库对话（关联库 + 设调用链 + 发布，一条龙）
python xfyun_knowledge.py enable <sceneId> <libId>

# 4. 到虚拟人对话框验证：问知识库里才有的内容，看是否被引用
```

#### 命令详解

**`upload` - 上传并向量化文档**
```bash
python xfyun_knowledge.py upload <libId> ./a.md ./b.pdf --wait
```
- 三步：重名检查 → 上传文件 → 提交拆分向量化（splitType=7 智能拆分）
- `--category` 不传时**自动取该库第一个分类**。⚠️ categoryID 必须非空，否则后端向量化会静默卡在"处理中"（见下方坑）
- `--wait` 阻塞轮询**文档级**状态到就绪/异常；不传则后台处理，用 `docs <libId>` 查进度

**`enable` - 打开场景的知识库对话**
```bash
python xfyun_knowledge.py enable <sceneId> <libId1> <libId2>   # 关联指定库
python xfyun_knowledge.py enable <sceneId>                     # 沿用现有已关联库，仅开启
```
- 一条龙：开启 docqa 检索(nlpStatus=1) → 设调用链 `docqa,xinghuo` → 发布
- **两个条件缺一不可**：docqa nlpStatus=1 且调用链含 docqa。只传文档进库不改调用链，对话不会走知识库
- `--chain` 可改调用顺序，如 `docqa`（只走库）或 `docqa,xinghuo`（库优先，大模型兜底）

**`disable` - 关闭知识库对话**
```bash
python xfyun_knowledge.py disable <sceneId>
```
把 docqa nlpStatus 置 0 并发布，保留库关联（不用重传 libId）。

#### 关键坑（实测踩过）

1. **拆分接口 categoryID 必填**：传空串接口仍返回成功，但向量化永远卡在"处理中(段落0)"。工具已自动取默认分类兜底。
2. **换模型会踢掉知识库**：`model_manage.py bind` 会把调用链重置成纯大模型。**换模型后必须重跑 `enable`** 把 docqa 加回调用链。安全顺序：先 bind 换模型 → 再 enable。
3. **domain 不能为空**：nlpExtra 的 domain 为空会在对话时报 `xinghuo.domain can not be blank`（保存时不报）。docqa 用 `generalv3.5`，大模型那条用其模型 domain。
4. **就绪判据看文档级 status**：版本级 status 处理期间恒为 -1 不可靠。文档状态码：1=就绪，0/-2/-4=处理中，-3=采编异常。

---

### 6. xfyun_template.py（Web 对话模板应用）

创建和配置 Web 对话模板应用（智能客服/H5 通话/大屏交互等），自动完成场景/模板/NLP/交互 4 步配置 + 资产授权，创建后**自动发布**并跳转浏览器（访问链接 + 配置页面双标签页）。

#### 命令一览

| 命令 | 用法 | 类型 |
|------|------|------|
| `list-templates` | `list-templates` | 只读 |
| `create` | `create <templateId> <appId> <name> [--desc D] [--no-browser]` | 写 |
| `update-bg` | `update-bg <sceneId> <图片路径>` | 写 |
| `update-avatar` | `update-avatar <sceneId> <anchorId> <vcn> [--app appId]` | 写 |
| `publish` | `publish <sceneId> [--domain D] [--expire TS] [--app appId] [--no-browser]` | 写 |

#### 可用模板（templateId）

| ID | 名称 | 说明 |
|----|------|------|
| 1 | 大屏交互对话 | 1920x1080，带引导词/识别展示/NLP 展示 |
| 3 | Web智能客服 | 1920x1080，横屏 Web 客服 |
| 4 | Web智能客服-横屏弹窗 | 1920x1080，弹窗模式 |
| 7 | H5-对话模板 | 1080x1920，移动端对话 |
| 11 | H5-通话模板 | 1080x1920，移动端通话（含语音按钮）|

#### 标准流程

```bash
# 1. 列出可用模板
python xfyun_template.py list-templates

# 2. 创建应用（一条龙：4步配置 + 资产授权 + 自动发布 + 跳转浏览器）
python xfyun_template.py create 3 YOUR_APP_ID "我的智能客服" --desc "测试应用"
#   完成后自动打开 2 个标签页：
#   - 访问链接: https://virtual-man.xfyun.cn/interact_web/common/web/{sceneId}
#   - 配置页面: https://virtual-man.xfyun.cn/console/projects/config/{appId}/{sceneId}/view

# 只建不开浏览器（脚本/批量场景）
python xfyun_template.py create 3 YOUR_APP_ID "我的智能客服" --no-browser

# 3. 可选：重新发布并绑定域名和有效期
python xfyun_template.py publish <sceneId> --domain 124.221. --expire 1785513599999 --app YOUR_APP_ID
```

#### 命令详解

**`create` - 创建模板应用（一条龙）**
```bash
python xfyun_template.py create 3 YOUR_APP_ID "智能客服Demo"
python xfyun_template.py create 3 YOUR_APP_ID "智能客服Demo" --no-browser  # 不开浏览器
```
- 自动执行 4 步：scene/createOrUpdate → template/createOrUpdate → nlp/createOrUpdate → interact/createOrUpdate
- **自动授权资产**：创建场景后授权模板用的形象(assetType=1)和发音人(assetType=3)给 appId，否则不生效
- 每个模板有预设的形象/声音/布局/引导词/背景图
- **创建后自动发布**，并打开浏览器 2 个标签页（访问链接 + 配置页面）
- `--no-browser` 跳过浏览器（脚本/批量场景），仅打印链接

**`publish` - 发布应用**
```bash
python xfyun_template.py publish 337419537274245120 --app YOUR_APP_ID
python xfyun_template.py publish 337419537274245120 --domain example.com --expire 1785513599999 --app YOUR_APP_ID
```
- `--domain` 授权域名（不填则不限制）
- `--expire` 有效期时间戳（毫秒，0=永久）
- `--app` 指定 appId（发布后跳转配置页面需要；不填则按 sceneId 自动反查）
- 生成访问链接格式：`https://virtual-man.xfyun.cn/interact_web/common/web/{sceneId}`

**`update-bg` - 更新背景图**
```bash
python xfyun_template.py update-bg <sceneId> ./background.jpg
```
自动上传图片并更新场景背景（支持 JPG/PNG 等）

**`update-avatar` - 更新形象和声音（自动授权新资产）**
```bash
python xfyun_template.py update-avatar <sceneId> 111322001 x4_yuexiaoni_assist
python xfyun_template.py update-avatar <sceneId> 111322001 x4_yuexiaoni_assist --app YOUR_APP_ID
```
- `anchorId` 形象ID，`vcn` 发音人（如 x4_mingge、x4_lingxiaoqi_oral）
- **换形象/发音人前会自动授权新资产**，未传 `--app` 时按 sceneId 反查 appId

#### 注意事项

- **appId 需有对话能力**：创建前用 `xfyun_model_manage.py check <sceneId>` 确认授权
- **资产授权是关键**：形象/发音人必须先授权给 appId 才生效，create/update-avatar 已自动处理
- **模板预设不可变部分**：每个模板的 widgets 布局、尺寸为固定预设
- **各模板背景图不同**：从抓包提取的官方默认背景（注意旧 URL 可能过期，报 403 时需换新图）
- **配置后需重新发布**：update-bg/update-avatar 等修改配置后，需再次 `publish` 才生效
- **浏览器免登录**：跳转时复用 `xfyun_cookies.json` 的登录态，注入 Cookie 到 playwright

---

### 7. xfyun_live.py（虚拟人直播项目）

创建虚拟人直播项目（营销带货场景），一条龙完成 10 步配置 + 资产授权 + 商品/分镜/脚本，创建后**自动发布**并跳转浏览器（直播间 + 配置页面双标签页）。

#### 命令一览

| 命令 | 用法 | 类型 |
|------|------|------|
| `create` | `create <appId> <name> [--desc D] [--anchor ID] [--vcn V] [--no-browser]` | 写 |
| `list` | `list` | 只读 |
| `query` | `query <sceneId>` | 只读 |

#### 10 步创建流程

`create` 一条龙自动执行：

1. 查询应用信息（验证 appId）
2. 创建场景（sceneType=6 直播场景，templateId=17）
3. 配置模板（形象/发音人/背景/画布组件）
4. 配置 NLP（星火大模型）
5. 配置交互（欢迎语/识别参数）
6. 授权发音人（assetType=3，assetScene=2 直播场景）
7. 授权形象（assetType=1，assetScene=2）
8. 创建默认商品（"商品1"）
9. 创建默认分镜（"分镜1"）
10. 添加默认脚本（**带内容且启用**，否则无法发布）

之后自动发布 → 打开浏览器：
- 直播间链接：`https://virtual-man.xfyun.cn/marketing/scene/{sceneId}`
- 配置页面：`https://virtual-man.xfyun.cn/console/projects/config/marketing/{appId}/{sceneId}/explain`

#### 标准流程

```bash
# 默认形象/发音人（晓姿-蓝色制服 110117026 / 灵小琪 x4_lingxiaoqi_oral）
python xfyun_live.py create YOUR_APP_ID "我的直播间"

# 自定义形象和发音人
python xfyun_live.py create YOUR_APP_ID "我的直播间" --anchor 110026010 --vcn x4_yiting

# 只建不开浏览器
python xfyun_live.py create YOUR_APP_ID "我的直播间" --no-browser

# 列出账号下的直播场景
python xfyun_live.py list

# 查询某个直播场景详情
python xfyun_live.py query <sceneId>
```

#### 默认配置

| 项 | 默认值 |
|----|--------|
| 形象 | 晓姿-蓝色制服 `110117026` |
| 发音人 | 灵小琪 `x4_lingxiaoqi_oral` |
| 背景图 | `.../20240606/9dfc4c95-...jpeg` |
| 商品 | 商品1 |
| 分镜 | 分镜1 |
| 脚本 | "大家好，欢迎来到我的直播间！今天给大家推荐一款非常不错的产品。"（启用）|

#### 注意事项

- **脚本必须有内容且启用**（disable=0）才能发布，空脚本无法发布
- **资产授权自动处理**：发音人/形象授权失败会警告但继续创建（部分资产可能需人工授权，不影响流程）
- **发布后即可访问**：创建流程末尾自动发布，直接打开直播间链接看效果
- **超过场景授权数量**：报此错说明账号场景配额已满，需先删除旧场景
- **浏览器免登录**：复用 `xfyun_cookies.json` 登录态，无 Cookie 时才拉浏览器登录

---

## 接口字段详解

### scene/query（查询场景）

**请求：** POST，负载 `{sceneType: 1, sceneStatus: 1, sceneTypeList: null, __times: 0}`

**响应关键字段：**
| 字段 | 说明 |
|------|------|
| data[].sceneId | 场景唯一 ID |
| data[].sceneName | 场景名称 |
| data[].appId | 关联的应用 ID |

### app/query（查询应用/密钥）

**请求方式一（单个）：** POST，负载 `{appId: "YOUR_APP_ID"}`
**请求方式二（分页）：** POST，负载 `{pageSize: 30, pageNum: 1, assetName: "", t: 0}`

**响应关键字段（data.records[]）：**
| 字段 | 说明 |
|------|------|
| appId | 应用 ID |
| apiKey | 应用 API Key |
| apiSecret | 应用 API Secret |
| appName | 应用名称 |
| auths[] | 授权列表（判断能力用） |

**auths[] 授权项字段：**
| 字段 | 说明 |
|------|------|
| authKey | 授权类型（如 LLM_DIALOG_NUM） |
| licState | 授权状态（valid/invalid） |
| authStatus | 1=启用 |
| effectEtime | 过期时间戳（毫秒），null=无限期 |
| concNum | 数量/并发数 |

### model/list（列出模型）

**请求：** GET，参数 `?uid=<account_id>`

**响应字段（data[]）：**
| 字段 | 说明 |
|------|------|
| id | 模型 ID |
| name | 模型显示名 |
| model | 模型标识 |
| domain | 模型 domain（通常同 model） |
| modelType | 1=官方，2=自有 |
| apiUrl | 接口地址（自有模型才有值） |
| apiKey | 密钥（自有模型才有值） |
| protocol | 协议类型 |

### model/create（创建模型）

**请求：** POST，负载：
| 字段 | 说明 |
|------|------|
| name | 模型名称 |
| model | 模型标识 |
| introduce | 模型介绍 |
| apiUrl | API 地址 |
| apiKey | API 密钥 |

### model/info（更新模型）⚠️ 用 PUT 方法

**请求：** **PUT**（不是 POST！），负载需带全字段：
| 字段 | 说明 | 必填 |
|------|------|------|
| id | 模型 ID | 是 |
| name | 名称 | 是 |
| model | 标识 | 是 |
| domain | domain（同 model） | 是 |
| introduce | 介绍 | 是 |
| apiUrl | API 地址 | 是 |
| apiKey | API 密钥 | 是 |
| modelType | 固定 2（自有） | 是 |
| protocol | 协议 | 是 |
| uid | 账号 ID | 是 |
| dataStatus | 固定 1 | 是 |
| createTime / updateTime | 时间戳 | 建议带 |

**关键坑：** 此接口只支持 PUT 方法。用 POST 会返回 `Request method 'POST' not supported`。

### nlp/query（查询 NLP 配置）

**请求：** POST，负载 `{sceneId: "335668583902351360"}`

**响应字段（data[]）：**
| 字段 | 说明 |
|------|------|
| id | 配置记录 ID（更新时需带上） |
| nlpType | xinghuo（官方）或 openai（自有） |
| nlpExtra | JSON 字符串，含模型详细参数 |
| nlpStatus | 状态，默认 1 |

**空配置：** `data: []` 表示该场景还没配过 NLP。

### nlp/createOrUpdate（创建/更新 NLP 配置）

**请求：** POST，负载：
| 字段 | 说明 |
|------|------|
| id | 更新时必带（从 query 获取），新建时省略 |
| sceneId | 场景 ID |
| label | 固定 "大模型" |
| value | 同 nlpType |
| collapsed | false |
| nlpType | xinghuo / openai |
| nlpStatus | 1 |
| nlpExtra | JSON 字符串（见下） |

**nlpExtra 内部字段：**
| 字段 | 取值范围 | 说明 |
|------|----------|------|
| domain | - | 模型标识（官方模型的 domain，如 xop3qwen32b） |
| model | - | 同 domain |
| temperature | 0.01-1 | 温度，默认 0.5 |
| maxTokens | 5-5000 | 最大 Token，默认 4000 |
| historyTimes | 1-100 | 历史轮数，默认 20 |
| apiKey | - | 自有模型填自身密钥，官方留空 |
| baseUrl | - | 自有模型填自身地址，官方留空 |
| systemPrompt | - | 系统提示词 |

### interact/createOrUpdate（保存交互配置）

有两种用法：

**用法一：最小版（只改模型和兜底回复）**
```json
{
  "sceneId": "335668583902351360",
  "nlpAssistantInfo": "xinghuo",
  "defaultReply": "对不起，我还没有学会"
}
```

**用法二：完整版（改识别/交互/唤醒等高级参数）**

| 字段 | 说明 | 取值 |
|------|------|------|
| id | 配置 ID（更新时带） | - |
| sceneId | 场景 ID | 必填 |
| nlpAssistantInfo | 大模型类型 | xinghuo / openai |
| defaultReply | 兜底回复 | 可空字符串 |
| iatType | 识别语言 | 10001中文/10002英文/10003日语/10004韩语 |
| iatHotWord | 识别热词 | 逗号分隔 |
| correctWordStr | 纠错词典 | JSON: {"错词":"正确词"} |
| bos | 前端点检测 | 毫秒，如 500 |
| eos | 尾端点检测 | 毫秒，如 500 |
| interactionMode | 交互模式 | 1随时打断/2限定词打断/3混合 |
| nicknameQualifier | 唤醒词 | 逗号分隔 |
| nicknameResponse | 唤醒回复 | - |
| welcomeMessage | 欢迎语 | - |
| guideQuestionInfo | 引导问题 | JSON数组字符串 |
| interactStatus | 发布状态 | 0草稿/1已发布 |
| isMultimodal | 是否多模态 | 0否/1是 |

**nlpAssistantInfo 说明：** 必须与模型类型匹配。查 model/list，modelType=2 用 openai，否则 xinghuo。

### scene/publish（发布配置）

**请求：** POST，负载 `{sceneId: "335668583902351360"}`

发布后配置正式生效。**每次 bind 或 update-interact 后都要调用。**

直播场景发布负载：`{sceneId, useType: 1, verifyMethod: 0, effectEtime: 0, captcha: ""}`

### app/auth_asset（资产授权）

**请求：** POST，负载 `{appId, assetKey, assetType, assetScene}`

形象/发音人使用前必须授权给对应 appId，否则不生效。

| 字段 | 说明 | 取值 |
|------|------|------|
| appId | 应用 ID | - |
| assetKey | 资产标识 | 形象填 anchorId，发音人填 vcn |
| assetType | 资产类型 | 1=形象 3=发音人 |
| assetScene | 授权场景 | 1=通用 2=直播场景 |

### 直播项目相关接口

| 接口 | 说明 | 关键字段 |
|------|------|---------|
| `product/add` | 创建商品 | `{sceneId, productName}` → 返回 productId |
| `scene/storyboard/add` | 创建分镜 | `{sceneId, productId, storyboardName, storyboardIndex, anchorId, vcn}` → 返回 storyboardId |
| `scene/storyboard/script/add` | 添加脚本 | `{storyboardId, scriptType:0, content, disable}` disable=0启用/1禁用 → 返回 scriptId |

**直播场景创建：** `scene/createOrUpdate` 负载 `{sceneName, appId, sceneDesc, templateId:17, thumbnail, sceneType:6, sceneProdType:4}`

---

## 模型类型与配置对照

| 属性 | 官方模型 (modelType=1) | 自有模型 (modelType=2) |
|------|----------------------|----------------------|
| 举例 | Spark/Qwen/DeepSeek | 用户自建 |
| nlpType/value | `xinghuo` | `openai` |
| nlpAssistantInfo | `xinghuo` | `openai` |
| nlpExtra.apiKey | 留空 | 模型自身 apiKey |
| nlpExtra.baseUrl | 留空 | 模型自身 apiUrl |
| 可否 update | 否 | 是（PUT model/info） |

---

## 能力判定规则（重要）

配置大模型前，场景对应的 app 必须具备对话能力，否则不应该配置。

**判定条件：** app 的 `auths[]` 中存在以下任一 authKey，且未过期：

- `LLM_TOKENS_NUM` - Token 授权
- `LLM_DIALOG_NUM` - 对话次数授权
- `LLM_DOC_NUM` - 文档数授权

**"未过期"的判定：**
- `licState != "invalid"`
- `authStatus == 1`
- `effectEtime > 当前时间戳`（或 effectEtime 为 null）

`bind` 命令内置了此检查，无能力的 app 会被直接拒绝，不会写入任何配置。也可单独用 `caps` / `check` 查询。

---

## 标准工作流

### 完整配置流程

```
查询服务 → 检查能力 → 选择/创建模型 → 绑定场景 → 发布 → 完成
   ↓           ↓            ↓            ↓        ↓
scene/query  check      list/create    bind   publish
```

### 示例：给场景配置官方模型

```bash
python xfyun_model_manage.py check 335668583902351360    # 确认有能力
python xfyun_model_manage.py bind 335668583902351360 "Spark V4.0"
python xfyun_model_manage.py publish 335668583902351360
```

### 示例：创建自有模型并配置

```bash
python xfyun_model_manage.py create "我的模型" "my_model" "描述" "https://api.example.com/chat"
# （交互式输入 apiKey）
python xfyun_model_manage.py bind 335668583902351360 "我的模型"
python xfyun_model_manage.py publish 335668583902351360
```

---

## 密钥安全最佳实践

### 两阶段安全更新（推荐给自动化/skill 集成）

当需要更新密钥但不希望密钥出现在命令行或对话中时：

**阶段 1：** 创建待填写文件
```python
with open('密钥待填写.txt', 'w', encoding='utf-8') as f:
    f.write('API_KEY=')
```

**阶段 2：** 用户填写后，运行 `scripts/secure_update_key.py`
- 读取密钥（不显示完整内容）
- 显示脱敏版确认
- PUT 更新
- 立即删除密钥文件

参考 `scripts/secure_update_key.py`，按需修改目标模型名。

### 安全要点

1. 所有查询输出、导出文件**自动脱敏**
2. 密钥**加密存储**在 `<plugin-root>/.runtime/secrets/`，不落明文
3. `create`/`update` 不接受命令行传 apiKey，走交互输入
4. debug 输出自动过滤敏感字段
5. 完整密钥只存在于加密文件和内存中，不进入日志

---

## 常见问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 返回 code=80000 | 登录失效或 Cookie 域不对 | 删除 xfyun_cookies.json 重新登录 |
| bind 被拒绝 | app 无对话能力 | 用 caps 查授权，换有能力的场景 |
| 配置不生效 | 忘记 publish | 运行 publish <sceneId> |
| 更新模型返回 method not supported | 用了 POST | model/info 必须用 PUT |
| create 后 apiKey 是空 | 交互输入被跳过 | 确认输入流程走完 |
| 浏览器不弹出 | playwright 未装 chromium | playwright install chromium |
| 文档一直"处理中(段落0)" | 拆分时 categoryID 为空 | 重传文档，用工具默认分类或 --category 指定 |
| 对话不引用知识库 | 调用链没含 docqa | 跑 enable，或 chain <sceneId> docqa,xinghuo |
| 换模型后知识库失效 | bind 重置了调用链 | 换模型后重跑 enable 把 docqa 加回 |
| 对话报 domain can not be blank | nlpExtra domain 为空 | 重跑 enable/bind 补全 domain |
| 背景图/资产返回 403 Forbidden | 默认资产 URL 已过期 | 换有效的资产 URL（curl -I 验证 200）|
| 直播项目无法发布 | 脚本为空或未启用 | 脚本需有 content 且 disable=0 |
| 形象/发音人不生效 | 资产未授权给 appId | 调 app/auth_asset 授权（create 已自动处理）|
| 场景创建报"超过场景授权数量" | 账号场景配额已满 | 删除旧场景后重试 |
| SDK 初始化成功但连不上（600003 / Expected HTTP 101 但收到 200）| 未显式 setServerUrl，走了 AAR 内置测试地址 | SDK 端设 serverUrl=wss://avatar.cn-huadong-1.xf-yun.com/v1/interact |
| SDK 接口场景连上即断（connect_success 后立刻 disconnect）| 接口场景不含形象/发音人 | SDK 端 AvatarParams 传 avatarId+vcn，并用 xfyun_interface.py auth-avatar 授权 |
| 默认形象 110117026 授权失败 | 可授权资产因账号而异，不能硬编码 | 用 auth-avatar 探测本账号实际可授权的 avatarId（如 118801001）|
| 各接口间歇性 ProxyError('Unable to connect to proxy') | session 继承了机器代理环境变量 | 已在 build_session 设 trust_env=False 直连修复 |

---

## 版本与维护

- Python 3.8+（cryptography 建议 3.9+）
- 所有脚本编码用 UTF-8
- Windows 控制台若显示乱码，是 GBK 编码问题，不影响功能

### 工具能力总览

| 工具 | 一句话职责 | 是否自动跳浏览器 |
|------|-----------|:---:|
| xfyun_common.py | 登录会话 + HTTP 封装（核心） | - |
| xfyun_secrets.py | 密钥脱敏/加密/输入（核心） | - |
| xfyun_query_services.py | 查询场景 + API 密钥 | - |
| xfyun_model_manage.py | 模型创建/修改/绑定/发布 | - |
| xfyun_knowledge.py | 知识库建库/上传/向量化/关联对话 | - |
| xfyun_template.py | Web 对话模板：创建+授权+发布 | ✅ 访问链接+配置页面 |
| xfyun_live.py | 直播项目：10步创建+授权+发布 | ✅ 直播间+配置页面 |

> `xfyun_template.py` 和 `xfyun_live.py` 创建后自动发布并跳转浏览器（复用登录态），加 `--no-browser` 可跳过。

