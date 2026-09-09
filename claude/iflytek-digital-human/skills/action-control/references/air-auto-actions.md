# 自动动作 AIR

**AIR (Automatic Interactive Response)**: 根据播报内容自动匹配合适的手势和表情。

## 启用 AIR

### Web
```javascript
// 全局启用 AIR
avatar.setGlobalParams({
  air: {
    air: true  // 启用自动动作
  }
});

// 之后的所有播报都会自动匹配动作
await avatar.writeText('欢迎来到我们的展厅', { nlp: false });
// 虚拟人会自动做出欢迎手势
```

### Android
```java
// 配置 AIR 参数
AvatarParams.AIR air = new AvatarParams.AIR();
air.setAir(true);  // 启用自动动作

AvatarParams params = new AvatarParams();
params.setAIR(air);

controller.setGlobalParams(params);

// 之后的播报会自动匹配动作
controller.writeText("欢迎来到我们的展厅", null);
```

### iOS
```objc
// 配置 AIR 参数
AvatarParamsAIR *air = [AvatarParamsAIR new];
air.air(YES);  // 启用自动动作

AvatarParams *params = [AvatarParams new];
params.air(air);

controller.globalParams = params;

// 之后的播报会自动匹配动作
[controller writeText:@"欢迎来到我们的展厅" textParams:nil];
```

---

## AIR 动作匹配规则

AIR 会根据播报内容智能匹配动作：

```yaml
欢迎类话术:
  文本: "欢迎" / "您好" / "大家好"
  动作: 挥手 / 欢迎手势

解释类话术:
  文本: "首先" / "其次" / "另外"
  动作: 手指指向 / 手掌展开

强调类话术:
  文本: "重点" / "注意" / "关键"
  动作: 手势加重 / 点头

数字类话术:
  文本: "第一" / "第二" / "三个"
  动作: 手指计数

疑问类话术:
  文本: "吗" / "呢" / "什么"
  动作: 摊手 / 疑惑表情

肯定类话术:
  文本: "是的" / "没错" / "正确"
  动作: 点头
```

**示例**:
```javascript
await avatar.writeText('首先，我们来看一下产品特点', { nlp: false });
// AIR 自动匹配"解释"类手势（如手掌展开）

await avatar.writeText('欢迎来到我们的展厅', { nlp: false });
// AIR 自动匹配"欢迎"手势（如挥手）
```
