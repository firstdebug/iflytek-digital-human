# Codex→Claude 技能包迁移完成报告

## 执行摘要

**状态**: ✅ 完成  
**测试**: 45/45 通过  
**修改文件**: 57 个  
**新增文件**: 5 个（delivery-modes.md、android-gradle-stability.md、3 个测试文件）

---

## 五大修改组

### Group 1: 运行数据与凭据安全 ✅

**目标**: Cookie 和密钥迁移到插件根目录 `.runtime/`，支持环境变量覆盖，原子写入，权限控制。

| 文件 | 修改内容 |
|------|----------|
| `tools/xfyun_secrets.py` | `SECRETS_DIR` 改为 `resolve_secrets_dir()` → `.runtime/secrets/`；`mask_secret` 修复 `show_suffix=0` 不泄露原值 |
| `tools/xfyun_common.py` | `COOKIE_FILE` 改为 `resolve_cookie_file()` → `.runtime/xfyun_cookies.json`；`save_cookies` 原子写入 + chmod 0600 |
| `tools/xfyun_query_services.py` | 删除重复登录栈（`do_browser_login`/`wait_for_login`/`save_cookies`），改用 `xc.get_session()` |
| `tools/write_env_safe.py` | `find_app_record` 精确匹配 appId；`resolve_output_path` ~展开；`build_env_content` 默认 `111310001` |
| `tools/xfyun_live.py` | `DEFAULT_ANCHOR_ID` 改为 `111310001` |
| `.gitignore` | `.runtime/`、`xfyun_cookies.json`、`.env` |

**验证**: `test_runtime_security.py` 11 个测试全部通过。

---

### Group 2: Skill 内容和一致性 ✅

**目标**: frontmatter name 与目录名一致，tools.yaml YAML 语法修复，硬编码路径改为 `${CLAUDE_PLUGIN_ROOT}`。

| 项目 | 修改内容 |
|------|----------|
| `config/tools.yaml` | YAML 语法修复（8 个 `array` 块）；anchor 默认 `111310001`；secrets 路径注释 |
| 8 个 skill frontmatter | `name: avatar-X` → `name: X`（action-control、audio-driver、full-duplex、subtitle-setup、text-driver、text-interact、transparent-bg、voice-interact） |
| 跨 skill 引用 | 所有 backtick 引用更新为新名称 |
| `avatar-workflow-entry/SKILL.md` | 删除 lowercase skill.md 错误说明，技能数量描述简化 |
| 硬编码路径 | `D:/avatar-platform-plugin` → `${CLAUDE_PLUGIN_ROOT}`；`/home/user/.env` → `<项目路径>/.env`；`~/.xfyun` → `<plugin-root>/.runtime/secrets` |
| `tools/README.md`, `tools/xfyun_model_manage.py`, `skills/avatar-credentials/SKILL.md` | 同上路径替换 |

**验证**: `test_plugin_consistency.py` 23 个测试全部通过；`tools.yaml` 可解析，33 个工具，0 重复。

---

### Group 3: Android Gradle 稳定构建 ✅

**目标**: 串行构建、国内镜像、超时处理、缓存锁诊断。

| 文件 | 修改内容 |
|------|----------|
| `skills/shared/android-gradle-stability.md` | 从 Codex 复制（118 行，串行原则、超时后强制流程、禁止盲目 clean） |
| `skills/avatar-executing/templates/android-build-template/gradle.properties` | `Xmx2048m` → `1280m`；`parallel=true` → `false`；`workers.max=2` |
| `skills/avatar-executing/templates/android-build-template/settings.gradle.template` | 添加腾讯云、华为云镜像（pluginManagement + dependencyResolutionManagement） |
| `skills/shared/SKILL.md` | 索引 `android-gradle-stability.md` |
| `skills/avatar-workflow-entry/SKILL.md` | 引用稳定构建文档 |
| `skills/toolchain/SKILL.md` | Android 检查表引用稳定构建 |
| `skills/avatar-executing/SKILL.md` | Step 2 构建门禁引用稳定构建 |
| `skills/avatar-troubleshoot/SKILL.md` | Gradle 故障诊断引用稳定构建 |
| `skills/avatar-verification/SKILL.md` | 验收构建引用稳定构建 |

