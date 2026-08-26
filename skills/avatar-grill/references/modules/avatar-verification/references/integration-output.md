# 验证结果输出

本资料只定义当前执行契约的验证结果，不调用另一个 Skill，也不创建新的入口。

## 输出结构

验证必须读取已确认契约中启用的能力，并把命令退出码、构建产物、运行事件和平台查询结果写入本轮证据。

```yaml
status: passed | blocked | failed
issues_found: 0
issues_fixed: 0
ready_to_deliver: true | false
evidence:
  - source: command | artifact | runtime-event | platform-query
    verified: true
```

只有全部验收项和平台门禁通过时才允许 `ready_to_deliver: true`；缺少证据、存在未解决 Critical 问题或契约授权不足时保持 `blocked`，记录恢复条件并回到 Grill 重新确认契约。
