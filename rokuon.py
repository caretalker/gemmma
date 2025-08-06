import sounddevice as sd
import soundfile as sf
import numpy as np
import queue
import time
from IPython.display import display, Audio
import pyttsx3
import requests
import os
import threading
import io
from concurrent.futures import ThreadPoolExecutor
import tempfile
import ssl
import urllib3

# SSL警告を抑制
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===========================================================================
# ★ 1. サーバーURL設定（エラー処理強化）
# ===========================================================================
def detect_server_url():
    """サーバーURLを検出します"""
    # ローカルサーバーチェック
    local_ports = [8000, 8001, 8002, 8003, 8004, 8005]
    
    def check_port(port):
        try:
            response = requests.get(f"http://localhost:{port}/docs", timeout=1)
            if response.status_code == 200:
                return f"http://localhost:{port}"
        except:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(check_port, local_ports))
        for result in results:
            if result:
                print(f"✅ ローカルサーバーを発見: {result}")
                return result
    
    # ngrok URLを手動入力
    print("🌐 ローカルサーバーが見つかりません。")
    print("📱 ngrok公開URLを入力してください（例: https://xxxxx.ngrok-free.app）")
    print("   またはローカルで実行する場合は 'local' と入力してください")
    
    user_input = input("URL入力: ").strip()
    
    if user_input.lower() == 'local':
        return "http://localhost:8000"
    elif user_input:
        ngrok_url = user_input
        if not ngrok_url.startswith('http'):
            ngrok_url = 'https://' + ngrok_url
        
        # ngrok URLの接続テスト
        print(f"🔍 接続テスト中: {ngrok_url}")
        try:
            # ngrokの特殊ヘッダーを追加
            headers = {
                'ngrok-skip-browser-warning': 'true',
                'User-Agent': 'Mozilla/5.0'
            }
            test_response = requests.get(
                f"{ngrok_url}/docs", 
                timeout=5, 
                headers=headers,
                verify=False  # SSL検証を一時的に無効化
            )
            if test_response.status_code in [200, 404, 405]:  # 接続は成功
                print(f"✅ ngrok URLに接続成功: {ngrok_url}")
                return ngrok_url
        except Exception as e:
            print(f"⚠️ 接続テスト失敗: {e}")
            print("   URLを確認するか、新しいngrokトンネルを作成してください")
            
    return "http://localhost:8000"

SERVER_URL = detect_server_url()
print(f"🎯 使用するサーバーURL: {SERVER_URL}")

# ===========================================================================
# ★ 2. グローバル状態管理
# ===========================================================================
class SystemState:
    """システム全体の状態を管理"""
    def __init__(self):
        self.is_tts_playing = False
        self.is_recording = False
        self.lock = threading.Lock()
        
    def set_tts_playing(self, state):
        with self.lock:
            self.is_tts_playing = state
            
    def set_recording(self, state):
        with self.lock:
            self.is_recording = state
            
    def can_record(self):
        with self.lock:
            return not self.is_tts_playing
            
    def can_play_tts(self):
        with self.lock:
            return not self.is_recording

system_state = SystemState()

# ===========================================================================
# ★ 3. 改善版VADクラス
# ===========================================================================
class ImprovedVAD:
    """改善された音声活動検出"""
    def __init__(self, calibration_seconds=3, voice_threshold_multiplier=3.0):
        self.calibration_seconds = calibration_seconds
        self.voice_threshold_multiplier = voice_threshold_multiplier
        self.baseline_rms = None
        self.calibration_samples = []
        self.is_calibrated = False
        self.voice_threshold = 0.01
        self.samples_needed = calibration_seconds * 50
        self.min_threshold = 0.001

    def calibrate(self, rms_value):
        """キャリブレーション"""
        self.calibration_samples.append(rms_value)
        
        if len(self.calibration_samples) >= self.samples_needed:
            sorted_samples = np.sort(self.calibration_samples)
            trim_count = len(sorted_samples) // 10
            trimmed_samples = sorted_samples[trim_count:-trim_count] if trim_count > 0 else sorted_samples
            
            self.baseline_rms = np.mean(trimmed_samples)
            self.voice_threshold = max(
                self.baseline_rms * self.voice_threshold_multiplier,
                self.min_threshold
            )
            self.is_calibrated = True
            print(f"\n[VAD] キャリブレーション完了！")
            print(f"  ベースライン: {self.baseline_rms:.6f}")
            print(f"  音声閾値: {self.voice_threshold:.6f}")
            return True
        return False

    def is_voice(self, rms_value):
        if not self.is_calibrated:
            return False
        if system_state.is_tts_playing:
            return False
        if rms_value > self.voice_threshold * 10:
            return False
        return rms_value > self.voice_threshold

