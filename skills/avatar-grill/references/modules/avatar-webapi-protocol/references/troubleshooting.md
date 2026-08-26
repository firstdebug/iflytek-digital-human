# 常见错误码实战排查指南

本文档基于实际构建 WebAPI demo 过程中遇到的问题，提供快速定位和解决方案。

## 高频错误码速查表

| 错误码 | 错误信息 | 根因 | 快速定位 | 解决方案 |
|--------|----------|------|----------|----------|
| 10163 | `'$.parameter.tts.vcn' length must be larger or equal than 1` | vcn 参数为空字符串 | 检查 .env 里 `XF_VCN=` 是否为空 | 设置有效发音人，如 `XF_VCN=x4_lingxiaoqi_oral` |
| 20016 | `vcn is invalid` 或 `avatarId is invalid` | 发音人或形象未授权给该场景 | 从已验证项目复用配置 | 见下文"20016 未授权问题" |
| 10113 | 签名错误 | apiSecret 错误或签名逻辑错误 | 检查 apiSecret 长度和内容 | 重新从平台获取完整密钥 |
| 10121 | 接口服务未发布 | sceneId 对应的接口服务未点击"发布" | 登录平台检查发布状态 | 在控制台点击"发布" |
| 10108 | session is invalid | start 不是第一个发送的协议 | 检查代码流程 | 确保连接后第一个发送 start |

---

## 实战案例 1：10163 vcn 为空

### 现象
```json
{
  "header": {
    "code": 10163,
    "message": "'$.parameter.tts.vcn' length must be larger or equal than 1"
  }
}
```

### 排查步骤

**Step 1**：检查 .env 文件
```bash
cat ~/.env | grep VCN
# 如果输出：XF_VCN=
# 说明 vcn 为空
```

**Step 2**：检查代码默认值
```python
VCN = os.environ.get("XF_VCN", "")  # ❌ 空字符串会覆盖默认值
VCN = os.environ.get("XF_VCN", "x4_lingxiaoqi_oral")  # ✓ 设置兜底默认值
```

**Step 3**：修复
```bash
# 方式 A：更新 .env
echo "XF_VCN=x4_lingxiaoqi_oral" >> ~/.env

# 方式 B：用脚本更新
python -c "
from pathlib import Path
env = Path.home() / '.env'
lines = env.read_text().splitlines()
new_lines = [line if not line.startswith('XF_VCN=') 
             else 'XF_VCN=x4_lingxiaoqi_oral' for line in lines]
env.write_text('\n'.join(new_lines) + '\n')
"
```

**关键教训**：
- `.env` 里的空值会覆盖代码默认值
- 设置默认值时用有意义的值，不要用空字符串

---

## 实战案例 2：20016 vcn/avatarId 未授权

### 现象
```json
{
  "header": {
    "code": 20016,
    "message": "vcn is invalid"
  }
}
```

### 根因
使用的 `avatar_id` 或 `vcn` 不在该场景的授权列表内。

### 解决方案

**推荐**：使用工具自动生成的默认配置
```bash
cd <plugin-root>
python tools/write_env_safe.py <app_id> <scene_id> ~/.env
# 工具会自动设置通用默认值：
# XF_AVATAR_ID=111310001
# XF_VCN=x4_lingxiaoqi_oral
```

这些默认值适用于大多数场景。如果特定场景未授权，错误信息会明确提示，再联系平台管理员添加授权。

**关键教训**：
- 优先使用工具自动设置的默认配置
- 20016 错误通常意味着场景授权不足，需要平台管理员操作
- 不要手动猜测 avatar_id/vcn 的值

---

## 实战案例 3：凭据获取

### 标准流程

```
需要 WebAPI 凭据？
├─ Step 1: 登录平台
│         cd <plugin-root>
│         python tools/xfyun_common.py login
│
├─ Step 2: 查询场景列表
│         python tools/xfyun_query_services.py
│
└─ Step 3: 写入完整凭据（含默认形象/发音人）
          python tools/write_env_safe.py <app_id> <scene_id> ~/.env
```

**关键教训**：
- 脱敏存储的密钥（`xxxx****xxxx`）不能用于 HMAC 签名，必须通过平台 API 获取完整值
- 工具会自动设置默认形象（111310001）和发音人（x4_lingxiaoqi_oral）
- 每次都用默认配置即可，无需扫盘查找其他项目

---

## 实战案例 4：工具调用路径错误

### 现象
```bash
python tools/xfyun_query_services.py
# ModuleNotFoundError: No module named 'xfyun_common'
```

### 根因
未在插件根目录执行，相对导入失效

### 解决
```bash
# ✓ 正确：先 cd 到插件根目录
cd <plugin-root>
python tools/xfyun_query_services.py

# ❌ 错误：在其他目录直接调用
cd ~/some-project
python <plugin-root>/tools/xfyun_query_services.py  # 直接按脚本路径运行可能导致相对导入失败
```

**关键教训**：
- 所有 `tools/*.py` 脚本必须在插件根目录执行
- 执行前务必 `cd <plugin-root>`

---

## 实战案例 5：Windows 编码崩溃

### 现象
```
UnicodeEncodeError: 'gbk' codec can't encode character '❌' in position 0
```

### 根因
Windows 控制台默认 GBK，不支持 emoji（✓ ❌ 🔐）

### 解决
在 Python 脚本开头添加：
```python
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
```

**关键教训**：
- 跨平台脚本要处理 Windows 编码差异
- 必须在最开头设置，在任何 print 之前

---

## 快速诊断命令

### 检查凭据完整性
```bash
# 检查 .env 是否存在且包含所有必需字段
cat ~/.env | grep -E "XF_(APP_ID|API_KEY|API_SECRET|SCENE_ID|AVATAR_ID|VCN)="

# 检查是否有空值
cat ~/.env | grep -E "XF_.*=$"
```

### 检查登录状态
```bash
cd <plugin-root>
python tools/xfyun_common.py cookie-path
```

### 验证 API 调用
```bash
cd <plugin-root>
python tools/xfyun_query_services.py 2>&1 | head -20
# 如果看到 "查询成功" → 登录有效
# 如果看到 "需要登录" → 运行 python tools/xfyun_common.py login
```

---

## 错误码完整参考

常见错误码：
- **10xxx**：会话/协议类错误
- **11xxx**：授权/配额类错误
- **20xxx**：参数/资源类错误

