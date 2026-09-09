import crypto from 'crypto';

const CANONICAL_WS_URL = 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact';

function required(env, name) {
  const value = env[name];
  if (!value) throw new Error(`missing ${name}`);
  return value;
}

function requireLength(value, name, length) {
  if (value.length !== length || value.includes('*')) {
    throw new Error(`invalid ${name}`);
  }
  return value;
}

export function avatarConfigFromEnv(env = process.env) {
  return {
    appId: required(env, 'APP_ID'),
    sceneId: required(env, 'SCENE_ID'),
    avatarId: required(env, 'AVATAR_ID'),
    vcn: required(env, 'VCN'),
    wsUrl: required(env, 'WS_URL'),
  };
}

export function generateSignedUrlFromEnv(env = process.env, now = new Date()) {
  const apiKey = requireLength(required(env, 'API_KEY'), 'API_KEY', 32);
  const apiSecret = requireLength(required(env, 'API_SECRET'), 'API_SECRET', 32);
  const wsUrl = required(env, 'WS_URL');
  if (wsUrl !== CANONICAL_WS_URL) {
    throw new Error('invalid WS_URL');
  }
  const url = new URL(wsUrl);
  const date = now.toUTCString();
  const host = url.host;
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${url.pathname} HTTP/1.1`;
  const signature = crypto
    .createHmac('sha256', apiSecret)
    .update(signatureOrigin)
    .digest('base64');
  const authorization = `api_key="${apiKey}", algorithm="hmac-sha256", headers="host date request-line", signature="${signature}"`;
  url.searchParams.set('authorization', Buffer.from(authorization).toString('base64'));
  url.searchParams.set('date', date);
  url.searchParams.set('host', host);
  return url.toString();
}

export function avatarConfigHandler(req, res) {
  try {
    res.json(avatarConfigFromEnv());
  } catch (error) {
    res.status(500).json({ error: 'avatar environment is invalid' });
  }
}

export function avatarAuthHandler(req, res) {
  try {
    res.json({ signedUrl: generateSignedUrlFromEnv(), timestamp: Date.now() });
  } catch (error) {
    res.status(500).json({ error: 'avatar authentication is invalid' });
  }
}
