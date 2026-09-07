---
name: avatar-credentials
description: >-
  平台凭据获取与验证工具。由 avatar-workflow-entry
  路由调用。触发条件：已明确需要创建接口服务、获取/验证凭据（appId/apiKey/apiSecret/sceneId 等）。
tags:
  - credentials
  - auth
  - verification
  - avatar
priority: critical
optional_tools:
  - name: query-services
    when: 用户已登录控制台，可自动获取凭据
    fallback: 交互式手动输入
  - name: xfyun-login
    when: 需要自动登录控制台
    fallback: 手动登录
---

# avatar-credentials: 凭据获取和验证

## ⚙️ 运行位置（从任意项目调用时必读）

本 skill 依赖的平台脚本与配置在固定位置：
- 工具根目录：`${CLAUDE_PLUGIN_ROOT}`（插件安装目录，Claude Code 自动解析为真实路径）
- 脚本 `tools/xfyun_*.py` · 工具注册表 `config/tools.yaml`

正文中的 `python tools/xxx.py`、`config/tools.yaml` 等**相对路径均以该根目录为基准**。
从其他项目目录执行时，先 `cd "${CLAUDE_PLUGIN_ROOT}"` 再运行，或改用绝对路径前缀。
依赖：Python 3.8+ 与 requests/playwright/cryptography；首次使用需浏览器登录。

## 定位

引导用户获取虚拟人平台凭据，并验证凭据有效性。

**调用时机**:
- `avatar-preflight` Layer 1 凭据验证
- 凭据配置错误时
- 首次接入时

---

## 必需凭据清单

```yaml
凭据类型: 说明
  appId: 应用ID，在控制台创建应用后获取
  apiKey: API 密钥
  apiSecret: API 密钥对（用于签名）
  sceneId: 接口服务ID，需发布后才有效
  avatarId: 形象ID，需要授权才能使用
  vcn: 发音人ID，与形象绑定
```

**官方接入指南**: https://www.yuque.com/xnrpt/bbc1du/usyebvyczgcy23pk
**控制台地址**: https://virtual-man.xfyun.cn/console/projects
**WebSocket 地址**: wss://avatar.cn-huadong-1.xf-yun.com/v1/interact

`WS_URL 是平台常量`，不是用户凭据，也不是可选输入。必须由 `write_env_safe.py` 自动写入；不得询问用户、
不得接受模型生成的替代 host/path。打开项目控制台必须执行：

```bash
python "${CLAUDE_PLUGIN_ROOT}/tools/xfyun_common.py" projects
```

不得自行拼接控制台 URL 或用 `start https://...` 绕过该命令。

---

## 核心工作流概览

| 阶段 | 目标 | 详见 |
|------|------|------|
| 0. 工具检测 | 检测是否有自动化工具（query-services）| 本页 "工具增强" |
| 1. 登录与应用检查 | 登录平台 → 检查应用列表 → 判断 appType/授权 | `references/app-authorization-check.md` |
| 2. 控制台获取 | 申请服务 → 创建接口项目 → 发布 → 获取 6 项凭据 | `references/console-setup-guide.md` |
| 3. 交互式引导 | 逐步引导用户输入凭据、保存到 `.env` | `references/interactive-guide.md` |
| 4. 格式验证 | 本地正则校验凭据格式 | `references/validation.md` |
| 5. 在线验证 | WebSocket 连接测试凭据有效性 | `references/validation.md` |
| 6. 排障 | 根据错误码定位问题 | `references/error-codes.md` |

---

## 工具增强（自动化获取凭据）

如果用户提供了 `xfyun-tools`（见 `config/tools.yaml`）：

### 检测流程
```bash
# 检测工具是否存在
if [ -f tools/xfyun_query_services.py ]; then
    echo "✅ 检测到讯飞工具集"
    # 询问用户是否使用自动获取
fi
```

### 自动获取流程（推荐）

**第 0 步：切换到插件根目录（HARD-GATE）**
```bash
# 所有工具调用必须在插件根目录执行
cd "${CLAUDE_PLUGIN_ROOT}"
# 插件根目录示例：<安装路径>\.claude\skills\avatar-platform\1.0.0
```

**第 1 步：验证登录状态**
```bash
# 检查 cookie 是否存在
ls tools/xfyun_cookies.json

# 如果不存在或过期，拉起浏览器登录
python tools/xfyun_common.py login
# 浏览器弹出登录页 → 用户完成登录 → 自动保存 cookie
# 强制重新登录：python tools/xfyun_common.py login --force
```

**第 2 步：查询场景列表（密钥自动脱敏）**
```bash
python tools/xfyun_query_services.py

# 输出格式（密钥已脱敏）:
# [场景 1]
#   场景名称: 学习帮手
#   场景 ID:  336130030977552384
#   App ID:   YOUR_APP_ID
#   API Key:    xxxx********xxxx
#   API Secret: xxxx********xxxx
```

