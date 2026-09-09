# 输出格式

## 成功诊断
```yaml
status: "diagnosed"
root_cause:
  category: "dependency_missing"
  description: "XRTC SDK 未引入"
  error_code: "20002"
fix:
  steps: 5
  estimated_time: "10分钟"
  difficulty: "medium"
verification:
  required: true
  methods: ["compile", "run", "functional"]
```

## 需要更多信息
```yaml
status: "needs_more_info"
missing:
  - "错误日志"
  - "是否收到 stream_start 事件"
questions:
  - "请提供完整的控制台日志"
  - "请确认是否收到 stream_start 事件"
```

## 无法诊断
```yaml
status: "unable_to_diagnose"
reason: "症状描述不明确且无错误日志"
suggestions:
  - "提供完整的错误日志"
  - "描述详细的复现步骤"
  - "说明最近的代码变更"
```