**验证**: `test_plugin_consistency.AndroidGradleStabilityTests` 6 个测试全部通过。

---

### Group 4: 快速与严格交付模式 ✅

**目标**: `workflow_mode: quick | strict`，quick 跳过过程文档，strict 保留完整评审；两个必问门禁（交付模式、语音能力）。

| 文件 | 修改内容 |
|------|----------|
| `skills/shared/delivery-modes.md` | 新建（103 行）：模式选择、必问门禁、Token 纪律、两种模式都不能跳过的安全检查 |
| `skills/shared/SKILL.md` | 索引 `delivery-modes.md` |
| `skills/avatar-workflow-entry/SKILL.md` | 添加两个 HARD-GATE（交付模式门禁、语音能力门禁）；删除强制三阶段规则，改为按模式分流 |
| `skills/avatar-workflow-entry/references/routing-rules.md` | 意图优先级、语音扩展路由带 `gate: HARD-GATE`、边界规则 |
| `skills/avatar-workflow-entry/references/examples.md` | 示例 3 添加模式门禁；新增示例 5（给现有项目加语音必须先确认） |
| `skills/avatar-brainstorming/SKILL.md` | 接收 `workflow_mode`；quick 不创建 design-spec、不调用 spec-reviewer |
| `skills/avatar-planning/SKILL.md` | quick 直接跳过本阶段 |
| `skills/avatar-executing/SKILL.md` | 接收 `workflow_mode`；共同前置门禁（语音确认、凭据验证、Android 稳定构建）；Red Flags 添加语音和模式违规 |
| `skills/avatar-verification/SKILL.md` | 接收 `workflow_mode`；quick 不创建报告但不降低验证覆盖 |

**验证**: `test_workflow_gates.WorkflowModeIntegrationTests` 5 个测试全部通过。

---

### Group 5: 必须询问的硬门禁（语音） ✅

**目标**: 新增语音能力前必须用 `AskUserQuestion` 确认，确认交互形态（按住说话 / 点击开始停止 / 自动 VAD / 全双工）。

| 文件 | 修改内容 |
|------|----------|
| `skills/voice-interact/SKILL.md` | 添加「用户确认门禁（HARD-GATE）」，用 `AskUserQuestion` 确认语音 + 交互形态；未确认前不得改 Manifest/Info.plist、不得加 `RECORD_AUDIO`、不得写录音代码 |
| `skills/avatar-permissions-setup/SKILL.md` | 添加「权限修改门禁」，新增能力时必须先问；排查已有错误时可直接修复 |
| `skills/avatar-executing/SKILL.md` | Red Flags 添加「用户未选择语音却加入麦克风权限 → 违反语音门禁」 |
| `skills/avatar-workflow-entry/references/routing-rules.md` | 语音扩展路由添加 `gate: HARD-GATE` |
| `skills/avatar-workflow-entry/references/examples.md` | 示例 5（给现有项目加语音）展示完整门禁流程和反例 |

**验证**: `test_workflow_gates.VoiceGateTests` 6 个测试全部通过。

---

## 测试覆盖

```
tests/test_runtime_security.py         11 tests  ✅
tests/test_plugin_consistency.py       23 tests  ✅
tests/test_workflow_gates.py           11 tests  ✅
                                       ─────────
                                       45 tests  ✅
```