# ===========================================================================
# ★ 4. 堅牢版AIクライアント（エラー処理強化）
# ===========================================================================
class RobustAIClient:
    """堅牢版AIクライアント - 接続エラーに強い"""
    
    def __init__(self, server_url):
        self.server_url = server_url
        self.is_ngrok = 'ngrok' in server_url
        self.session = self.create_session()
        self.retry_count = 3
        
    def create_session(self):
        """セッションを作成（ngrok用の特別設定付き）"""
        session = requests.Session()
        session.headers.update({
            'Connection': 'keep-alive',
            'User-Agent': 'Mozilla/5.0'
        })
        
        if self.is_ngrok:
            # ngrok用の特別なヘッダー
            session.headers.update({
                'ngrok-skip-browser-warning': 'true'
            })
            # SSL検証を緩和（開発環境のみ）
            session.verify = False
            
        return session
        
    def send_audio(self, audio_data, sample_rate=16000):
        """音声データを送信（リトライ機能付き）"""
        print("🚀 AI送信中...")
        
        for attempt in range(self.retry_count):
            try:
                # WAVファイルをメモリ内で作成
                with io.BytesIO() as wav_buffer:
                    sf.write(wav_buffer, audio_data, sample_rate, format='WAV', subtype='PCM_16')
                    wav_buffer.seek(0)
                    wav_data = wav_buffer.read()
                
                files = {'audio': ('recording.wav', wav_data, 'audio/wav')}
                
                # リクエスト送信
                response = self.session.post(
                    f"{self.server_url}/voice-chat/", 
                    files=files, 
                    timeout=30,
                    verify=False if self.is_ngrok else True
                )
                
                response.raise_for_status()
                ai_response_data = response.json()
                ai_response = ai_response_data.get("response", "（AIから応答がありませんでした）")
                
                print(f"🤖 応答受信完了")
                return ai_response
                
            except requests.exceptions.SSLError as e:
                print(f"⚠️ SSL エラー (試行 {attempt + 1}/{self.retry_count})")
                if attempt < self.retry_count - 1:
                    print("   再接続を試みます...")
                    time.sleep(2)
                    # セッションを再作成
                    self.session.close()
                    self.session = self.create_session()
                else:
                    return "SSL接続エラーが発生しました。ngrok URLを確認してください。"
                    
            except requests.exceptions.ConnectionError as e:
                print(f"⚠️ 接続エラー (試行 {attempt + 1}/{self.retry_count})")
                if attempt < self.retry_count - 1:
                    print("   再接続を試みます...")
                    time.sleep(2)
                else:
                    return "サーバーに接続できません。URLまたはngrokの状態を確認してください。"
                    
            except requests.exceptions.Timeout:
                return "⏰ タイムアウト（30秒）"
                
            except Exception as e:
                print(f"❌ 予期しないエラー: {type(e).__name__}: {str(e)[:100]}")
                return f"エラー: {str(e)[:50]}..."
        
        return "複数回の試行に失敗しました。接続を確認してください。"

# ===========================================================================
# ★ 5. 改善版TTS
# ===========================================================================
class ImprovedTTS:
    """改善版TTS"""
    
    def __init__(self):
        self.engine = None
        self.init_engine()
        
    def init_engine(self):
        """TTSエンジンを初期化"""
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', 180)
            self.engine.setProperty('volume', 0.9)
            
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if 'japanese' in voice.id.lower() or 'ja' in voice.id.lower():
                    self.engine.setProperty('voice', voice.id)
                    break
                    
            print("✅ TTSエンジン準備完了")
            return True
        except Exception as e:
            print(f"⚠️ TTSエンジン初期化エラー: {e}")
            self.engine = None
            return False
    
    def speak(self, text):
        """同期的に読み上げ"""
        if not text:
            return
            
        system_state.set_tts_playing(True)
        print(f"🔊 読み上げ中: {text[:50]}...")
        
        try:
            if self.engine is None:
                if not self.init_engine():
                    print(f"📝 TTS無効: {text}")
                    return
            
            self.engine.say(text)
            self.engine.runAndWait()
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ TTS読み上げエラー: {e}")
            self.engine = None
            
        finally:
            system_state.set_tts_playing(False)
            print("✅ 読み上げ完了")

