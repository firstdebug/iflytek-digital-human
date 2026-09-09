# 反幻觉验证清单（Anti-Hallucination Checklist）

## 目标

防止 AI agent 在执行过程中出现"基于常识推理而非实际代码/文档"的幻觉问题。

---

## 核心原则

### ❌ 禁止的行为模式
1. **假设 API 端点**：根据"常见 REST 风格"拼接 URL
2. **臆测数据结构**：凭"经验"假设 JSON 返回格式
3. **猜测文件内容**：在未 Read 的情况下进行 Edit
4. **忽略返回码**：看到标准输出文本就认为成功
5. **编造外部链接**：根据"常见控制台 URL 模式"生成链接

### ✅ 强制的验证流程
1. **Read → Understand → Use**：必须先读取源码/文档，理解后再使用
2. **Verify Exit Code**：工具调用后检查返回码，不依赖输出文本
3. **Admit Uncertainty**：不确定时说"我不知道"，而非编造答案
4. **Explicit Sources**：每个断言必须注明来源（文件路径 + 行号）

---

## 分类检查清单

### 0. Web SDK 交付链（低自由度）

对 Web SDK 自建工程，不允许模型手工拼接凭据、服务生命周期或完成上报。统一运行
`tools/web_delivery.py run`：首次运行准备凭据/SDK/服务/端口并打开浏览器；真实运行证据产生后再次运行同一命令，才进入最终 gate。不得直接读取或回显 `.env`，不得手写 `.runtime/web-runtime-evidence.json`，不得杀掉全部 Node 进程或在重启时改端口。

端点只能从 `tools/platform_endpoints.py` 取得；真实错误 URL 不写入反例文本，避免检索截断后把反例当答案。
退出码 2 必须执行 JSON `next_action`；退出码 2/3 的门禁状态由状态机自动上报，模型不得自行改终态。

### A. API 调用前（防止端点幻觉）

**触发场景**：需要调用 HTTP API、使用 SDK 方法、调用工具脚本

**强制步骤**：
```yaml
- [ ] Step 1: 定位源码文件（脚本/SDK 文档/playbook）
- [ ] Step 2: Read 文件全文
- [ ] Step 3: 搜索 API 定义
      - grep "API_.*=" <file>          # 查找常量定义
      - grep "def.*query\|function" <file>  # 查找函数签名
- [ ] Step 4: 提取真实端点/方法签名
      - 端点: https://...（来源: file.py:36）
      - 参数: {appId, current, size}（来源: file.py:89-91）
- [ ] Step 5: 使用真实端点构造请求
```

**案例对比**：
```python
# ❌ 幻觉版本（基于 REST 风格猜测）
endpoint = "https://ava-api.xfyun.cn/api/app/v2/info?appId=542c98ba"
# 来源：无（凭空编造）

# ✅ 验证版本（基于实际代码）
# 来源：xfyun_query_services.py:37
API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"
resp = session.post(API_APP_QUERY, json={"appId": app_id})
```

**违规检测**：
- 如果你写 API 调用前没有 Read 源文件 → **STOP**
- 如果你说"根据经验这个端点应该是..." → **STOP**

---

### B. 数据结构访问前（防止结构幻觉）

**触发场景**：解析 JSON 响应、访问对象属性、处理返回值

**强制步骤**：
```yaml
- [ ] Step 1: 找到处理该数据的示例代码
- [ ] Step 2: Read 示例代码（函数/脚本）
- [ ] Step 3: 定位数据访问路径
      - 例：data.get("data", {}).get("records", [])[0]
- [ ] Step 4: 复用相同的访问路径
```

**案例对比**：
```python
# ❌ 幻觉版本（假设扁平结构）
api_key = data.get('apiKey')  # 假设在顶层

# ✅ 验证版本（基于实际代码）
# 来源：xfyun_query_services.py:105-107
records = data.get("data", {}).get("records", [])
if records:
    api_key = records[0].get('apiKey')
```

**违规检测**：
- 如果你说"JSON 通常是扁平的" → **STOP**
- 如果你访问数据前没有查看示例代码 → **STOP**

