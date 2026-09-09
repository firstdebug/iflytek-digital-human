import express from 'express';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { avatarConfigHandler, avatarAuthHandler } from './xfyun-auth.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// 托管静态资源
app.use(express.static('public'));
app.use('/sdk', express.static('sdk'));

// 认证和非敏感配置统一由经过哈希校验的 canonical 模块提供。
app.get('/api/config', avatarConfigHandler);
app.get('/api/avatar-auth', avatarAuthHandler);

app.listen(PORT, () => {
  console.log(`✅ 服务器已启动: http://localhost:${PORT}`);
  console.log(`📝 配置接口: http://localhost:${PORT}/api/config`);
  console.log(`🔐 签名接口: http://localhost:${PORT}/api/avatar-auth`);
});
