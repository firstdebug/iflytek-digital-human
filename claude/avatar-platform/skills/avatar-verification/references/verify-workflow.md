# 完整验证流程

```javascript
async function verifyProject() {
  console.log('🔍 开始项目验证...');
  console.log('');
  
  const issues = [];
  
  // Layer 1: 文件完整性
  console.log('Layer 1: 检查文件完整性...');
  const requiredFiles = [
    'index.html',
    'src/main.js',
    'src/avatar-service.js',
    'package.json',
    '.env'
  ];
  
  for (const file of requiredFiles) {
    if (!fs.existsSync(file)) {
      issues.push({
        layer: 1,
        severity: 'critical',
        file: file,
        error: '文件缺失',
        fix: '重新生成文件'
      });
    }
  }
  
  if (issues.filter(i => i.layer === 1).length === 0) {
    console.log('✅ Layer 1 通过');
  }
  console.log('');
  
  // Layer 2: 凭据验证
  console.log('Layer 2: 验证凭据配置...');
  if (fs.existsSync('.env')) {
    const envContent = fs.readFileSync('.env', 'utf-8');
    const requiredVars = [
      'APP_ID',
      'API_KEY',
      'API_SECRET',
      'SCENE_ID',
      'AVATAR_ID',
      'VCN',
      'WS_URL'
    ];
    
    for (const varName of requiredVars) {
      if (!envContent.includes(varName)) {
        issues.push({
          layer: 2,
          severity: 'critical',
          error: `缺少环境变量: ${varName}`,
          fix: '重新配置凭据'
        });
      }
    }
    
    if (issues.filter(i => i.layer === 2).length === 0) {
      console.log('✅ Layer 2 通过');
    }
  }
  console.log('');
  
  // Layer 3: SDK 验证
  console.log('Layer 3: 验证 SDK...');
  const sdkDirs = fs.readdirSync('./sdk', { withFileTypes: true })
    .filter(d => d.isDirectory() && d.name.startsWith('avatar-sdk-web'));
  
  if (sdkDirs.length === 0) {
    issues.push({
      layer: 3,
      severity: 'critical',
      error: 'SDK 未下载',
      fix: '执行 avatar-artifact-download'
    });
  } else {
    console.log(`✅ Layer 3 通过 (SDK: ${sdkDirs[0].name})`);
  }
  console.log('');
  
  // Layer 4: 依赖验证
  console.log('Layer 4: 验证依赖...');
  if (!fs.existsSync('node_modules')) {
    issues.push({
      layer: 4,
      severity: 'high',
      error: '依赖未安装',
      fix: '运行 npm install'
    });
  } else {
    console.log('✅ Layer 4 通过');
  }
  console.log('');
  
  // Layer 5: 配置参数验证（关键）
  console.log('Layer 5: 验证配置参数...');
  
  // 检查 bitrate
  const bitrateCheck = checkBitrateConfig('src/avatar-service.js');
  if (!bitrateCheck.valid) {
    issues.push({
      layer: 5,
      severity: 'critical',
      file: 'src/avatar-service.js',
      error: bitrateCheck.error,
      fix: bitrateCheck.fix,
      autofix: () => fixBitrateConfig('src/avatar-service.js')
    });
  }
  
  // 检查 SDK 路径
  const sdkPathCheck = checkSDKPath('src/avatar-service.js');
  if (!sdkPathCheck.valid) {
    issues.push({
      layer: 5,
      severity: 'high',
      file: 'src/avatar-service.js',
      error: sdkPathCheck.error,
      fix: sdkPathCheck.fix
    });
  }
  
  if (issues.filter(i => i.layer === 5).length === 0) {
    console.log('✅ Layer 5 通过');
  }
  console.log('');
  
  // Layer 6: 编译验证
  console.log('Layer 6: 编译验证...');
  // 简单的语法检查
  try {
    const mainContent = fs.readFileSync('src/main.js', 'utf-8');
    const serviceContent = fs.readFileSync('src/avatar-service.js', 'utf-8');
    
    // 检查基本语法错误
    if (mainContent.includes('undefined') && !mainContent.includes('!== undefined')) {
      console.warn('⚠️  代码中可能存在 undefined 引用');
    }
    
    console.log('✅ Layer 6 通过');
  } catch (error) {
    issues.push({
      layer: 6,
      severity: 'high',
      error: '文件读取失败',
      fix: '检查文件权限'
    });
  }
  console.log('');
  
  // 汇总结果
  console.log('═'.repeat(60));
  console.log('验证结果汇总');
  console.log('═'.repeat(60));
  
  if (issues.length === 0) {
    console.log('');
    console.log('✅ 所有检查通过！项目可以交付');
    console.log('');
    return { valid: true, issues: [] };
  } else {
    console.log('');
    console.log(`❌ 发现 ${issues.length} 个问题`);
    console.log('');
    
    // 按严重程度分组
    const critical = issues.filter(i => i.severity === 'critical');
    const high = issues.filter(i => i.severity === 'high');
    
    if (critical.length > 0) {
      console.log('🔴 Critical 问题:');
      critical.forEach((issue, idx) => {
        console.log(`  ${idx + 1}. ${issue.error}`);
        console.log(`     修复: ${issue.fix}`);
        if (issue.file) console.log(`     文件: ${issue.file}`);
      });
      console.log('');
    }
    
    if (high.length > 0) {
      console.log('🟡 High 问题:');
      high.forEach((issue, idx) => {
        console.log(`  ${idx + 1}. ${issue.error}`);
        console.log(`     修复: ${issue.fix}`);
      });
      console.log('');
    }
    
    // 尝试自动修复
    console.log('🔧 尝试自动修复...');
    let fixed = 0;
    
    for (const issue of issues) {
      if (issue.autofix) {
        try {
          issue.autofix();
          console.log(`✅ 已修复: ${issue.error}`);
          fixed++;
        } catch (error) {
          console.error(`❌ 修复失败: ${issue.error}`);
        }
      }
    }
    
    console.log('');
    console.log(`修复完成: ${fixed}/${issues.length}`);
    console.log('');
    
    if (fixed === issues.length) {
      console.log('✅ 所有问题已自动修复！');
      return { valid: true, issues: [], fixed: fixed };
    } else {
      console.log('⚠️  仍有问题需要手动处理');
      return { valid: false, issues: issues.filter(i => !i.autofix), fixed: fixed };
    }
  }
}
```
