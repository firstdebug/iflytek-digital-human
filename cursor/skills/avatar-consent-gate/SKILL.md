---
name: avatar-consent-gate
description: >-
  在任何讯飞虚拟人工作流进入路由、扫描或实施前建立并验证本地隐私授权准入凭证。
  仅用于明确调用 iflytek-digital-human 的 avatar skill；普通后端、NLP、OpenAI SSE 或 Higress 调试不适用。
---

# avatar-consent-gate: 隐私授权准入

这是独立的 HARD-GATE。调用本 skill 后，先处理授权，再允许任何路由、工程扫描、模式询问或下游 skill。

## 工具解析

工具根目录是本技能包根目录下的 `tools/`；从当前 skill 目录解析为 `../../tools/`。所有命令都必须指向这套当前插件工具，不得因宿主平台差异跳过。

## 准入流程

1. 在助手对话正文完整展示 `docs/capabilities.md` 和 `python tools/telemetry.py notice` 的完整输出。工具 stdout、隐藏上下文、脚本文件或仅给路径不算展示。
2. 只向用户询问“同意使用统计”或“不同意使用统计”，等待明确选择。
3. 选择后执行对应命令：

   ```text
   python tools/telemetry.py consent --accept
   python tools/telemetry.py consent --decline
   ```

4. 选择命令必须成功返回；随后执行 `python tools/telemetry.py consent --validate-gate`。

## 可验证准入凭证

授权命令会原子写入当前工作目录的 `.runtime/gate-consent.json`，`consent` 只能是 `accepted` 或 `declined`。两者都允许继续虚拟人功能；`declined` 仅表示关闭统计上传。

在执行任何路由、扫描、实施、凭据操作或下游 skill 前，必须检查 `python tools/telemetry.py consent --validate-gate`。命令必须返回 `valid (accepted)` 或 `valid (declined)`；文件不存在、格式错误、时间戳无效、来源不对或与 `consent --status` 不一致时，立即回到本门禁，禁止跳过。

## 边界

Hook 只有在当前消息显式调用 avatar skill 时才进入本门禁。自然语言、引用历史和代码块中的示例不算调用；普通后端、NLP、OpenAI SSE 或 Higress 调试不适用。
