# 安装

这是独立本地仓库，当前没有远程地址，也没有改动原 `avatar-platform`。

## Claude Code

将整个 `avatar-grill` 目录作为插件目录安装。不要只复制 `skills/avatar-grill/`，否则会丢失根目录的 `tools/`、`config/` 和 Hook。显式调用 `avatar-grill`。

## Codex

将整个 `avatar-grill` 目录作为本地插件添加，插件清单为 `.codex-plugin/plugin.json`。显式调用 `avatar-grill`。

## Cursor

将整个 `avatar-grill` 目录通过 Cursor 的插件导入功能导入，插件清单为 `.cursor-plugin/plugin.json`。Cursor 没有 Claude Hook，必须显式调用 `avatar-grill`。

安装后检查仓库根目录存在 `tools/xfyun_common.py`；不存在即为错误安装，不要从其他 cache/backup 目录补文件。

`avatar-grill` 与旧 `avatar-platform` 互斥，请不要同时安装，否则会出现两套路由和两套执行边界。三种安装方式都只注册一个 Skill。
