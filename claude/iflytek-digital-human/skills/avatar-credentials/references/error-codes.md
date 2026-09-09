# 常见错误码

```yaml
10110: appId 错误
  fix: 重新复制 appId

10113: apiSecret 错误或签名错误
  fix: 
    - 检查 apiSecret 拼写
    - 检查签名生成逻辑

10120: avatarId 未授权
  fix: 在控制台授权该形象

10121: sceneId 未发布或错误
  fix: 
    - 发布接口服务
    - 检查 sceneId 拼写

11203: 超过并发路数限制
  fix: 默认1路，关闭其他连接或申请更多路数
```
