> 本文件是 avatar-grill 的领域资料，不是独立 Skill。
> 执行边界以已确认的 `.avatar/avatar-run-contract.json` 为准。
> 直接由主 Agent 执行，不要求流程模式、计划文档或任务派发。
> 语音和麦克风能力必须读取契约确认项，未确认不得加入。


# shared: 共享材料容器

## 定位

本资料收纳多个能力共用的工程事实，按当前执行契约需要读取，不定义入口或调度流程。

## 内容索引

| 材料 | 路径 | 用途 |
|------|------|------|
| 测试驱动开发 | `test-driven-development/source-skill.md` | 通用 TDD 工作方法（先写测试再实现） |
| Android 分区存储适配 | `android-scoped-storage.md` | Android 11+ (API 30) 分区存储下的日志路径配置 |
| Android Gradle 稳定构建 | `android-gradle-stability.md` | Wrapper 镜像、Maven 顺序、内存/并发、缓存锁与超时处理 |

## 使用建议

- 涉及测试策略 → 参考 `test-driven-development`
- Android 工程遇到 `/sdcard/` 写入受限 → 参考 `android-scoped-storage.md`
- Android 构建慢、卡住、缓存锁或 daemon 异常 → 参考 `android-gradle-stability.md`（构建、预检、排障、验收共用）