---

### C. 文件编辑前（防止内容臆测）

**触发场景**：使用 Edit/Write 工具修改文件

**强制步骤**：
```yaml
- [ ] Step 1: Read 目标文件
- [ ] Step 2: 确认当前内容
- [ ] Step 3: 使用 exact match 进行 Edit
- [ ] Step 4: Edit 失败时，重新 Read 而非猜测
```

**案例对比**：
```python
# ❌ 幻觉版本（假设文件内容）
Edit(
    file_path="gradle-wrapper.properties",
    old_string="distributionUrl=https\\://services.gradle.org/...",  # 猜测
    new_string="..."
)

# ✅ 验证版本（基于实际内容）
Read("gradle-wrapper.properties")
# 发现实际是: distributionUrl=https\\://mirrors.cloud.tencent.com/...
Edit(
    file_path="gradle-wrapper.properties",
    old_string="distributionUrl=https\\://mirrors.cloud.tencent.com/...",
    new_string="..."
)
```

**违规检测**：
- 如果 Edit 失败提示 "String to replace not found" → **必须 Read 重新确认**
- 如果你说"这个文件通常包含..." → **STOP**

---

### D. 工具执行后（防止结果误判）

**触发场景**：执行 Bash/PowerShell 命令、调用构建工具

**强制步骤**：
```yaml
- [ ] Step 1: 检查 exit code（而非 stdout 文本）
      - exit code 0 = 成功
      - exit code 非 0 = 失败（即使有 "✅ 成功" 输出）
- [ ] Step 2: 验证副作用
      - 文件是否存在：ls/Test-Path
      - 进程是否运行：ps/Get-Process
      - 服务是否启动：端口监听检查
- [ ] Step 3: 读取错误输出（stderr）
```

**案例对比**：
```bash
# ❌ 幻觉版本（看输出文本判断）
$ gradle wrapper; echo "✅ Gradle Wrapper 已创建"
# 输出: ✅ Gradle Wrapper 已创建
# 结论: 成功 ❌（实际 gradle 命令不存在）

# ✅ 验证版本（检查 exit code + 副作用）
$ gradle wrapper
# exit code: 127 (command not found)
$ Test-Path "gradlew.bat"
# False
# 结论: 失败 ✓
```

**违规检测**：
- 如果你看到自己写的 `echo "成功"` 就认为成功 → **STOP**
- 如果工具返回 exit code 1 但你说"应该成功了" → **STOP**

---

### E. 外部资源引用前（防止链接编造）

**触发场景**：提供文档链接、控制台 URL、第三方服务地址

**强制步骤**：
```yaml
- [ ] Step 1: 检查是否有官方文档/脚本注释
- [ ] Step 2: 如果找到 → 使用找到的链接
- [ ] Step 3: 如果未找到 → 明确说"我不确定链接"
- [ ] Step 4: 禁止根据"常见模式"编造 URL
```

**案例对比**：
```markdown
# ❌ 幻觉版本（编造链接）
 请访问讯飞控制台订阅应用：
https://wrong.example/guessed-console
（来源：无，根据"常见控制台 URL 模式"猜测）

# ✅ 验证版本（承认不确定）
请访问讯飞开放平台控制台订阅应用。
具体链接请在讯飞官方文档中查找，我无法确定准确 URL。

# ✅✅ 最佳版本（找到官方文档）
Read tools/platform_endpoints.py
# 找到：PROJECTS_URL = "https://virtual-man.xfyun.cn/console/projects"
执行: python "<plugin-root>/tools/xfyun_common.py" projects
（来源：tools/platform_endpoints.py + tools/xfyun_common.py）
```

**违规检测**：
- 如果你说"根据讯飞的命名风格，链接应该是..." → **STOP**
- 如果你提供链接时没有注明来源 → **STOP**

---

## 派发子 Agent 时的特殊规则

### 问题：主 agent 读了 ≠ 子 agent 读了

