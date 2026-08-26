# 凭据存储

## 环境变量（推荐）

```bash
# .env 文件
AVATAR_APP_ID=12345678
AVATAR_API_KEY=abcdef1234567890abcdef1234567890
AVATAR_API_SECRET=1234567890abcdef1234567890abcdef
AVATAR_SCENE_ID=scene1234567890abcdef1234567890ab
AVATAR_AVATAR_ID=118801001
AVATAR_VCN=x4_yezi
```

**⚠️ 安全提示**:
```
.gitignore 必须包含:
  .env
  config/credentials.json
  **/credentials.*
```

## 配置文件

```json
{
  "appId": "12345678",
  "apiKey": "abcdef1234567890abcdef1234567890",
  "apiSecret": "******",
  "sceneId": "scene1234567890abcdef1234567890ab",
  "avatarId": "118801001",
  "vcn": "x4_yezi"
}
```

## 代码中读取

```javascript
// Web
const credentials = {
  appId: process.env.AVATAR_APP_ID || import.meta.env.VITE_AVATAR_APP_ID,
  apiKey: process.env.AVATAR_API_KEY,
  apiSecret: process.env.AVATAR_API_SECRET,
  sceneId: process.env.AVATAR_SCENE_ID,
  avatarId: process.env.AVATAR_AVATAR_ID,
  vcn: process.env.AVATAR_VCN
};

// Android (gradle.properties)
def appId = project.findProperty('AVATAR_APP_ID') ?: ''

// iOS (Info.plist or Bundle)
let appId = Bundle.main.object(forInfoDictionaryKey: "AVATAR_APP_ID") as? String
```
