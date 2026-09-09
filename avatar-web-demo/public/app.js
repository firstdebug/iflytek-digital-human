// Web SDK 集成 - 严格遵循 Playbook §3 字段锁定表
let avatar = null;
let player = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];
let config = {};

// 初始化
async function init() {
  try {
    // 获取配置
    const configRes = await fetch('/api/config');
    config = await configRes.json();

    // 获取签名 URL（安全：apiSecret 在服务端，前端只拿 signedUrl）
    const authRes = await fetch('/api/avatar-auth');
    const authData = await authRes.json();

    // 动态导入 SDK（IAvatarPlatform 是 default 导出）
    const module = await import('/sdk/avatar-web-sdk/avatar-sdk-web_3.2.3.1002/esm/index.js');
    const AvatarPlatform = module.default;
    const { SDKEvents, PlayerEvents } = module;

    // 1. 创建实例
    avatar = new AvatarPlatform();

    // 2. 设置认证信息（包含 serverUrl、signedUrl 等）
    avatar.setApiInfo({
      serverUrl: config.wsUrl,  // 必须显式设置，否则用 SDK 内置测试地址
      signedUrl: authData.signedUrl,
      appId: config.appId,
      sceneId: config.sceneId
    });

    // 3. 设置全局参数 - 严格按照 Playbook §3 字段锁定表
    avatar.setGlobalParams({
      // 顶层 stream：SDK 会读 protocol/bitrate（bitrate 会被 /1024）
      stream: {
        protocol: 'xrtc',   // 透明背景必须 xrtc
        fps: 25,
        bitrate: 2000,      // 顶层占位值（会被 /1024，真实值看 avatar.stream）
      },
      avatar: {
        avatar_id: config.avatarId,
        width: 720,
        height: 1280,
        // ✅ 关键：手写 avatar.stream，值原样发送不再 /1024（WYSIWYG）
        stream: {
          protocol: 'xrtc',   // 必填
          fps: 25,            // 必填
          bitrate: 2000,      // 必填，单位 kbps，这就是平台实际收到的值
          alpha: 1,           // 1=透明背景（用户选择了透明背景功能）
        },
      },
      tts: {
        vcn: config.vcn,
        speed: 50,
        pitch: 50,
        volume: 50,
      },
      avatar_dispatch: {
        interactive_mode: 0,   // 0=append 追加
      },
    });

    // 4. 监听事件（必须在 start 前注册）
    avatar.on(SDKEvents.connected, () => {
      console.log('✅ WebSocket 已连接');
      updateStatus('已连接', 'success');
    });

    avatar.on(SDKEvents.disconnected, () => {
      console.log('⚠️ WebSocket 已断开');
      updateStatus('已断开', 'warning');
    });

    avatar.on(SDKEvents.error, (error) => {
      console.error('❌ SDK 错误:', error);
      updateStatus(`错误: ${error.code || error.message}`, 'error');
    });

    avatar.on(SDKEvents.stream_start, () => {
      console.log('📡 云端推流开始');
    });

    // 播放器事件
    avatar.on(PlayerEvents.play, () => {
      console.log('▶️ 播放器开始播放');
    });

    avatar.on(PlayerEvents.playing, () => {
      console.log('▶️ 播放中（首帧已渲染）');
      updateStatus('播放中', 'success');
    });

    avatar.on(PlayerEvents.playNotAllowed, () => {
      console.log('⚠️ 浏览器阻止自动播放，需要用户交互');
      showResumeHint();
    });

    // NLP 回复事件
    avatar.on(SDKEvents.nlp_result, (data) => {
      console.log('💬 NLP 回复:', data);
      addMessage('assistant', data.answer || data.text);
    });

    // ASR 识别结果
    avatar.on(SDKEvents.asr_result, (data) => {
      console.log('🎤 ASR 识别:', data);
      if (data.text) {
        addMessage('user', data.text);
      }
    });

    // 5. 启动（传入渲染容器）
    const wrapper = document.getElementById('avatar-container');
    await avatar.start({ wrapper });

    player = avatar.player;

    updateStatus('就绪', 'success');
    enableControls();

  } catch (error) {
    console.error('初始化失败:', error);
    updateStatus(`初始化失败: ${error.message}`, 'error');
  }
}