**第 3 步：写入完整凭据到 .env（密钥不进对话）**
```bash
# 使用安全脚本，完整密钥从平台 API 获取，直接写入 .env
python tools/write_env_safe.py <app_id> <scene_id> <output_path>

# 示例
python tools/write_env_safe.py YOUR_APP_ID 336130030977552384 ~/.env

# 输出（仅显示脱敏版本）：
# [OK] API Key:    xxxx********xxxx
# [OK] API Secret: xxxx********xxxx
# [完成] 凭据已写入: <项目路径>/.env
# [安全] 密钥未打印到控制台，仅存储在本地文件
```

**第 4 步：确认默认配置（自动完成）**

工具会自动设置通用默认值：
- 形象 ID：`111310001`
- 发音人：`x4_lingxiaoqi_oral`

这些值适用于大多数场景，无需手动调整。

### 执行分工（HARD-GATE：主动执行，最小化用户手动操作）

- **Claude 负责**：执行**所有** python 命令、`cd` 切换目录——用 Bash/PowerShell 工具直接跑。
- **用户负责**：仅浏览器弹出后的**人类动作**（扫码、输入账号密码、在页面上确认订阅）。
- **切勿**让用户自己在输入框输命令（如 `! cd ... && python ...`）。登录命令由 Claude 执行，
  脚本会自动拉起浏览器；把命令推给用户是错误做法。
- **理解要点**："需要用户手动操作"指的是浏览器里人类才能完成的动作，**不是**让用户代跑命令。
- **所有工具调用前必须 `cd "${CLAUDE_PLUGIN_ROOT}"`**，否则相对路径失效。

### ⚠️ HARD-GATE：给交互式脚本喂 stdin（Windows 密钥错位血泪教训）

`xfyun_model_manage.py create/update` 需要输入 apiKey（`prompt_secret`，getpass/input 交互）。
**Windows 下必须用 cmd.exe 的 `<` 文件重定向喂 stdin，严禁 PowerShell 对象管道**。

- ❌ **错误**：`Get-Content resp.txt | python tools\xfyun_model_manage.py create ...`
  或 `"2`n$key`ny" | python ...` —— PowerShell 对象管道喂 Python stdin **行序会错乱**，
  实测把正确密钥 `sk-35b...` 存成了错位的 `s-7f41...`（getpass 分支在管道下不可靠）。
- ✅ **正确**：cmd 重定向给真实文件句柄，`prompt_secret` 的"方式2 从文件读取"稳定逐行读：
  ```powershell
  # 1) 密钥单独存文件（api.txt 有多行, 只取 api: 行去前缀 4 字符）
  $key = (Get-Content api.txt | Where-Object { $_ -like 'api:*' }).Substring(4).Trim()
  $kf = Join-Path $env:TEMP 'dskey.txt'; Set-Content $kf -Value $key -NoNewline -Encoding ascii
  # 2) 响应文件: 选2(从文件读取) → 密钥文件路径 → y(确认) → y(读后删除)
  $resp = Join-Path $env:TEMP 'resp.txt'; Set-Content $resp -Value @('2',$kf,'y','y') -Encoding ascii
  # 3) cmd 重定向（PowerShell 5.1 不支持 < , 用 cmd 包一层）
  cmd /c "python tools\xfyun_model_manage.py create <name> deepseek-chat `"简介`" https://api.deepseek.com < `"$resp`""
  ```
- update 修改密钥同理：响应文件 `@('5','2',$kf,'y','y')`（选字段5 API Key → 方式2 → 路径 → 确认 → 删除）。
- 校验：`mask_secret(show_suffix=0)` 显示有 bug（会重复拼原串），**核对密钥看前缀 `sk-` 是否正确即可**。

### 优势
- ✅ **凭据不进对话框** —— 脚本直接从控制台 API 获取，写入 .env
- ✅ **自动脱敏显示** —— 交互时只显示脱敏值
- ✅ **支持多场景** —— 一次查询所有场景，用户选择
- ✅ **安全加密存储** —— 可选的加密本地存储（xfyun_secrets.py）

### Fallback
如果工具不存在或执行失败，自动降级到 `references/interactive-guide.md` 的手动流程。

---

## 凭据对照表

| 配置项 | 变量名 | 说明 |
|--------|--------|------|
| 应用 ID | `APP_ID` / `appId` | 控制台应用 AppId |
| 接口密钥 | `API_KEY` / `apiKey` | 控制台应用 ApiKey |
| 接口密钥 Secret | `API_SECRET` / `apiSecret` | 控制台应用 ApiSecret |
| 接口服务 ID | `SCENE_ID` / `sceneId` | 控制台接口服务 ID（必须已发布） |
| 形象 ID | `AVATAR_ID` / `avatarId` | 已授权虚拟人形象 ID |
| 发音人 | `VCN` / `vcn` | 已授权发音人标识 |

---

## 决策分支（场景 → 应读哪个 reference）

```
凭据获取任务
├── 检测到 xfyun-tools？
│   ├── YES: 使用自动化工具
│   │   ├── 登录: python tools/xfyun_common.py login（在插件根目录执行）
│   │   ├── 检查应用: POST /app/query → 判断 appType/auths (见 references/app-authorization-check.md)
│   │   │   ├── 无应用 → 问需求 → 推荐订阅类型 → 给链接 → [等用户订阅]
│   │   │   ├── 授权不足 → 提示缺什么 → 给链接重订阅 → [等用户订阅]
│   │   │   └── ✓ 正常 → 存 appType/auths/appId → 继续
│   │   ├── 查询场景: python tools/xfyun_query_services.py
│   │   ├── 用户选择场景
│   │   └── 自动写入 .env（凭据不进对话框）
│   │
│   └── NO 或失败: 降级到手动流程
│       ├── 首次接入 → references/console-setup-guide.md
│       ├── 交互输入 → references/interactive-guide.md
│       └── 格式验证 → references/validation.md
│
├── 验证凭据有效性
│   ├── 本地格式校验 → references/validation.md
│   └── 在线连接测试 → references/validation.md
│
└── 连接失败排障
    ├── 错误码查询 → references/error-codes.md
    └── 深度诊断 → avatar-network-debug
