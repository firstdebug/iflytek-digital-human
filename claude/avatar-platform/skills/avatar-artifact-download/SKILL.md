---
name: avatar-artifact-download
description: 下载并校验讯飞虚拟人 Web、Android 或 iOS SDK 产物，验证压缩包、关键入口与本地清单。用于首次接入缺少 SDK、需要核对 SDK 包或禁止无 SDK 假交付时。
---

# avatar-artifact-download: SDK 下载

## 目标

把目标平台的 SDK 放到项目约定目录并验证关键文件。已有完整 SDK 时直接复用；下载失败时返回明确阻塞，不猜测替代链接，也不把缺少 SDK 的项目描述成可运行。

## 输入与输出

输入：

- `platform`：`web`、`android` 或 `ios`
- `project_path`：目标项目根目录
- 可选 `target_dir`：用户指定的落盘目录

输出状态：

| 状态 | 含义 |
|---|---|
| `already_exists` | 关键文件已存在，未重复下载 |
| `success` | 下载、解压和校验均通过 |
| `blocked_missing_sdk` | 自动下载或校验失败，SDK 仍缺失，workflow 不得完成 |
| `failed` | 文件损坏、平台不支持或目标目录不可写 |

## 工作流

1. 根据平台确定默认目录和验证规则。
2. 递归检查关键文件；完整则返回 `already_exists`。
3. Web 直接执行：`python "<plugin-root>/tools/sdk_artifact.py" ensure --platform web --project "<project>"`。
4. 工具从内置当前配置下载到系统临时目录，验证 ZIP 并阻止路径穿越，再解压到目标目录。
5. 按平台验证关键文件；Web 还要验证 `index.d.ts` 并生成 `.runtime/sdk-artifact.json` 的入口哈希。
6. 检查命令退出码和 JSON 状态；不得只看 HTTP 200、控制台文字或目录非空。
7. 非零退出时保留 `blocked_missing_sdk`，修复网络/源地址/权限后重跑同一命令。

## 平台规则

| 平台 | 默认目录 | 必须存在 |
|---|---|---|
| Web | `<project>/sdk/` | `**/index.js` |
| Android | `<project>/app/libs/` | `avatar-core-*.aar` 和 `xrtcsdk-*.aar` |
| iOS | `<project>/Frameworks/` | `AvatarSDK.framework` |

不要仅凭压缩包存在、HTTP 200 或目录非空判定成功。

## 执行策略

- Windows 优先使用 PowerShell；macOS/Linux 优先使用 `curl` 或 `wget`。
- 创建目标目录和下载 SDK 属于快速接入的常规操作，可直接执行。
- 不覆盖用户已有的同名 SDK 文件；版本不确定时先报告现状，再选择新目录或由用户明确覆盖。
- 下载完成后以 `sdk-artifact.json` 记录相对入口、类型文件、版本和 SHA-256，供 `avatar-preflight` 与 `avatar-executing` 使用。
- 需要现成 Bash/PowerShell 实现时读取 `references/download-scripts.md`，并按目标项目调整路径。

## 失败处理

网络失败时报告具体错误类型，例如 DNS、TLS、代理、超时或 HTTP 状态。若配置中没有经过验证的替代源，不提供手动下载 URL；保持 `blocked_missing_sdk`，修复下载条件后重跑。用户自行提供 SDK 包时也必须重新执行本工具校验，不能凭文件名放行。

## HARD-GATE

- Android 必须同时有 core 与 XRTC 两个 AAR。
- 不把 WebSocket 手写实现当作 SDK 缺失的替代方案。
- 不把未经校验的压缩包或解压目录交给后续构建。
- 不写死用户目录、用户名或安装缓存路径。
- 不声称 OSS 永久有效；以实际请求和校验结果为准。
- SDK 缺失时不得创建完成标记、调用 Reporter complete，或输出“下载后即可运行”的交付总结。

## References

- `references/config-templates.md`：当前版本、下载地址、目标目录和验证规则
- `references/download-scripts.md`：按需使用的 Bash 与 PowerShell 完整脚本
- `references/integration.md`：与 preflight 的衔接和结果结构示例

## 验证清单

- [ ] 目标平台与目录已确定
- [ ] 下载前已检查现有 SDK
- [ ] 命令退出码为 0，下载、ZIP 安全检查和解压均成功
- [ ] 平台关键文件全部存在
- [ ] `.runtime/sdk-artifact.json` 的入口路径和哈希与磁盘一致
- [ ] 临时文件已清理
- [ ] 返回状态、实际路径和版本清晰

## 相关 Skill

- `avatar-preflight`：检测 SDK 是否就绪
- `avatar-executing`：使用已验证 SDK 构建工程
- `avatar-credentials`：准备 SDK 初始化所需凭据
