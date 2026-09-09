# 集成到工作流

## avatar-executing 完成后调用

```yaml
# avatar-executing 流程

Step 8: 代码实现
  → 生成所有代码文件

Step 9: ⭐ 验证和自检（新增）
  → 调用 avatar-verification
  → 自动检测问题
  → 自动修复问题
  → 确认所有检查通过

Step 10: 交付
  → 只有验证通过才交付给用户
  → 用户拿到的是开箱即用的项目
```

## 验证报告格式

```
╔══════════════════════════════════════════════════════════════╗
║     项目验证报告                                              ║
╚══════════════════════════════════════════════════════════════╝

Layer 1: 文件完整性     ✅ 通过
Layer 2: 凭据验证       ✅ 通过
Layer 3: SDK 验证       ✅ 通过
Layer 4: 依赖验证       ✅ 通过
Layer 5: 配置参数验证   ✅ 通过（自动修复 1 个问题）
Layer 6: 编译验证       ✅ 通过
Layer 7: 运行时验证     ✅ 通过

════════════════════════════════════════════════════════════════

✅ 验证通过！项目可以安全交付

自动修复的问题:
  1. bitrate 参数: 0 → 2000

════════════════════════════════════════════════════════════════
```

---

# 输出

## 验证通过
```yaml
status: "passed"
issues_found: 3
issues_fixed: 3
ready_to_deliver: true
```

## 验证失败
```yaml
status: "failed"
issues_found: 5
issues_fixed: 3
remaining_issues:
  - error: "SDK 未下载"
    fix: "执行 avatar-artifact-download"
ready_to_deliver: false
```
