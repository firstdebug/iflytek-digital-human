---
name: avatar-network-debug
description: 虚拟人网络连接问题诊断
tags:
  - network
  - websocket
  - connectivity
  - troubleshooting
priority: high
---

# avatar-network-debug: 网络诊断

## 定位

诊断虚拟人 WebSocket 连接和流媒体网络问题。

## 调用时机

- 连接失败（错误码 10200/10201）
- WebSocket 超时
- 流媒体不可达（错误码 10202）
- 由 `avatar-workflow-entry` 路由

---

## 诊断流程概览

```
Step 1: 基础网络检查
Step 2: WebSocket 连通性测试
Step 3: 鉴权握手验证
Step 4: 流媒体服务测试
Step 5: 防火墙和代理检查
Step 6: 生成诊断报告

→ 输出: 诊断结果 + 修复建议
```

| Step | 检查内容 | 详见 reference |
|------|----------|----------------|
| 1 | 网络连接状态 / DNS 解析 / 网络质量 | references/network-checks.md |
| 2 | TCP 连接 / WebSocket 握手 / 关闭码 | references/websocket-tests.md |
| 3 | 签名生成 / 鉴权参数验证 | references/auth-verification.md |
| 4 | XRTC/WebRTC 连通性 / 流媒体诊断 | references/stream-tests.md |
| 5 | 防火墙 / 代理 / 企业网络限制 | references/firewall-proxy.md |
| 6 | 诊断报告 / 一键脚本 / 输出格式 | references/diagnostic-output.md |

---

## 决策分支（场景 → 应读哪个 reference）

- **完全连不上 / 离线** → 从 Step 1 开始，读 `references/network-checks.md`（网络状态、DNS、网络质量）。
- **网络正常但 WebSocket 建立失败 / 频繁断开** → 读 `references/websocket-tests.md`（TCP 端口、握手代码、关闭码含义）。
- **握手被拒绝、关闭码 1008、错误提示 authorization 无效** → 读 `references/auth-verification.md`（签名算法、date 格式、URL 参数）。
- **连接成功但看不到虚拟人 / 首帧超时 / 播放卡顿** → 读 `references/stream-tests.md`（XRTC/WebRTC 连通性、流媒体诊断）。
- **企业内网 / 代理环境 / 特定网络下才失败** → 读 `references/firewall-proxy.md`（端口放行、代理、白名单）。
- **需要交付诊断结论或跑一键脚本** → 读 `references/diagnostic-output.md`（报告结构、Bash 脚本、输出格式）。

---

## 关键约束 / Red Flags

- **date 必须是 UTC GMT 格式**（`toUTCString()`），如 `Mon, 13 Jul 2026 10:30:00 GMT`。格式错误会导致签名不匹配、握手被拒（关闭码 1008）。这是最高频根因。
- **签名算法必须是 HMAC-SHA256**，不可用 HMAC-SHA1 / MD5。
- **authorization 最终为标准 Base64 编码**，且其本身无需再做 URL 编码；`date`、`host` 参数才需要 URL 编码。
- **关闭码 1008 = 鉴权失败**，优先排查签名与凭据，而非网络。
- **关闭码 1006 = 异常断开**，指向网络稳定性 / 防火墙，而非鉴权。
- **流媒体走 UDP 动态端口**，企业防火墙常只放行 443，UDP 被拦会导致首帧超时——连接成功不代表流媒体可达。

---

## references/ 索引

| 文件 | 内容 |
|------|------|
| references/network-checks.md | Step 1：网络连接状态（Web/Android/iOS）、DNS 解析测试、网络质量评估 |
| references/websocket-tests.md | Step 2：TCP 连接测试命令、WebSocket 握手测试代码、关闭码诊断 |
| references/auth-verification.md | Step 3：签名生成代码、常见签名错误、鉴权参数与 URL 编码 |
| references/stream-tests.md | Step 4：XRTC/WebRTC 连通性测试代码、流媒体问题诊断 |
| references/firewall-proxy.md | Step 5：防火墙规则、代理检测、企业网络限制 |
| references/diagnostic-output.md | Step 6：诊断报告结构、一键 Bash 脚本、成功/问题输出格式 |

---

## 验证清单

- [ ] Step 1 网络与 DNS 通过（在线、解析正常、延迟丢包可接受）
- [ ] Step 2 TCP 443 可连、WebSocket 握手成功
- [ ] Step 3 签名 date/算法/编码正确，无 1008 拒绝
- [ ] Step 4 收到首帧、无持续卡顿
- [ ] Step 5 防火墙/代理/白名单已放行 443 与 UDP
- [ ] Step 6 已产出诊断报告（含根因与修复建议）

---

## 相关技能

- `avatar-workflow-entry`: 路由入口
- `avatar-troubleshoot`: 调用本技能进行网络诊断
- `avatar-preflight`: Layer 4 网络连通性检查
