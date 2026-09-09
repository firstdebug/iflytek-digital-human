# 门禁结果处理、缓存与输出格式

## 门禁结果处理

### 全部 PASS
```yaml
保存到 ~/.avatar-code/dev-env.yaml:
  platform: web | android | ios
  credentials:
    appId: "xxx"
    sceneId: "xxx"
  resources:
    avatarId: "xxx"
    vcn: "xxx"
  sdk:
    path: "..."
  environment:
    verified: true
  toolchain:
    verified_at: "2026-07-13T10:30:00Z"
  network:
    websocket: "ok"
    last_check: "2026-07-13T10:30:00Z"

返回 avatar-brainstorming，进入 Phase 3（意图分类）
```

### 部分 FAIL
```yaml
输出:
  - 失败的检查项
  - 失败原因
  - 修复建议
  - 相关文档链接

提示用户:
  1. 修复后重新执行 preflight
  2. 或选择"跳过此项"（风险提示）
  3. 或选择"稍后手动配置"（不推荐）

风险提示:
  - 跳过凭据验证 → 后续连接必定失败
  - 跳过 SDK 检查 → 编译/运行时错误
  - 跳过网络检查 → 运行时连接失败
```

---

## 缓存与复用

### 缓存策略
```yaml
# dev-env.yaml 缓存内容
credentials:
  appId: "xxx"
  sceneId: "xxx"
  # apiSecret 不缓存

resources:
  avatarId: "xxx"
  vcn: "xxx"

environment:
  last_verified: "2026-07-13T10:30:00Z"
  
toolchain:
  last_verified: "2026-07-13T10:30:00Z"

network:
  last_check: "2026-07-13T10:30:00Z"
```

### 复用规则
```
1. 凭据: 始终从环境变量/用户输入读取 apiSecret
2. SDK 路径: 缓存有效，跳过扫描
3. 工具链: 24小时内缓存有效
4. 网络: 1小时内缓存有效
```

### 强制重新检查
```bash
# 用户可强制重新检查
avatar-preflight --force-recheck

# 或删除缓存
rm ~/.avatar-code/dev-env.yaml
```

---

## 输出格式

### 成功输出
```json
{
  "status": "all_pass",
  "platform": "web",
  "checks": {
    "layer0_platform": "pass",
    "layer1_credentials": "pass",
    "layer2_resources": "pass",
    "layer3_sdk": "pass",
    "layer4_network": "pass",
    "layer5_toolchain": "pass",
    "layer6_validation": "pass"
  },
  "config": {
    "appId": "xxx",
    "sceneId": "xxx",
    "avatarId": "xxx",
    "vcn": "xxx",
    "sdkPath": "./sdk/avatar-sdk-web_3.2.3.1002/"
  },
  "cached": true,
  "verified_at": "2026-07-13T10:30:00Z"
}
```

### 失败输出
```json
{
  "status": "failed",
  "checks": {
    "layer1_credentials": "fail",
    "layer3_sdk": "fail"
  },
  "failures": [
    {
      "layer": "layer1",
      "step": "1.2",
      "name": "凭据有效性验证",
      "reason": "apiSecret 错误或签名生成有误",
      "errorCode": "10113",
      "fix": "请检查 apiSecret 是否正确复制",
      "docs": "https://doc.xfyun.cn/avatar/..."
    },
    {
      "layer": "layer3",
      "step": "3.1.1",
      "name": "SDK 文件检查",
      "reason": "未找到 index.js",
      "fix": "请下载 SDK 到项目目录",
      "downloadUrl": "https://..."
    }
  ]
}
```
