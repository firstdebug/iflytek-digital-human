# SKILL.md 编写规范

> 始终装载(适用于所有 skill 创建/修改场景)。

## 核心原则

SKILL.md 是**导航文档**,不是**实施手册**。

| 应该写 | 不该写 |
|-------|-------|
| 触发条件、工作流概览 | 完整可运行代码(>15 行) |
| 决策分支、判定规则 | 多平台代码模板 |
| 关键约束、Red Flags、HARD-GATE | 详细 API 调用序列(>5 步) |
| 指向 references/ 的索引 | 反例代码块 |
| 短代码片段(≤10 行示意) | 完整工程示例 |

## 硬约束

1. **单文件 ≤ 250 行**(推荐 ≤ 150 行)
2. **单代码块 ≤ 15 行** —— 超过必须拆到 `references/<topic>.md`
3. **多平台/多场景代码模板必须放 references/** —— SKILL.md 只列平台→reference 映射表
4. **决策分支保留在 SKILL.md** —— 这是查找索引,不能拆
5. **HARD-GATE / Red Flags 文字保留在 SKILL.md** —— LLM 第一时间需要看到的约束

## 推荐结构

```
SKILL.md(≤150 行)
├── frontmatter (name, description)
├── 触发条件
├── 知识源(references/ 索引)
├── 核心工作流(文字描述 + 简表)
├── 决策分支(场景 → 应读哪个 reference)
├── 关键约束 / HARD-GATE
└── 验证清单 / 交接协议

references/<topic>.md(按需加载)
├── 详细代码模板
├── 各平台实现
├── 完整调用序列
└── 反例与陷阱说明
```

## 自检清单

- [ ] 文件行数 ≤ 250 行(超过必须拆)
- [ ] 没有单个代码块 > 15 行
- [ ] 多平台代码模板已移到 references/,SKILL.md 只留索引表
- [ ] 触发条件、决策分支、HARD-GATE 都还在 SKILL.md
- [ ] 所有 `references/<file>.md` 引用真实存在(无死链)

## 例外

只有以下情况允许 > 250 行:
- 全部是文字(无代码块)的决策树/排障指南
- 全部是流程文字(无代码块)的工作流定义

## Skill 间依赖单向

- 编排型 skill(preflight / brainstorming / planning / executing)可引用专家 skill
- 专家 skill **不得反向引用**编排型 skill
- Skill 之间通过**输入/输出契约**通信
- 跨 skill 引用用仓库根相对路径:`skills/<name>/...`
