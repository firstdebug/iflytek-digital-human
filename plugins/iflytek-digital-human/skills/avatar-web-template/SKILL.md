---
name: avatar-web-template
description: >-
  使用讯飞官方预设模板创建 Web 对话应用（零代码生成可访问链接）。由 avatar-workflow-entry
  路由调用，不应直接匹配用户的宽泛需求。触发条件：已明确要使用官方模板（templateId 1/3/4/7/11）且有 appId。
---

# avatar-web-template: Web 对话模板应用

## 准入凭证自检（HARD-GATE）

实施前必须执行 `python tools/telemetry.py consent --validate-gate`。只有返回
`valid (accepted)` 或 `valid (declined)` 才能继续；缺少、格式错误或与当前
`consent --status` 不一致的 `.runtime/gate-consent.json` 必须拒绝执行，并回到
`avatar-consent-gate`。

## ⚙️ 运行位置（从任意项目调用时必读）

本 skill 依赖的平台脚本与配置在固定位置：
- 工具根目录：`<plugin-root>`（插件安装目录，Codex 自动解析为真实路径）
- 脚本 `tools/xfyun_template.py` · 工具注册表 `config/tools.yaml`

正文中的 `python tools/xxx.py` 等**相对路径均以该根目录为基准**。
从其他项目目录执行时，先 `cd "<plugin-root>"` 再运行，或改用绝对路径前缀。
依赖：Python 3.8+ 与 requests/playwright/cryptography；首次使用需浏览器登录（见 avatar-credentials）。

## 定位

用讯飞官方**预设模板**快速生成一个开箱即用的 Web 对话应用（无需自己写前端），
自动完成场景/模板/NLP/交互 4 步配置 + 资产授权，创建后自动发布并给出可访问链接。

**调用时机**:
- 想快速要一个能直接访问的对话页面（智能客服 / H5 / 大屏）
- 不想自己搭前端工程，用官方模板即可
- 已有对话能力的 appId，只差一个前端载体

**与相关 skill 的区别**:
- 与 `avatar-executing`（自建前端工程）不同：这里用官方现成模板，零代码
- 与 `avatar-config-authoring` 不同：这里是"从模板创建应用"，不是改已有项目配置

---

## 可用模板（templateId）

| ID | 名称 | 尺寸/说明 |
|----|------|-----------|
| 1 | 大屏交互对话 | 1920x1080，带引导词/识别展示/NLP 展示 |
| 3 | Web 智能客服 | 1920x1080，横屏 Web 客服 |
| 4 | Web 智能客服-横屏弹窗 | 1920x1080，弹窗模式 |
| 7 | H5-对话模板 | 1080x1920，移动端对话 |
| 11 | H5-通话模板 | 1080x1920，移动端通话（含语音按钮） |

## 核心工作流

```bash
# 1. 列出可用模板
python tools/xfyun_template.py list-templates

# 2. 创建应用（一条龙：4步配置 + 资产授权 + 自动发布 + 跳转浏览器）
#    交互场景默认这样调（不加 --no-browser），完成后自动打开浏览器让用户立刻测试对话：
python tools/xfyun_template.py create <templateId> <appId> "应用名称" --desc "描述"
#   完成后自动打开 2 个标签页：访问链接 + 配置页面
#   ⚠️ 仅批量创建 / CI / 无头脚本场景才加 --no-browser（跳过浏览器，仅打印链接）

# 3. 可选：更新背景 / 形象后重新发布
python tools/xfyun_template.py update-bg <sceneId> ./background.jpg
python tools/xfyun_template.py update-avatar <sceneId> <anchorId> <vcn> --app <appId>
python tools/xfyun_template.py publish <sceneId> --domain <域名> --expire <毫秒时间戳> --app <appId>
```

**命令一览**:

| 命令 | 用法 | 类型 |
|------|------|------|
| `list-templates` | `list-templates` | 只读 |
| `create` | `create <templateId> <appId> <name> [--desc D] [--no-browser]` | 写 |
| `update-bg` | `update-bg <sceneId> <图片路径>` | 写 |
| `update-avatar` | `update-avatar <sceneId> <anchorId> <vcn> [--app appId]` | 写 |
| `publish` | `publish <sceneId> [--domain D] [--expire TS] [--app appId] [--no-browser]` | 写 |

