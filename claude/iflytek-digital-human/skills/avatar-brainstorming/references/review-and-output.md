# Phase 6 / Phase 7 / 输出

## Phase 6: 设计文档评审

**调用**: `spec-reviewer` 子代理

**评审维度**:
```yaml
completeness:
  - 工程信息是否完整
  - 技术选型是否明确
  - 参数配置是否齐全
  - 错误处理是否覆盖

consistency:
  - 协议选择与透明背景需求一致
  - 权限配置与功能需求一致
  - 平台能力与目标功能一致

clarity:
  - 术语使用准确
  - 流程描述清晰
  - 配置示例正确

feasibility:
  - 目标功能在当前平台可实现
  - 资源已授权
  - 环境已通过门禁
```

**评审输出**:
```yaml
status: pass | needs_revision
issues:
  - severity: critical | high | medium | low
    category: completeness | consistency | clarity | feasibility
    description: "xxx"
    suggestion: "xxx"
```

**处理**:
- 若 pass: 进入 Phase 7
- 若 needs_revision: 根据建议修改设计文档，重新评审

---

## Phase 7: 用户确认

**展示设计文档**:
```markdown
生成的设计文档已完成，请审阅:

## 核心内容摘要
- 平台: Web
- 目标功能: 文本驱动、语音交互、透明背景
- 协议: XRTC
- 预计实施步骤: 6 步

## 关键决策点
- 使用 XRTC 协议支持透明背景
- 需申请麦克风权限（语音功能）
- 建议在 HTTPS 环境下测试

完整设计文档已保存到: ./avatar-integration-spec.md
```

**用户确认**:
```
AskUserQuestion:
  question: "设计文档是否符合预期？"
  options:
    - label: "确认，开始实施"
      → 进入 avatar-planning
    - label: "需要调整"
      → 返回 Phase 4 重新访谈
    - label: "暂时不实施"
      → 保存设计文档，结束流程
```

---

## 输出

### 成功输出
```yaml
status: "completed"
design_spec_path: "./avatar-integration-spec.md"
next_step: "avatar-planning"
summary:
  platform: "web"
  intent: "first_integration"
  target_features:
    - text_driver
    - voice_interact
    - transparent_bg
  protocol: "xrtc"
  resources:
    avatarId: "xxx"
    vcn: "xxx"
```

### 异常输出
```yaml
status: "failed" | "cancelled"
reason: "用户取消" | "环境门禁未通过" | "需求不明确"
suggestions:
  - "修复环境门禁失败项后重试"
  - "明确需求后重新发起"
```
