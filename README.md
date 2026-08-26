# avatar-grill

独立的讯飞虚拟人 Grill Skill。本地包只暴露 `avatar-grill` 一个入口，使用集中问题前沿和执行契约，不提供流程模式选择。

它覆盖现有 avatar-platform 的 Web、Android、iOS、WebAPI、模板、直播、凭据、模型、知识库、交互、配置、排障、验证和授权后异步遥测能力。专业资料以内置 references 保存，平台工具以内置 `tools/` 保存；Claude Hook 位于 `hooks/`。

## 使用

显式调用 `avatar-grill`。它会先查询平台事实，再按 Grill 回合格式集中询问仍会改变执行路径的用户决策，生成 `.avatar/avatar-run-contract.json`，等待一次确认，随后直接执行和验证。

请只安装整个仓库，并与旧 `avatar-platform` 二选一；不要复制 `skills/avatar-grill/` 子目录，也不要同时启用两个插件。

## 本地校验

```powershell
python .\skills\avatar-grill\scripts\validate_contract.py .\path\to\project\.avatar\avatar-run-contract.json
```

本分支用于在 `firstdebug/avatar-platform` 中独立测试 `avatar-grill`。原版仍在 `main` / `avatar-platform-original` 分支。

## GitHub 分支测试

```bash
# Claude Code
claude plugin marketplace add https://github.com/firstdebug/avatar-platform.git --ref avatar-grill
claude plugin install avatar-grill@avatar-grill-marketplace

# Codex
codex plugin marketplace add firstdebug/avatar-platform --ref avatar-grill
codex plugin add avatar-grill@avatar-grill-marketplace
```

Cursor 在插件市场导入仓库时选择 `avatar-grill` 分支。测试时不要同时启用原版 `avatar-platform`，避免两套路由 Hook 同时注入。