# ===========================================================================
# ★ 6. 録音処理
# ===========================================================================
def record_improved(vad=None, output_filename="recording.wav"):
    """改善された録音処理"""
    SAMPLERATE = 16000
    BLOCK_DURATION_MS = 30
    BLOCKSIZE = int(SAMPLERATE * BLOCK_DURATION_MS / 1000)
    SILENCE_SECONDS = 1.5
    MAX_RECORDING_SECONDS = 30

    # VADが渡されていない場合は新規作成（初回のみ）
    if vad is None:
        vad = ImprovedVAD()
        need_calibration = True
    else:
        need_calibration = False
        
    audio_queue = queue.Queue()
    recording_started = False

    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"⚠️ 録音: {status}")
        audio_queue.put(indata.copy())

    try:
        with sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype='float32', 
                          blocksize=BLOCKSIZE, callback=audio_callback):
            
            while system_state.is_tts_playing:
                print("⏸️ TTS再生中... 待機しています")
                time.sleep(0.5)
            
            system_state.set_recording(True)
            
            # 初回のみキャリブレーション
            if need_calibration:
                print("📊 環境音をキャリブレーション中（3秒）...")
                print("静かにしてください...")
                
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except:
                        break
                
                while not vad.is_calibrated:
                    try:
                        audio_chunk = audio_queue.get(timeout=1)
                        rms = np.sqrt(np.mean(audio_chunk**2))
                        if vad.calibrate(rms):
                            break
                    except queue.Empty:
                        pass
            else:
                # キューをクリア
                while not audio_queue.empty():
                    try:
                        audio_queue.get_nowait()
                    except:
                        break
            
            print("🎤 話してください...")
            recorded_frames = []
            is_recording = False
            last_voice_time = None
            recording_start_time = None

            while True:
                if system_state.is_tts_playing:
                    print("⚠️ TTS再生を検出。録音を中断します。")
                    break
                    
                try:
                    audio_chunk = audio_queue.get(timeout=0.1)
                    rms = np.sqrt(np.mean(audio_chunk**2))

                    if vad.is_voice(rms):
                        if not is_recording:
                            print("🔴 音声を検出！録音開始")
                            is_recording = True
                            recording_started = True
                            recording_start_time = time.time()
                        recorded_frames.append(audio_chunk)
                        last_voice_time = time.time()
                    
                    elif is_recording:
                        recorded_frames.append(audio_chunk)
                        
                        if time.time() - last_voice_time > SILENCE_SECONDS:
                            print("⏹️ 録音終了")
                            break
                        
                        if time.time() - recording_start_time > MAX_RECORDING_SECONDS:
                            print("⏹️ 最大録音時間に達しました")
                            break
                            
                except queue.Empty:
                    if recording_started and is_recording and last_voice_time:
                        if time.time() - last_voice_time > SILENCE_SECONDS:
                            break

            system_state.set_recording(False)
            
            if recorded_frames:
                recording = np.concatenate(recorded_frames, axis=0)
                duration = len(recording) / SAMPLERATE
                print(f"💾 録音完了: {duration:.1f}秒 @ {SAMPLERATE}Hz")
                
                if np.max(np.abs(recording)) > 0:
                    recording = recording / np.max(np.abs(recording))
                
                return recording, SAMPLERATE, vad  # VADも返す
            else:
                print("⚠️ 音声が検出されませんでした")
                return None, SAMPLERATE, vad  # VADも返す

    except Exception as e:
        print(f"❌ 録音エラー: {e}")
        return None, SAMPLERATE, vad  # VADも返す
    finally:
        system_state.set_recording(False)

# ===========================================================================
# ★ 7. メイン処理
# ===========================================================================
def main_voice_chat():
    """堅牢版AI音声チャットシステム"""
    
    print("\n🎙️ AI音声対話システム（堅牢版 v3）")
    print("="*50)
    print("📌 改善内容:")
    print("  • ngrok接続エラー対策")
    print("  • 自動リトライ機能")
    print("  • SSL/接続エラーの処理強化")
    print("  • キャリブレーションは初回のみ")
    print("="*50)
    
    ai_client = RobustAIClient(SERVER_URL)
    tts = ImprovedTTS()
    
    session_count = 1
    error_count = 0
    max_errors = 5
    vad = None  # VADを保持
    
    try:
        while True:
            print(f"\n{'='*50}")
            print(f"📍 セッション #{session_count}")
            
            start_time = time.time()
            audio_data, sample_rate, vad = record_improved(vad)  # VADを渡す
            
            if audio_data is not None:
                record_time = time.time() - start_time
                print(f"⏱️ 録音時間: {record_time:.1f}秒")
                
                send_start = time.time()
                ai_response = ai_client.send_audio(audio_data, sample_rate)
                ai_time = time.time() - send_start
                
                print(f"⏱️ AI応答時間: {ai_time:.1f}秒")
                
                if ai_response and not any(err in ai_response for err in ["エラー", "SSL", "接続", "タイムアウト"]):
                    print(f"\n🤖 ケアトーカー: {ai_response}")
                    tts.speak(ai_response)
                    error_count = 0  # エラーカウントをリセット
                else:
                    print(f"⚠️ 応答エラー: {ai_response}")
                    error_count += 1
                    
                    if error_count >= max_errors:
                        print(f"\n❌ エラーが{max_errors}回連続で発生しました。")
                        print("以下を確認してください：")
                        print("1. Google Colabでサーバーが実行中か")
                        print("2. ngrok URLが正しいか")
                        print("3. ngrokトンネルが有効か")
                        
                        retry = input("\n再試行しますか？ (y/n): ")
                        if retry.lower() != 'y':
                            break
                        error_count = 0
                
                session_count += 1
                
            else:
                print("⚠️ 録音データがありません。")
            
            # 待機時間を短縮
            print("\n⏸️ 次の録音を開始... (Ctrl+C で終了)")
            time.sleep(1)  # 2秒から1秒に短縮

    except KeyboardInterrupt:
        print("\n\n👋 対話を終了しました。お疲れさまでした！")
    except Exception as e:
        print(f"\n❌ システムエラー: {e}")
    finally:
        if ai_client.session:
            ai_client.session.close()
        if tts.engine:
            try:
                tts.engine.stop()
            except:
                pass

# ===========================================================================
# ★ 8. 起動
# ===========================================================================
if __name__ == "__main__":
    main_voice_chat()
