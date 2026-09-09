# 路由规则表（完整）

本文件是**路由规则的唯一权威来源**。`SKILL.md` 的决策分支表只是快速索引，出现分歧时以本文件为准。

## 意图优先级

同时命中多个信号时按此顺序处理：

1. 明确故障、错误码或异常行为
2. 权限或纯网络问题
3. 已有项目的配置修改
4. 用户明确指定的交付形态或平台能力
5. 首次接入和宽泛构建需求
6. 纯概念或文档查询

## 关键词 / 指标映射

完整的关键词 / 指标 / 路由目标映射规则。

```yaml
故障排查:
  keywords:
    - "失败" / "报错" / "不工作" / "黑屏"
    - "错误码" / "error" / "异常"
    - "为什么..." / "怎么回事"
  indicators:
    - 提供了错误码
    - 提供了日志片段
    - 描述了异常行为
  route_to: avatar-troubleshoot
  priority: highest

配置调整:
  keywords:
    - "调整" / "修改" / "更换" / "优化"
    - "分辨率" / "码率" / "帧率"
    - "形象" / "声音" / "参数"
  indicators:
    - SDK 已集成
    - 基础功能已工作
    - 只涉及参数修改
  route_to: avatar-config-authoring
  priority: high

首次接入:
  keywords:
    - "集成" / "接入" / "从零" / "新项目"
    - "如何开始" / "怎么用"
  indicators:
    - SDK 未集成
    - 工程中无虚拟人相关代码
  route_to: avatar-brainstorming
  priority: medium

功能扩展（非语音）:
  keywords:
    - "添加" / "新增" / "扩展"
    - "动作控制" / "透明背景" / "字幕" / "文本交互"
  indicators:
    - SDK 已集成
    - 部分功能已实现
    - 只增加单一非语音能力
  route_to: 对应能力 skill（单一能力，默认 quick）；多能力或架构调整走 avatar-brainstorming
  priority: medium

语音能力扩展:
  keywords:
    - "语音交互" / "语音识别" / "语音问答" / "录音"
    - "麦克风" / "ASR" / "说话"
  indicators:
    - 要新增 ASR/录音/麦克风权限或语音 UI
  route_to: 先执行语音确认门禁（平台交互提问 确认能力 + 交互形态），确认后 avatar-voice-interact / avatar-permissions-setup
  priority: medium
  gate: HARD-GATE  # 未确认前不得修改 Manifest/Info.plist、不得加 RECORD_AUDIO、不得写录音代码或语音 UI

文档查询:
  keywords:
    - "如何..." / "怎么..." / "能不能"
    - "文档" / "教程" / "示例"
  indicators:
    - 无明确实施意图
    - 仅需信息不需实现
  route_to: provide_docs
  priority: low

权限问题:
  keywords:
    - "权限" / "拒绝" / "无法录音"
    - "麦克风" / "摄像头"
  indicators:
    - 权限相关错误
  route_to: avatar-permissions-setup
  priority: high

网络问题:
  keywords:
    - "连接" / "超时" / "断开"
    - "10200" / "10201" / "网络"
  indicators:
    - 网络相关错误码
  route_to: avatar-network-debug
  priority: high

鉴权失败:
  keywords:
    - "avatar authentication failed" / "authorization invalid"
    - "1008" / "10110" / "10113" / "10114" / "10120" / "10121"
  indicators:
    - WebSocket 鉴权握手被拒绝或 SDK 初始化后立即断开
  route_to: avatar-troubleshoot
  required_reference: references/authentication-failed.md
  rule: 通用错误文案不直接映射根因，先查询 app/scene/发布/资产关系并保留平台错误说明
  priority: highest

知识库管理:
  keywords:
    - "知识库" / "docqa" / "RAG"
    - "上传文档" / "知识问答" / "文档检索"
    - "向量化" / "检索增强"
  indicators:
    - 明确提到操作知识库（创建/上传/关联）
    - 已有知识库需配置到场景
  route_to: avatar-knowledge-base
  priority: high
```

## 边界规则

- "调高分辨率"是明确的配置修改，直接处理，不需要再问是否要修改。
- "黑屏后想换形象"先排查黑屏，再修改形象。
- "做一个虚拟客服"缺少交付形态，只询问官方模板、数字人直播、SDK 自建三选一。
- "用 Android SDK 做虚拟客服"已经明确 SDK 自建，直接进入 `avatar-brainstorming`，并按
  `../../avatar-shared/delivery-modes.md` 确认 `workflow_mode`。
- **"给现有项目加语音交互"即使工程和目标明确，也必须先确认是否加入语音能力和交互形态**
  （按住说话 / 点击开始停止 / 自动 VAD / 全双工），确认后才用 `avatar-voice-interact`。
  涉及多项能力或架构调整时还要进入 `avatar-brainstorming` 并选择 `quick` 或 `strict`。
- **用户只要求文本对话时不得自行添加语音功能**；未确认的能力写入 `excluded`。
- `avatar-integration-guides` 仅解释 SDK 结构，不作为 Android 或 Web 生产代码来源；真正构建工程必须读
  `avatar-executing/references/` 下的真实 Playbook。
- 工程扫描结果与用户描述冲突时，说明证据并以实际工程状态规划后续操作。

## 门禁提醒

首次 SDK 自建、从零构建或多能力扩展必须先确认 `workflow_mode: quick | strict`，用户未选择前停止实施。
新增语音能力必须单独确认。两个门禁的完整规则见 `../../avatar-shared/delivery-modes.md`。
