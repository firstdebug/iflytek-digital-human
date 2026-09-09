# Phase 3: 意图分类

**目的**: 明确任务类型，决定后续流程

## 3.1 意图识别规则

**规则表**:
```yaml
首次接入（新建项目）:
  conditions:
    - 用户需求包含"构建"/"创建"/"搭建"/"从零"/"新建"等关键词
    - 或明确提供了不存在的项目路径
    - 或当前目录为空/非项目目录
  next_phase: "跳过扫描 → 询问平台和工作目录 → 详细访谈（全功能）"

首次接入（现有项目集成）:
  conditions:
    - sdk_status = not_integrated
    - 用户需求包含"集成"/"接入"等关键词
    - 且当前目录是现有项目
  next_phase: "扫描现有项目 → 详细访谈（全功能）"

功能扩展:
  conditions:
    - sdk_status = partially_integrated | fully_integrated
    - 用户需求明确提到具体功能（如"添加语音交互"）
  next_phase: "增量访谈（目标功能）"

故障排查:
  conditions:
    - 用户需求包含"失败"/"报错"/"不工作"等关键词
    - 提供了错误码或日志
  next_phase: "路由到 avatar-troubleshoot"

配置调整:
  conditions:
    - sdk_status = fully_integrated
    - 用户需求为参数调整（如"调整分辨率"/"更换形象"）
  next_phase: "路由到 avatar-config-authoring"

文档查询:
  conditions:
    - 用户需求为"如何..."/"怎么..."等疑问
    - 无明确实施意图
  next_phase: "提供文档链接和简要说明"
```

## 3.2 意图分类示例

**示例 1: 首次接入**
```
用户: "我想在 Vue 项目中集成虚拟人播报功能"

识别结果:
  intent: first_integration
  target_platform: web
  target_features: [text_driver]
  
下一步: 详细访谈
```

**示例 2: 功能扩展**
```
用户: "已有文本播报，想添加语音交互"

识别结果:
  intent: feature_extension
  existing_features: [text_driver]
  target_features: [voice_interact]
  
下一步: 增量访谈
```

**示例 3: 故障排查**
```
用户: "Android 虚拟人黑屏，错误码 20002"

识别结果:
  intent: troubleshooting
  platform: android
  error_code: "20002"
  
下一步: 路由到 avatar-troubleshoot
```
