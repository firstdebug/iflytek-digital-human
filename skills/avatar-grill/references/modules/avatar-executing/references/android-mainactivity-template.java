package com.example.fitnessavatar;

import android.Manifest;
import android.content.pm.PackageManager;
import android.media.AudioFormat;
import android.media.MediaRecorder;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.TextUtils;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.iflytek.avalibrary.AvatarPlatform;
import com.iflytek.avalibrary.AvatarPlatformConfig;
import com.iflytek.avalibrary.AvatarPlayController;
import com.iflytek.avalibrary.IAvatarListener;
import com.iflytek.avalibrary.constant.AvatarConstant;
import com.iflytek.avalibrary.constant.AvatarDataType;
import com.iflytek.avalibrary.params.AudioParams;
import com.iflytek.avalibrary.params.AvatarParams;
import com.iflytek.avalibrary.params.TextParams;
import com.iflytek.avalibrary.videoplayer.rt.StreamPlayerFactory;
import com.iflytek.avalibrary.videoplayer.rt.interfaces.IStreamPlayer;
import com.iflytek.ys.core.log.LogLevel;
import com.iflytek.ys.core.recorder.AudioRecorder;

import org.json.JSONObject;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;

public class MainActivity extends AppCompatActivity {

    private static final String TAG = "FitnessAvatar";
    private static final int REQ_AUDIO = 1001;

    private final Handler mUi = new Handler(Looper.getMainLooper());

    private FrameLayout mAvatarContainer;
    private TextView mStatus;
    private TextView mSubtitle;
    private EditText mInput;

    private AvatarPlayController mController;
    private IStreamPlayer mStreamPlayer;
    private AudioRecorder mRecorder;
    private boolean mAvatarReady = false;
    private boolean mRecording = false;

    // credentials loaded from assets/credentials.json
    private String mAppId, mApiKey, mApiSecret, mServerUrl;
    private String mSceneId, mAvatarId, mVcn;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        mAvatarContainer = findViewById(R.id.avatar_container);
        mStatus = findViewById(R.id.tv_status);
        mSubtitle = findViewById(R.id.tv_subtitle);
        mInput = findViewById(R.id.et_input);

        findViewById(R.id.btn_ask).setOnClickListener(v -> ask());
        findViewById(R.id.btn_speak).setOnClickListener(v -> speak());
        findViewById(R.id.btn_interrupt).setOnClickListener(v -> interrupt());
        Button voice = findViewById(R.id.btn_voice);
        voice.setOnTouchListener((view, event) -> {
            switch (event.getAction()) {
                case android.view.MotionEvent.ACTION_DOWN: startVoice(); return true;
                case android.view.MotionEvent.ACTION_UP:
                case android.view.MotionEvent.ACTION_CANCEL: stopVoice(); return true;
            }
            return false;
        });

