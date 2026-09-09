# 计划评审、用户确认与输出

对应 Step 3（plan-reviewer 评审）、Step 4（用户确认）及最终输出结构。

## Step 3: plan-reviewer 评审

**评审重点**:
```yaml
executable:
  - 每个步骤是否可执行
  - 是否有明确的验证方法
  - 操作是否有代码示例

dependencies:
  - 步骤依赖顺序是否正确
  - 前置条件是否明确

completeness:
  - 是否遗漏关键步骤
  - 错误处理是否覆盖
  - 资源释放是否完整

risks:
  - 是否识别高风险点
  - 是否提供缓解措施
  - 是否有回滚策略
```

**评审输出**:
```yaml
status: pass | needs_revision
issues:
  - step: "Step 3"
    severity: high
    problem: "缺少初始化失败的错误处理"
    suggestion: "添加 try-catch 和错误码判断"
```

**策略**: 最多 2 轮评审，只找阻塞性问题

## Step 4: 用户确认

**展示计划摘要**:
```markdown
实现计划已生成，包含 8 个步骤:

1. SDK 安装与引入
2. 环境配置（权限、依赖）
3. SDK 初始化
4. 播放器创建与配置
5. 全局参数配置
6. 启动虚拟人
7. 实现核心功能
8. 错误处理与资源释放

预计实施时间: 2-4 小时
风险点: 3 个高风险，2 个中风险

完整计划已保存到: ./avatar-implementation-plan.md
```

**用户确认**:
```
AskUserQuestion:
  question: "实现计划是否可以开始执行？"
  options:
    - label: "确认，开始实施"
      → 进入 avatar-executing
    - label: "需要调整"
      → 修改计划后重新评审
    - label: "查看完整计划"
      → 展示完整计划内容
```

## 输出

### 成功输出
```yaml
status: "completed"
plan_path: "./avatar-implementation-plan.md"
next_step: "avatar-executing"
summary:
  total_steps: 8
  estimated_time: "2-4 hours"
  high_risks: 3
  medium_risks: 2
```

### 异常输出
```yaml
status: "failed" | "cancelled"
reason: "设计文档缺失" | "用户取消" | "评审未通过"
```