// 发送文本（文字对话功能）
async function sendText() {
  const input = document.getElementById('text-input');
  const text = input.value.trim();

  if (!text || !avatar) return;

  try {
    addMessage('user', text);
    await avatar.writeText(text, { nlp: true });  // 启用 NLP 对话
    input.value = '';
  } catch (error) {
    console.error('发送文本失败:', error);
    updateStatus(`发送失败: ${error.message}`, 'error');
  }
}

// 语音交互（点击开始/停止模式）
async function toggleVoice() {
  const btn = document.getElementById('voice-btn');

  if (!isRecording) {
    // 开始录音
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,  // 虚拟人 SDK 要求 16000
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true
        }
      });

      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        await sendAudio(audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      isRecording = true;
      btn.textContent = '🔴 停止录音';
      btn.classList.add('recording');
      updateStatus('正在录音...', 'info');

    } catch (error) {
      console.error('录音失败:', error);
      updateStatus(`录音失败: ${error.message}`, 'error');
    }
  } else {
    // 停止录音
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
    isRecording = false;
    btn.textContent = '🎤 开始语音';
    btn.classList.remove('recording');
  }
}

// 发送音频（语音交互功能）
async function sendAudio(audioBlob) {
  try {
    // 转换为 PCM 并发送给 SDK
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
    const pcmData = audioBuffer.getChannelData(0);

    // 转为 Int16Array（SDK 要求的格式）
    const int16Data = new Int16Array(pcmData.length);
    for (let i = 0; i < pcmData.length; i++) {
      int16Data[i] = Math.max(-1, Math.min(1, pcmData[i])) * 0x7FFF;
    }

    await avatar.writeAudio(int16Data.buffer, { nlp: true });
    updateStatus('音频已发送', 'success');

  } catch (error) {
    console.error('发送音频失败:', error);
    updateStatus(`发送音频失败: ${error.message}`, 'error');
  }
}

// 触发动作（动作控制功能）
async function triggerAction(actionId) {
  if (!avatar) return;

  try {
    await avatar.triggerAction({ action_id: actionId });
    updateStatus(`动作已触发: ${actionId}`, 'success');
  } catch (error) {
    console.error('触发动作失败:', error);
    updateStatus(`动作失败: ${error.message}`, 'error');
  }
}

// 恢复播放（处理浏览器自动播放限制）
function resumePlay() {
  if (player) {
    player.resume();
    document.getElementById('resume-hint').style.display = 'none';
  }
}

// UI 辅助函数
function updateStatus(message, type) {
  const statusEl = document.getElementById('status');
  statusEl.textContent = message;
  statusEl.className = `status ${type}`;
}

function addMessage(role, text) {
  const messagesEl = document.getElementById('messages');
  const msgEl = document.createElement('div');
  msgEl.className = `message ${role}`;
  msgEl.textContent = text;
  messagesEl.appendChild(msgEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function showResumeHint() {
  document.getElementById('resume-hint').style.display = 'block';
}

function enableControls() {
  document.getElementById('send-btn').disabled = false;
  document.getElementById('voice-btn').disabled = false;
  document.querySelectorAll('.action-btn').forEach(btn => btn.disabled = false);
}

// 清理资源
window.addEventListener('beforeunload', () => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
  if (avatar) {
    avatar.stop();
    avatar.destroy();
  }
});

// 绑定事件
document.getElementById('init-btn').addEventListener('click', init);
document.getElementById('send-btn').addEventListener('click', sendText);
document.getElementById('text-input').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendText();
});
document.getElementById('voice-btn').addEventListener('click', toggleVoice);
document.getElementById('resume-btn').addEventListener('click', resumePlay);

// 动作按钮
document.querySelectorAll('.action-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const actionId = btn.dataset.action;
    triggerAction(actionId);
  });
});