```

---

## 关键约束 / HARD-GATE

- **固定端点门禁**：`WS_URL` 必须精确等于
  `wss://avatar.cn-huadong-1.xf-yun.com/v1/interact`；host、path、query 任一不同均阻断。
- **缺凭据恢复门禁**：收到 `blocked_missing_credentials` 时，必须执行返回 JSON 中的 `next_action`：
  `xfyun_common.py login` → `xfyun_query_services.py` → 携带平台返回的精确 `appId/sceneId` 重跑
  `web_delivery.py`。不得要求用户提供 `WS_URL`、API 地址或控制台地址。
- **阻断上报**：可恢复的凭据门禁保持 workflow 为 `in_progress`，由 `web_delivery.py` 自动记录并上传
  `gate=web_delivery`、`gate_status` 和脱敏后的 `remaining_issues`；不得调用 fail/complete 抢先收口。
- **必须发布接口服务**：未发布的 scene 不能用于 SDK 连接。但通用 `avatar authentication failed`
  不能直接判定为未发布，必须转入 `avatar-troubleshoot/references/authentication-failed.md` 取证。
- **API_SECRET 只显示一次**：控制台创建后必须立即复制保存，无法二次查看。
- **只能使用已授权的形象和发音人**：未授权的 avatarId 连接时报错 10120。
- **默认并发 1 路**：超过路数报错 11203。
- **凭据格式不作为在线有效性的替代证据**：字段非空、Key/Secret 长度和固定端点只能做本地初筛；
  appId/sceneId 的归属、类型和状态以平台实时查询为准，不用历史正则拒绝平台返回的合法值。

## Red Flags

- ❌ 凭据配好但出现通用鉴权失败 → 读取 `../avatar-troubleshoot/references/authentication-failed.md`，
  依次检查真实错误码、canonical 签名、app/scene 归属、发布状态和资产授权，不得跳步定因。
- ❌ 签名错误 / apiSecret 报错（10113）→ 检查 apiSecret 拼写和签名逻辑。
- ❌ `.env` 未加入 `.gitignore` → 凭据泄露风险，必须确认 `.env`、`config/credentials.json`、`**/credentials.*` 已忽略。
- ❌ 超拟人（cnr 开头）不支持透明背景，勿用于需要透明背景的场景。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| `references/console-setup-guide.md` | 控制台 6 步获取流程、创建应用/接口服务/授权形象/发音人的详细操作与检查代码 |
| `references/interactive-guide.md` | 交互式引导完整实现（Phase 1-8）：打开浏览器、AskUserQuestion 采集、保存 `.env`、检查 `.gitignore`、完成提示 |
| `references/validation.md` | 基础/完整格式验证函数、在线连接验证函数、验证成功/失败输出格式 |
| `references/config-templates.md` | 凭据存储模板：`.env`、JSON 配置文件、Web/Android/iOS 读取代码 |
| `references/error-codes.md` | 常见错误码（10110/10113/10120/10121/11203）及修复方式 |

**排障优先级**：
- 凭据相关错误 → 先读本 skill 的 `error-codes.md`
- WebAPI 报文错误 → 读 `../avatar-webapi-protocol/references/troubleshooting.md`

---

## 验证清单

- [ ] 6 项凭据齐全（appId/apiKey/apiSecret/sceneId/avatarId/vcn）
- [ ] 格式校验通过（见 `references/validation.md`）
- [ ] 接口服务已发布
- [ ] avatarId 与 vcn 已授权
- [ ] 在线连接验证成功
- [ ] 凭据已保存到 `.env` 且 `.env` 在 `.gitignore` 中

---

## 交接协议

- **上游**: `avatar-preflight` 调用本技能验证凭据。
- **下游**: 凭据就绪后 → `avatar-artifact-download`（SDK 下载）。
- **排障移交**: 连接失败无法通过错误码解决时 → `avatar-network-debug`。
