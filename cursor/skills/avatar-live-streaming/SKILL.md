---
name: avatar-live-streaming
description: 虚拟人直播项目（营销带货）创建工具。由 avatar-workflow-entry 路由调用。触发条件：已明确要创建直播项目，需配置商品/分镜/脚本。
---

# avatar-live-streaming: 虚拟人直播项目

## ⚙️ 运行位置（从任意项目调用时必读）

本 skill 依赖的平台脚本与配置在固定位置：
- 工具根目录：`<plugin-root>`（插件安装目录，Cursor 自动解析为真实路径）
- 脚本 `tools/xfyun_live.py` · 工具注册表 `config/tools.yaml`

正文中的 `python tools/xxx.py` 等**相对路径均以该根目录为基准**。
从其他项目目录执行时，先 `cd "<plugin-root>"` 再运行，或改用绝对路径前缀。
依赖：Python 3.8+ 与 requests/playwright/cryptography；首次使用需浏览器登录（见 avatar-credentials）。

## 定位

创建虚拟人**直播带货**项目（营销场景），一条龙完成 10 步配置 + 资产授权 +
商品/分镜/脚本，创建后自动发布并给出直播间链接。

**调用时机**:
- 搭建数字人直播间 / 虚拟主播带货
- 需要自动配好商品、分镜、直播脚本的完整直播项目

**注意**: 直播是较复杂的营销场景（sceneType=6），与普通对话/Web 模板不同。

---

## 核心工作流

```bash
# 创建直播项目（一条龙，默认形象晓姿/发音人灵小琪）
python tools/xfyun_live.py create <appId> "直播间名称" --desc "描述"

# 自定义形象和发音人
python tools/xfyun_live.py create <appId> "直播间名称" --anchor <anchorId> --vcn <vcn>

# 只建不开浏览器（脚本/批量）
python tools/xfyun_live.py create <appId> "直播间名称" --no-browser

# 列出账号下的直播场景
python tools/xfyun_live.py list

# 查询某个直播场景详情
python tools/xfyun_live.py query <sceneId>
```

**命令一览**:

| 命令 | 用法 | 类型 |
|------|------|------|
| `create` | `create <appId> <name> [--desc D] [--anchor ID] [--vcn V] [--no-browser]` | 写 |
| `list` | `list` | 只读 |
| `query` | `query <sceneId>` | 只读 |

## create 的 10 步一条龙

1. 查询应用信息（验证 appId）
2. 创建场景（sceneType=6 直播场景，templateId=17）
3. 配置模板（形象/发音人/背景/画布组件）
4. 配置 NLP（星火大模型）
5. 配置交互（欢迎语/识别参数）
6. 授权发音人（assetType=3，assetScene=2）
7. 授权形象（assetType=1，assetScene=2）
8. 创建默认商品（"商品1"）
9. 创建默认分镜（"分镜1"）
10. 添加默认脚本（**带内容且启用**，否则无法发布）

之后自动发布 → 打开直播间链接 + 配置页面。

**默认配置**: 形象 晓姿-蓝色制服 `110117026`｜发音人 灵小琪 `x4_lingxiaoqi_oral`｜商品/分镜/脚本各 1 个（脚本已启用）。

---

## 关键约束（HARD-GATE）

1. **脚本必须有内容且启用**（disable=0）才能发布 — 空脚本无法发布（create 已自动带默认脚本）
2. **资产授权自动处理** — 发音人/形象授权失败会警告但继续；部分资产可能需人工授权
3. **发布后即可访问** — 创建流程末尾自动发布，直接打开直播间链接看效果
4. **场景配额限制** — 报"超过场景授权数量"说明账号配额满，需先删旧场景
5. **浏览器免登录** — 复用 `xfyun_cookies.json` 登录态

---

## 验证清单

- [ ] appId 有效（create 第 1 步验证）
- [ ] 直播场景已创建（拿到 sceneId）
- [ ] 商品/分镜/脚本已配（create 自动，脚本启用）
- [ ] 已发布（create 末尾自动）
- [ ] 直播间链接能打开

---

## 交付收尾（必做）

直播间创建并发布后，记录交付物并上报完成：

```bash
mkdir -p .runtime && cat > .runtime/artifacts.json <<'EOF'
{"live_url": "<直播间链接>", "anchor_id": "<anchorId>"}
EOF
python "<plugin-root>/tools/telemetry.py" complete --type live_streaming
```

未发布成功时**不要**执行。

---

## 相关技能

- `avatar-credentials`: 获取 appId 等凭据
- `avatar-model-config`: 确认/配置对话能力
- `avatar-web-template`: 非直播的 Web 对话模板应用
- `avatar-config-authoring`: 直播间形象/背景等配置调整
