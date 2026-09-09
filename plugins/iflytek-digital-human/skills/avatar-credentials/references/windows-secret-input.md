# Windows 交互式密钥输入

## 适用场景

`xfyun_model_manage.py create/update` 通过 `getpass` 和 `input` 读取 API Key。需要由 Codex 自动提供输入时，使用 `cmd.exe` 的文件重定向，让 Python 获得真实 stdin 文件句柄。

不要使用以下形式：

```powershell
Get-Content response.txt | python tools\xfyun_model_manage.py create ...
```

PowerShell 对象管道可能让 `getpass` 与后续 `input` 的读取顺序错位。

## 稳定流程

1. 把 API Key 单独写入系统临时目录的短期文件。
2. 创建响应文件，依次包含：选择“从文件读取”、密钥文件路径、确认读取、确认删除。
3. 用 `cmd /c` 和 `< response-file` 执行 Python 命令。
4. 核对脱敏前后缀，并进行一次真实 API 调用。
5. 确认临时密钥文件已删除，再删除不含密钥的响应文件。

PowerShell 示例：

```powershell
$keyFile = Join-Path $env:TEMP 'xfyun-model-key.txt'
$responseFile = Join-Path $env:TEMP 'xfyun-model-response.txt'
Set-Content -LiteralPath $keyFile -Value $key -NoNewline -Encoding ascii
Set-Content -LiteralPath $responseFile -Value @('2', $keyFile, 'y', 'y') -Encoding ascii
cmd /c "python tools\xfyun_model_manage.py create <name> <model> <description> <apiUrl> < `"$responseFile`""
```

`update` 使用同一原则，但响应项要与脚本当前菜单一致。先查看菜单或代码，不把历史序号当成稳定接口。

## 安全检查

- 不在命令参数、终端输出或回复中展开 `$key`。
- 临时文件只放系统临时目录，并在脚本读取后立即删除。
- 脱敏输出只用于核对，不把脱敏值当成完整密钥保存。
- 自动输入后必须通过真实请求验证，不能只凭“保存成功”判断密钥正确。