**关键测试**:
- Cookie/secrets 路径解析和环境变量覆盖
- mask_secret 零后缀不泄露原值
- write_env_safe 精确匹配 appId、~展开、默认 111310001
- query_services 不重复登录栈
- frontmatter name 与目录名一致
- tools.yaml 可解析、工具名不重复、脚本存在、命令存在
- 无机器特定路径（C:\Users\、D:/、/home/user/、~/.xfyun）
- Gradle 稳定性合约（串行、镜像顺序、超时处理）
- workflow_mode 完整集成（5 个主流程 skill 都接收并处理）
- 语音门禁完整性（voice-interact、permissions-setup、executing Red Flags、routing-rules、examples）

---

## 关键差异：Codex vs Claude

| 维度 | Codex 约定 | Claude 约定 |
|------|------------|-------------|
| Skill 目录命名 | 强制 `avatar-*` 前缀 | 不强制前缀，但 frontmatter `name` 必须等于目录名 |
| 询问工具 | 无原生询问工具，需自建或用 agent | `AskUserQuestion`（Claude 原生） |
| Frontmatter 键 | 仅 `name`/`description` | 允许 `tags`/`priority`/`required_tools`/`optional_tools` |
| 三阶段流程 | 强制完整走完（brainstorming → planning → executing） | 按 `workflow_mode` 分流：quick 跳过文档，strict 保留完整流程 |
| 语音能力扩展 | "工程明确、目标明确 → 直接实施" | 必须先用 `AskUserQuestion` 确认能力和交互形态 |

---

## 迁移原则

1. **路径可移植性优先**：凭据、Cookie、密钥全部迁移到 `.runtime/`，支持环境变量覆盖，删除所有硬编码用户路径。
2. **遵循 Claude 命名约定**：frontmatter `name` 等于目录名；不强制 `avatar-` 前缀。
3. **利用 Claude 原生能力**：用 `AskUserQuestion` 实现门禁，不自建询问机制。
4. **保留 Codex 的安全和稳定性规则**：Android Gradle 稳定构建、语音门禁、凭据安全检查完整移植。
5. **快速与严格模式分流，不降低安全门槛**：`quick` 跳过过程文档和评审，但凭据验证、资源授权、构建验证、语音确认门禁两种模式都执行。

---

## 剩余工作（可选）

- [ ] 移植更多 Codex 侧的 skill references（如有）
- [ ] 添加 `tests/__init__.py`（Python 包结构，非必需）
- [ ] CI/CD 集成（GitHub Actions / GitLab CI）
- [ ] 用户文档更新（README.md 添加快速开始、测试运行、环境变量说明）

---

## 验收清单

- [x] 所有工具脚本使用 `.runtime/` 作为默认运行数据目录
- [x] `xfyun_query_services.py` 不重复登录逻辑
- [x] `mask_secret(value, show_suffix=0)` 不泄露原值
- [x] `write_env_safe.py` 精确匹配 appId、默认 111310001
- [x] `.gitignore` 包含 `.runtime/`、`xfyun_cookies.json`、`.env`
- [x] `tools.yaml` YAML 语法有效，33 个工具全部解析
- [x] 8 个 skill frontmatter `name` 与目录名一致
- [x] 所有 backtick skill 引用指向存在的 skill
- [x] 无机器特定路径（C:\Users\、D:/、~/.xfyun）
- [x] Android Gradle 模板：串行构建、1280m、镜像顺序正确
- [x] `android-gradle-stability.md` 被 5 个构建相关 skill 引用
- [x] `delivery-modes.md` 定义 `workflow_mode: quick | strict`
- [x] 5 个主流程 skill 接收并处理 `workflow_mode`
- [x] 两个必问门禁（交付模式、语音能力）在 workflow-entry 和下游 skill 中强制执行
- [x] `voice-interact` 和 `avatar-permissions-setup` 有完整的语音确认门禁
- [x] `avatar-executing` Red Flags 包含语音和模式违规检测
- [x] `routing-rules.md` 和 `examples.md` 展示完整门禁流程
- [x] 45 个测试全部通过

---

**结论**: Codex 技能包已成功迁移到 Claude 约定，保留全部安全和稳定性规则，增加快速/严格交付模式和语音确认门禁。测试覆盖完整，可投入使用。
