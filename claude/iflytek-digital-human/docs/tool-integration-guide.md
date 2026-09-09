# 自定义工具规范

> 用于定义用户提供的外部工具，供 skills 调用。

## 工具注册格式

```yaml
tools:
  - name: tool-name
    description: 工具功能描述
    type: script | api | binary
    path: 相对于 iflytek-digital-human 根目录的路径
    input:
      param1: type
      param2: type
    output:
      field1: type
      field2: type
    required: true | false
    security:
      sensitive_output: true  # 输出包含敏感信息
```

## 工具类型

### 1. script (脚本工具)

**约定**:
- 输入: 命令行参数或环境变量
- 输出: JSON 到 stdout（必须是有效 JSON）
- 错误: 非 0 退出码 + stderr

**示例**:
```yaml
- name: auto-login
  type: script
  path: tools/auto-login.js
  input:
    username: string
    password: string
  output:
    appId: string
    apiKey: string
    apiSecret: string
  security:
    sensitive_output: true
```

**调用**:
```bash
node tools/auto-login.js --username=xxx --password=xxx
# 或
USERNAME=xxx PASSWORD=xxx node tools/auto-login.js
```

### 2. api (HTTP API 工具)

**约定**:
- 本地服务（localhost）或内网 API
- RESTful 接口
- 返回 JSON

**示例**:
```yaml
- name: check-scene-status
  type: api
  endpoint: http://localhost:3000/scene/{sceneId}/status
  method: GET
  input:
    sceneId: string
  output:
    published: boolean
    remaining_minutes: number
```

**调用**:
```bash
curl http://localhost:3000/scene/123456/status
```

### 3. binary (二进制工具)

**约定**:
- 可执行文件（编译好的程序）
- 输入输出同 script

**示例**:
```yaml
- name: credential-manager
  type: binary
  path: tools/cred-manager
  platform: linux | darwin | win32
```

---

## 工具发现机制

Skill 执行时按此顺序查找工具:

1. 检查 `config/tools.yaml` 是否定义了该工具
2. 检查 `tools/工具名.*` 文件是否存在
3. 如果都不存在,fallback 到默认行为

---

## 安全约定

### 敏感输出处理

如果工具输出包含敏感信息（凭据、密钥等）:
```yaml
security:
  sensitive_output: true
```

我会:
- 不在对话框里回显完整输出
- 只显示"✅ 工具执行成功，已获取凭据"
- 直接写入目标文件（如 .env）

### 敏感输入处理

如果工具需要敏感输入（密码等）:
```yaml
security:
  sensitive_input: [password, apiSecret]
```

我会:
- 提示用户通过环境变量提供
- 不在命令行参数里暴露

---

## Skill 如何声明工具依赖

### 在 frontmatter 声明

```yaml
---
name: avatar-credentials
optional_tools:
  - name: auto-login
    when: 用户不想手动复制粘贴凭据
    fallback: 交互式引导流程
required_tools: []
---
```

### 在正文引用

```markdown
## 工具增强

如果用户提供了 `auto-login` 工具（见 `config/tools.yaml`）：

1. 检测工具: 查找 tools/auto-login.*
2. 询问用户: "检测到自动登录工具，是否使用？"
3. 调用工具: 传入必需参数
4. 解析输出: 验证 JSON schema
5. 写入结果: 直接到 .env，不经过对话框

否则，执行默认流程（交互式引导）。
```

---

## 工具模板

### JavaScript 脚本模板

```javascript
#!/usr/bin/env node
// tools/example-tool.js

const args = process.argv.slice(2);
const input = {
  param1: process.env.PARAM1 || args[0],
  param2: process.env.PARAM2 || args[1],
};

async function main() {
  try {
    // 执行工具逻辑
    const result = {
      field1: "value1",
      field2: "value2"
    };
    
    // 输出 JSON 到 stdout
    console.log(JSON.stringify(result));
    process.exit(0);
  } catch (error) {
    // 错误输出到 stderr
    console.error(JSON.stringify({ error: error.message }));
    process.exit(1);
  }
}

main();
```

### Python 脚本模板

```python
#!/usr/bin/env python3
# tools/example-tool.py

import sys
import json
import os

def main():
    try:
        # 读取输入
        param1 = os.getenv('PARAM1') or sys.argv[1]
        
        # 执行逻辑
        result = {
            "field1": "value1",
            "field2": "value2"
        }
        
        # 输出 JSON
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 调用示例

### 从 Skill 中调用

```bash
# 检查工具是否存在
if [ -f tools/auto-login.js ]; then
    echo "✅ 检测到自动登录工具"
    
    # 询问用户
    # (通过 AskUserQuestion 或直接执行)
    
    # 调用工具
    result=$(USERNAME="$user" PASSWORD="$pass" node tools/auto-login.js 2>&1)
    
    # 检查退出码
    if [ $? -eq 0 ]; then
        # 解析 JSON
        appId=$(echo "$result" | jq -r .appId)
        apiSecret=$(echo "$result" | jq -r .apiSecret)
        
        # 写入 .env（敏感信息不回显）
        cat > .env << EOF
VITE_AVATAR_APP_ID=$appId
VITE_AVATAR_API_SECRET=$apiSecret
EOF
        
        echo "✅ 凭据已自动获取并保存"
    else
        echo "❌ 工具执行失败: $result"
        # fallback 到默认流程
    fi
else
    echo "未检测到自动登录工具，使用交互式流程"
fi
```

---

## 工具测试

用户提供工具后，应先测试:

```bash
# 1. 语法检查
node --check tools/auto-login.js

# 2. 干跑测试（mock 输入）
USERNAME=test PASSWORD=test node tools/auto-login.js

# 3. 验证输出格式
node tools/auto-login.js | jq .

# 4. 验证错误处理
echo "invalid" | node tools/auto-login.js
echo "Exit code: $?"
```

---

## 相关文件

- `config/tools.yaml` - 工具注册表
- `tools/` - 用户提供的工具脚本
- `skills/*/SKILL.md` - 声明工具依赖
- `rules/common/security.md` - 敏感信息处理规范