---

## 关键约束（HARD-GATE）

0. **appId 必须是 appType=2（标准产品类）+ 有效 + 具备「Web对话系统」能力** — ⚠️ **最先检查这一条，且必须用正确命令查**。

   **正确查法**：`python tools/xfyun_query_services.py list-apps`（**不是**默认的 `list` / 不带参数——那个查的是「场景」，看不到 appType，会误判！）。`list-apps` 会逐个应用列出：
   - `应用类型: 2 - 标准产品(Web模板/直播)` ← 模板必须是 2；`1 - 接口能力(SDK/WebAPI)` 不行
   - `是否有效: 是/否` ← 过期的标准产品应用也不能用，需续订
   - `标准产品能力: ...Web对话系统...` ← 必须包含「Web对话系统」

   **判定**：选一个「appType=2 且有效 且含 Web对话系统」的 appId 才能建模板。
   - 若有符合的 → 用它 create
   - 若标准产品应用全部过期 → 去控制台续订：https://virtual-man.xfyun.cn/console/applications/
   - 若账号下只有 appType=1 → 去控制台新建标准产品类应用（需用户手动，可能付费），或改走 SDK 自建工程路线（avatar-executing）

   **切勿用查场景的结果判断 appType**——那是上一版踩过的坑：默认 `list` 查场景查不到应用类型，导致走到 create 才被硬门禁拦下。
1. **appId 需有对话能力** — 创建前用 `python tools/xfyun_model_manage.py check <sceneId>` 确认授权
2. **资产授权是关键** — 形象/发音人必须先授权给 appId 才生效（create/update-avatar 已自动处理）
3. **配置后需重新发布** — update-bg/update-avatar 修改后，必须再次 `publish` 才生效
4. **模板预设不可变** — 每个模板的 widgets 布局、尺寸为固定预设，不能改
5. **背景图 URL 可能过期** — 官方默认背景旧 URL 报 403 时需换新图（`curl -I` 验证 200）
6. **浏览器免登录** — 跳转时复用 `xfyun_cookies.json` 登录态
7. **交互模式默认打开浏览器** — create/publish 命令由 Claude 执行且**默认不加 `--no-browser`**，
   让脚本自动打开浏览器标签页（访问链接 + 配置页），用户可立刻测试对话。**切勿**只把链接
   打印出来让用户自己复制粘贴去浏览器打开。只有批量创建 / CI / 无头场景才用 `--no-browser`。
8. **命令由 Claude 执行** — 所有 `python tools/...` 命令用 Bash/PowerShell 工具直接跑，
   不要让用户在输入框自己输命令。用户只负责浏览器里的人类动作（扫码、测试对话）。

---

## 决策分支

```
Web 对话模板任务
├── 不知道选哪个模板 → list-templates 看 5 个预设
├── 创建应用
│   ├── 先确认对话能力 → xfyun_model_manage.py check <sceneId>
│   ├── create <templateId> <appId> <name>（自动配置+授权+发布）
│   └── 拿到访问链接
├── 调整外观
│   ├── 换背景 → update-bg → publish
│   └── 换形象/发音人 → update-avatar → publish
└── 绑定域名/有效期 → publish --domain --expire
```

---

## 验证清单

- [ ] appId 具备对话能力（check 通过）
- [ ] 模板应用已创建（拿到 sceneId + 访问链接）
- [ ] 形象/发音人已授权（create 自动处理）
- [ ] 已发布（publish 执行）
- [ ] 访问链接能打开对话页面

---

## 交付收尾（必做）

拿到可访问链接后，把交付物记录到 `.runtime/artifacts.json` 并上报完成：

```bash
mkdir -p .runtime && cat > .runtime/artifacts.json <<'EOF'
{"template_url": "<实际访问链接>", "scene_id": "<sceneId>"}
EOF
python "<plugin-root>/tools/telemetry.py" complete --type web_template
```

链接未生成或未发布成功时**不要**执行上述命令。

---

## 相关技能

- `avatar-credentials`: 获取 appId 等凭据
- `avatar-model-config`: 确认/配置对话能力（前置）
- `avatar-knowledge-base`: 给模板应用挂知识库
- `avatar-live-streaming`: 直播场景的模板（营销带货）
- `avatar-config-authoring`: 已有项目的配置调整
