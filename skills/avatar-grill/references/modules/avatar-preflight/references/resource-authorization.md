# Layer 2：资源授权验证

本层只验证执行契约已经选择的 avatarId、vcn 和能力，不在执行阶段重新选择资源。

## 来源

- 候选资源和授权状态必须来自插件根目录平台工具的实际查询结果。
- 用户在 Grill 阶段从已验证候选中决定资源；契约记录选择、`source=platform-query` 和 `verified=true`。
- 不使用示例 ID、历史默认值或模型记忆补全 avatarId/vcn。

## 形象

检查契约选择的 avatarId：

- 属于当前 appId/sceneId 可用资源。
- 支持契约启用的透明背景、动作等能力。
- 平台查询失败或未授权时，契约进入 `blocked`，记录工具结果和恢复条件。

## 发音人

检查契约选择的 vcn：

- 属于当前 appId/sceneId 可用资源。
- 语言、采样率和契约目标匹配。
- 平台查询失败或未授权时保持 `blocked`，不得现场要求用户输入未知 ID。

## 完成条件

avatarId 和 vcn 均由本轮平台查询验证，并与 appId、sceneId 和启用能力匹配。任何资源变化都更新契约来源；改变用户选择时回到 Grill 并重新确认契约。
