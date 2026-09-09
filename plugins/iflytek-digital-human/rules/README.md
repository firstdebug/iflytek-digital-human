# Rules 规则体系

本包**没有 hook 自动装载机制**,所以没有"始终注入上下文"的规则。
规则通过 skill / agent 正文里的显式引用(`见 rules/...`)在需要时被读取。

## avatar-domain/sdk-conventions.md

虚拟人领域约束的**唯一权威源**。涵盖:初始化顺序、参数硬约束(bitrate/采样率等)、
事件监听完整性、NLP 数据解析、资源释放顺序、透明背景双配置、安全约束(凭据/网络/隐私)、
以及一批高频陷阱(playNotAllowed/HTTPS/ESM/10121/11203)。

涉及虚拟人 SDK / WebSocket / 播放器 / 录音的任务应参照它。当前显式引用它的 skill:
`avatar-troubleshoot`(可按需在 avatar-executing / avatar-code-writer 里补引用)。

## 历史说明

早期仿 AIUI 架构曾有 common/ 下多个规则文件(skill-authoring / investigate-before-answer /
security / coding-style / custom-tools),依赖"始终装载"机制生效。因本包无 hook,该机制不存在:
- `security` / `common-pitfalls` 内容已并入 `sdk-conventions.md`
- `custom-tools`(工具集成设计规范)、`skill-authoring`(编写规范)是开发文档,已移到 `docs/`
- `coding-style` / `investigate-before-answer` 与默认行为重合,已删除