**历史事故**：
- 主 agent 读取了 playbook
- 派发 `avatar-code-writer` 时只传了摘要："请生成 MainActivity，使用 writeText 发送文本"
- 子 agent 没有 playbook 上下文，按摘要生成了**不存在的 API**

**强制规则**：
```yaml
派发 avatar-code-writer / avatar-code-reviewer 时:
  - [ ] prompt 中必须包含完整路径
        - "先 Read <playbook-path>，按 §6 模板生成代码"
  - [ ] 不允许只传主 agent 的手搓摘要
  - [ ] 不允许说"我已经读过了，你直接写"
```

**正确示例**：
```markdown
# ✅ 正确的派发 prompt
请生成 Android MainActivity：
1. 先 Read C:\...\android-sdk-build-playbook.md 全文
2. 严格按 §1 真实 API 签名生成（IAvatarListener/writeText/setRenderArea）
3. 使用 §6.2 MainActivity 模板作为基础
4. 禁止使用 avatar-integration-guides/android.md 的简化 API

# ❌ 错误的派发 prompt
请生成 Android MainActivity，使用 sendText() 发送文本
（子 agent 会用不存在的 sendText API）
```

---

## 自我豁免检测

### 危险的心理模式

如果你发现自己在想：
- "这次情况特殊，可以跳过验证"
- "我反编译过 AAR，不用看 playbook 了"
- "时间紧，先写了再说"
- "这个 API 我很熟悉，肯定是..."
- "虽然 exit code 是 1，但看输出应该成功了"

→ **立即停止，重新走验证流程**

### 识别自我豁免的信号

```python
if any([
    "我确信这个 API 是...",
    "根据经验...",
    "通常情况下...",
    "应该是...",
    "可能是...",
    "看起来像是...",
]) and not has_explicit_source():
    raise HallucinationAlert("正在基于推理而非事实")
```

---

## 执行检查点（Checkpoint）

### 每次 API 调用前
```
□ 已 Read 源文件？
□ 已定位 API 定义？
□ 已提取真实签名？
□ 来源已注明？
```

### 每次数据访问前
```
□ 已查看示例代码？
□ 已复用相同访问路径？
□ 不是基于"经验"假设？
```

### 每次文件编辑前
```
□ 已 Read 目标文件？
□ 已确认当前内容？
□ 使用 exact match？
```

### 每次工具执行后
```
□ 已检查 exit code？
□ 已验证副作用？
□ 未仅依赖输出文本？
```

### 每次提供链接前
```
□ 已查找官方文档？
□ 已注明来源 或 承认不确定？
□ 未编造 URL？
```

### 派发子 agent 前
```
□ prompt 包含完整路径？
□ 要求子 agent 先 Read？
□ 未仅传摘要？
```

---

## 违规记录模板

当发现幻觉时，记录到 `hallucination-log.md`：

```markdown
## [日期] 幻觉事件

**类别**: API端点幻觉 / 数据结构幻觉 / 文件内容臆测 / 结果误判 / 链接编造

**触发场景**:
需要调用讯飞 API 获取应用详情

**错误行为**:
使用了臆造的端点 https://ava-api.xfyun.cn/api/app/v2/info

**根本原因**:
未 Read 脚本源码，基于"REST 风格"推理

**正确流程**:
1. Read xfyun_query_services.py
2. 定位 API_APP_QUERY = "https://virtual-man.xfyun.cn/zs_web/app/query"
3. 使用真实端点

**预防措施**:
在 API 调用前强制执行 A 类检查清单
```

---

## 集成到 Skill 工作流

### avatar-executing 中的集成点

**Phase 1: 读取实现计划后**
→ 执行 Checkpoint: 文件编辑前检查清单

**Phase 2: 确定执行模式时**
→ 执行 Checkpoint: API 调用前检查清单（读取 playbook）

**Phase 3: 派发子 agent 前**
→ 执行 Checkpoint: 派发前检查清单

**Phase 4: 验证构建结果时**
→ 执行 Checkpoint: 工具执行后检查清单

---

## 总结：一句话原则

**"Read first, verify always, admit uncertainty"**

- 没读过的不要用
- 用过的要验证
- 不确定的说不知道
