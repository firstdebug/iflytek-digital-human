# Step 6: 验证修复

## 6.1 验证清单

**基础验证**:
```yaml
编译验证:
  - [ ] 编译通过，无错误

运行验证:
  - [ ] 应用正常启动
  - [ ] 无崩溃

功能验证:
  - [ ] SDK 初始化成功
  - [ ] 虚拟人连接成功
  - [ ] 视频正常播放
  - [ ] 原问题不再复现
```

**回归验证**:
```yaml
已有功能:
  - [ ] 文本驱动仍正常
  - [ ] 事件监听仍正常
  - [ ] 资源释放仍正常

边界场景:
  - [ ] 网络断开后重连
  - [ ] 权限拒绝后恢复
```

## 6.2 验证方法

```javascript
async function verifyFix(issue, fix) {
  console.log(`验证修复: ${issue.symptom}`);
  
  // 1. 编译验证
  const compileResult = await runCommand('build');
  if (!compileResult.success) {
    return { status: 'compile_failed', error: compileResult.error };
  }
  
  // 2. 运行验证
  const runResult = await runCommand('run');
  if (!runResult.success) {
    return { status: 'runtime_error', error: runResult.error };
  }
  
  // 3. 功能验证（需要用户手动确认）
  const functionalOk = await askUser(
    "问题是否已解决？虚拟人是否正常显示？"
  );
  
  if (!functionalOk) {
    return {
      status: 'fix_ineffective',
      suggestion: '修复未生效，需要进一步诊断'
    };
  }
  
  // 4. 回归验证
  const regressionOk = await askUser(
    "其他已有功能是否仍正常？"
  );
  
  if (!regressionOk) {
    return {
      status: 'regression_detected',
      suggestion: '修复引入了新问题，需要调整方案'
    };
  }
  
  return { status: 'verified', message: '修复成功并验证通过' };
}
```