        if (!loadCredentials()) {
            setStatus("凭据加载失败: assets/credentials.json 缺失或不完整");
            return;
        }
        ensureAudioPermission();
        initSdk();
    }

    private boolean loadCredentials() {
        try (InputStream is = getAssets().open("credentials.json")) {
            byte[] buf = new byte[is.available()];
            int n = is.read(buf);
            JSONObject j = new JSONObject(new String(buf, 0, n, StandardCharsets.UTF_8));
            mAppId = j.optString("appId");
            mApiKey = j.optString("apiKey");
            mApiSecret = j.optString("apiSecret");
            mServerUrl = j.optString("serverUrl");
            mSceneId = j.optString("sceneId");
            mAvatarId = j.optString("avatarId");
            mVcn = j.optString("vcn");
            return !TextUtils.isEmpty(mAppId) && !TextUtils.isEmpty(mApiKey)
                    && !TextUtils.isEmpty(mApiSecret) && !TextUtils.isEmpty(mServerUrl);
        } catch (Exception e) {
            return false;
        }
    }

    private void ensureAudioPermission() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.RECORD_AUDIO}, REQ_AUDIO);
        }
    }

    // ==================== SDK 初始化 ====================
    private void initSdk() {
        setStatus("SDK 初始化中...");
        AvatarPlatformConfig config = new AvatarPlatformConfig.Builder()
                .setAppId(mAppId)
                .setApikey(mApiKey)      // 注意: 真实 API 是小写 k
                .setApiSecret(mApiSecret)
                .setServerUrl(mServerUrl)
                .setLogLevel(LogLevel.INFO)
                .build();

        AvatarPlatform.initialize(getApplicationContext(), config,
                (code, msg) -> {
                    // IInitListener.onResult(code, msg); 成功 code="0"
                    if ("0".equals(code)) {
                        mUi.post(this::onInitSuccess);
                    } else {
                        mUi.post(() -> setStatus("初始化失败 code=" + code + " " + msg));
                    }
                });
    }

    private void onInitSuccess() {
        setStatus("SDK 初始化成功, 连接中...");
        mController = AvatarPlatform.getController();

        // 全局参数: avatar / stream(xrtc) / tts / subtitle / scene
        AvatarParams params = new AvatarParams();

        AvatarParams.Stream stream = new AvatarParams.Stream();
        stream.setProtocol(AvatarConstant.STREAM_XRTC);

        AvatarParams.Avatar avatar = new AvatarParams.Avatar();
        avatar.setAvatarId(mAvatarId);
        avatar.setStream(stream);
        params.setAvatar(avatar);

        AvatarParams.TTS tts = new AvatarParams.TTS();
        tts.setVcn(mVcn);
        params.setTTS(tts);

        // 字幕由 SDK 渲染
        AvatarParams.Subtitle subtitle = new AvatarParams.Subtitle();
        subtitle.setSubtitle(1);
        subtitle.setFontColor("#FFFFFF");
        params.setSubtitle(subtitle);

        if (!TextUtils.isEmpty(mSceneId)) {
            AvatarParams.Scene scene = new AvatarParams.Scene();
            scene.setSceneId(mSceneId);
            params.setScene(scene);
        }

        mController.setGlobalParams(params);
        mController.setListenerHandler(mUi);
        mController.addAvatarListener(mAvatarListener);

        // 创建 xrtc 流播放器, 把容器交给 SDK 管理渲染面
        mStreamPlayer = StreamPlayerFactory.createPlayer(this, AvatarConstant.STREAM_XRTC);
        mStreamPlayer.setRenderArea(mAvatarContainer);
        // setStreamPlayer 内部自动 bindAvatar + setAvatarListener
        mController.setStreamPlayer(mStreamPlayer);

        mController.start();
    }

    // ==================== 事件监听 ====================
    private final IAvatarListener mAvatarListener = new IAvatarListener() {
        @Override
        public void onResult(String type, byte[] data, String extra) {
            // type: asr / nlp (AvatarDataType). 真实结构: 文本在 extra 的 JSON, 不在 data
            android.util.Log.i(TAG, "onResult type=" + type + " extra=" + extra);
            mUi.post(() -> {
                if (AvatarDataType.RESPONSE_ASR.equals(type)) {
                    String t = extractAsr(extra);
                    if (!TextUtils.isEmpty(t)) appendSubtitle("我: " + t);
                } else if (AvatarDataType.RESPONSE_NLP.equals(type)) {
                    // nlp 流式分片: extra.answer.text; status=1 中间, 2 结束 -> 累加
                    NlpChunk c = extractNlp(extra);
                    if (c != null && !TextUtils.isEmpty(c.text)) appendNlpStream(c);
                }
            });
        }

        @Override
        public void onEvent(String type, String value) {
            android.util.Log.i(TAG, "onEvent type=" + type + " value=" + value);
            mUi.post(() -> {
                setStatus("事件: " + type);
                mAvatarReady = true;
            });
        }

        @Override
        public void onError(String code, String desc, String extra) {
            android.util.Log.e(TAG, "onError code=" + code + " desc=" + desc + " extra=" + extra);
            mUi.post(() -> setStatus("错误 " + code + ": " + desc));
        }
    };

    // ASR 结果: extra JSON 里的 text 字段
    private String extractAsr(String extra) {
        if (TextUtils.isEmpty(extra)) return "";
        try {
            JSONObject j = new JSONObject(extra);
            return j.optString("text", "");
        } catch (Exception e) {
            return "";
        }
    }

    // NLP 流式分片: {answer:{text}, index, status(1中间/2结束), request_id}
    private static class NlpChunk {
        String text; int status; String reqId;
    }

    private NlpChunk extractNlp(String extra) {
        if (TextUtils.isEmpty(extra)) return null;
        try {
            JSONObject j = new JSONObject(extra);
            NlpChunk c = new NlpChunk();
            JSONObject ans = j.optJSONObject("answer");
            c.text = ans != null ? ans.optString("text", "") : "";
            c.status = j.optInt("status", 1);
            c.reqId = j.optString("request_id", "");
            return c;
        } catch (Exception e) {
            return null;
        }
    }

    // 流式累加: 同一 request_id 的分片拼到同一行, status=2 收尾
    private String mNlpReqId = null;
    private final StringBuilder mNlpBuf = new StringBuilder();
    private int mNlpLineStart = -1;

    private void appendNlpStream(NlpChunk c) {
        if (!c.reqId.equals(mNlpReqId)) {
            // 新一轮回答, 起新行
            mNlpReqId = c.reqId;
            mNlpBuf.setLength(0);
            mNlpLineStart = mSubtitle.getText().length();
            mSubtitle.append("教练: ");
        }
        mNlpBuf.append(c.text);
        // 重绘当前回答行
        CharSequence head = mSubtitle.getText().subSequence(0, mNlpLineStart);
        mSubtitle.setText(head + "教练: " + mNlpBuf);
        if (c.status == 2) {
            mSubtitle.append("\n");
            mNlpReqId = null;
        }
    }

    // ==================== 四大交互 ====================
    // 1. 文本提问 (走知识库+DeepSeek): writeText + TextParams.setNlp(true)
    private void ask() {
        if (!checkReady()) return;
        String q = mInput.getText().toString().trim();
        if (TextUtils.isEmpty(q)) return;
        appendSubtitle("我: " + q);
        TextParams tp = new TextParams();
        tp.setNlp(true);   // true = 文本交互, 经 NLP(知识库/DeepSeek)
        mController.writeText(q, tp);
        mInput.setText("");
    }

    // 2. 文本播报 (纯 TTS, 不经 NLP): writeText 默认 nlp=false
    private void speak() {
        if (!checkReady()) return;
        String t = mInput.getText().toString().trim();
        if (TextUtils.isEmpty(t)) return;
        mController.writeText(t);   // 默认 mNlp=false = 直接播报
        mInput.setText("");
    }

    // 3. 打断当前播报
    private void interrupt() {
        if (mController != null) mController.interrupt();
    }

    // 4. 语音交互: AudioRecorder + setAudioRecorder(recorder, audioParams.setNlp(true))
    private void startVoice() {
        if (!checkReady()) return;
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            ensureAudioPermission();
            return;
        }
        if (mRecording) return;
        mRecording = true;
        setStatus("聆听中...");
        // 采样率必须 16000, 单声道, 16bit
        mRecorder = new AudioRecorder(
                MediaRecorder.AudioSource.MIC,
                16000,
                AudioFormat.ENCODING_PCM_16BIT,
                AudioFormat.CHANNEL_IN_MONO);
        mRecorder.init();
        AudioParams ap = new AudioParams();
        ap.setNlp(true);   // 语音交互走 NLP
        // SDK 内部自动注册 PcmDataListener 泵送 PCM 到 writeAudio
        mController.setAudioRecorder(mRecorder, ap);
        mRecorder.startRecord();
    }

    private void stopVoice() {
        if (!mRecording) return;
        mRecording = false;
        setStatus("处理中...");
        if (mRecorder != null) mRecorder.stopRecord();
    }

    private boolean checkReady() {
        if (mController == null) {
            toast("SDK 未就绪");
            return false;
        }
        return true;
    }

    // ==================== UI 辅助 ====================
    private void setStatus(String s) { mStatus.setText(s); }

    private void appendSubtitle(String s) {
        mSubtitle.append(s + "\n");
    }

    private void toast(String s) { Toast.makeText(this, s, Toast.LENGTH_SHORT).show(); }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions,
                                           @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_AUDIO && (grantResults.length == 0
                || grantResults[0] != PackageManager.PERMISSION_GRANTED)) {
            toast("需要录音权限才能语音交互");
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mRecording && mRecorder != null) mRecorder.stopRecord();
        if (mController != null) {
            mController.removeAvatarListener(mAvatarListener);
            mController.stop();
            mController.destroy();
        }
    }
}



