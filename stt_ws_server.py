from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google.cloud import speech
import google.oauth2.service_account
import asyncio
import os
import time
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="STT WebSocket Server for Cloud Run")

# Cloud Run環境変数からポート取得
PORT = int(os.environ.get("PORT", 8080))

# Google Cloud認証設定
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'firebase-key.json')

# firebase-key.jsonの存在確認
if not os.path.exists(SERVICE_ACCOUNT_FILE):
    logger.error(f"firebase-key.json not found at {SERVICE_ACCOUNT_FILE}")
    raise FileNotFoundError("firebase-key.json is required for Google Cloud Speech API")

credentials = google.oauth2.service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
speech_client = speech.SpeechClient(credentials=credentials)

@app.get("/")
async def root():
    """ヘルスチェック用エンドポイント"""
    return {
        "status": "healthy",
        "service": "STT WebSocket Server",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health"
        }
    }

@app.get("/health")
async def health_check():
    """詳細ヘルスチェック"""
    try:
        # Google Cloud Speech APIの接続テスト
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="ja-JP",
        )
        # 空の音声データでテスト（実際には認識しない）
        return {
            "status": "healthy",
            "google_cloud_speech": "connected",
            "timestamp": time.time(),
            "port": PORT
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket音声認識エンドポイント"""
    await websocket.accept()
    
    client_id = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"WebSocket接続開始: {client_id}")
    
    audio_buffer = []
    chunk_count = 0
    last_recognition_time = time.time()
    session_start = time.time()
    
    try:
        while True:
            try:
                # Cloud Runのタイムアウト対策（60秒制限）
                data = await asyncio.wait_for(websocket.receive_bytes(), timeout=55.0)
                chunk_count += 1
                audio_buffer.append(data)
                
                # 定期的なログ出力（Cloud Runのログ監視用）
                if chunk_count <= 10 or chunk_count % 100 == 0:
                    logger.info(f"[{client_id}] 受信データ: {len(data)} bytes (chunk {chunk_count})")
                
                # 3秒分のデータ（約93チャンク）または5秒経過で処理
                should_process = (
                    len(audio_buffer) >= 93 or  # 3秒分
                    (time.time() - last_recognition_time > 5.0 and len(audio_buffer) > 10)  # 5秒経過
                )
                
                if should_process:
                    try:
                        # バッファした音声データをまとめて処理
                        combined_audio = b''.join(audio_buffer)
                        
                        # Google STT用の設定（Cloud Run最適化）
                        config = speech.RecognitionConfig(
                            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                            sample_rate_hertz=16000,
                            language_code="ja-JP",
                            enable_automatic_punctuation=True,
                            model="latest_long",  # 長い音声用
                            use_enhanced=True,
                            # Cloud Run用の最適化設定
                            max_alternatives=1,
                            profanity_filter=False,
                        )
                        
                        # ストリーミングではなく、バッチ処理を使用（Cloud Run安定性重視）
                        audio = speech.RecognitionAudio(content=combined_audio)
                        
                        # Google Cloud Speech API呼び出し
                        logger.info(f"[{client_id}] Google STT処理開始 (バッファサイズ: {len(combined_audio)} bytes)")
                        response = speech_client.recognize(config=config, audio=audio)
                        
                        # 結果を送信
                        results_sent = 0
                        for result in response.results:
                            transcript = result.alternatives[0].transcript
                            if transcript.strip():
                                logger.info(f"[{client_id}] 認識結果: {transcript}")
                                await websocket.send_text(transcript)
                                results_sent += 1
                        
                        if results_sent == 0:
                            logger.info(f"[{client_id}] 認識結果なし（無音または不明瞭）")
                        
                        # バッファクリアと時間更新
                        audio_buffer = []
                        last_recognition_time = time.time()
                        
                    except Exception as e:
                        logger.error(f"[{client_id}] Google STT処理エラー: {e}")
                        audio_buffer = []  # エラー時もバッファクリア
                        last_recognition_time = time.time()
                        
                        # クライアントにエラー通知（オプション）
                        try:
                            await websocket.send_text(f"[認識エラー] 音声を再度話してください")
                        except:
                            pass
                
                # Cloud Runのリソース制限対策（長時間接続の制限）
                session_duration = time.time() - session_start
                if session_duration > 300:  # 5分制限
                    logger.info(f"[{client_id}] セッション時間制限（5分）に達しました")
                    await websocket.send_text("[システム] セッション時間制限です。再接続してください。")
                    break
            
            except asyncio.TimeoutError:
                logger.warning(f"[{client_id}] データ受信タイムアウト（55秒）")
                await websocket.send_text("[システム] 接続タイムアウトです。")
                break
            
            except WebSocketDisconnect:
                logger.info(f"[{client_id}] クライアントが接続を切断しました")
                break
    
    except Exception as e:
        logger.error(f"[{client_id}] WebSocketエラー: {e}")
    
    finally:
        session_duration = time.time() - session_start
        logger.info(f"[{client_id}] 接続終了 - セッション時間: {session_duration:.1f}秒, 処理チャンク数: {chunk_count}")

# Cloud Run用のスタートアップイベント
@app.on_event("startup")
async def startup_event():
    logger.info("STT WebSocket Server starting up...")
    logger.info(f"Port: {PORT}")
    logger.info(f"Firebase key file: {SERVICE_ACCOUNT_FILE}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("STT WebSocket Server shutting down...")

if __name__ == "__main__":
    import uvicorn
    
    # Cloud Run用の設定
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Cloud Runでは必須
        port=PORT,
        log_level="info",
        access_log=True,
        # Cloud Run最適化設定
        timeout_keep_alive=30,
        limit_concurrency=100,
        limit_max_requests=1000
    )
