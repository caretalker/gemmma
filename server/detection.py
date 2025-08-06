#!/usr/bin/env python3
"""
detection.py - 人検知専用モジュール（改良版）
一度検知したら終了してstandby.pyを起動
"""

import cv2
import time
import subprocess
import sys
from datetime import datetime

class PersonDetector:
    """人検知クラス（一回検知で終了版）"""
    
    def __init__(self, camera_id=0):
        """初期化"""
        self.camera_id = camera_id
        self.camera = None
        
        # 連続検知確認用
        self.detection_buffer = []
        self.buffer_size = 5
        self.required_detections = 3
        
        # OpenCV人検知用カスケード分類器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.body_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_fullbody.xml'
        )
        
        print("🔍 PersonDetector 初期化完了（一回検知終了版）")
    
    def initialize_camera(self):
        """カメラ初期化"""
        try:
            self.camera = cv2.VideoCapture(self.camera_id)
            if not self.camera.isOpened():
                print("❌ カメラ接続エラー")
                return False
            
            # カメラ設定
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            print("✅ カメラ初期化完了")
            return True
            
        except Exception as e:
            print(f"❌ カメラ初期化エラー: {e}")
            return False
    
    def detect_person(self, frame):
        """フレームから人を検知"""
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 顔検知（厳しい条件）
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.2,
                minNeighbors=8,
                minSize=(60, 60),
                maxSize=(300, 300),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            # 人体検知（厳しい条件）
            bodies = self.body_cascade.detectMultiScale(
                gray,
                scaleFactor=1.3,
                minNeighbors=6,
                minSize=(80, 120),
                maxSize=(400, 600),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            valid_faces = len(faces)
            valid_bodies = len(bodies)
            
            if valid_faces > 0 or valid_bodies > 0:
                confidence_score = valid_faces * 2 + valid_bodies
                if confidence_score >= 2:
                    print(f"👤 人検知（信頼度:{confidence_score}): 顔={valid_faces}, 体={valid_bodies}")
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 人検知エラー: {e}")
            return False
    
    def wait_for_person(self):
        """人を待機（一度検知したら終了）"""
        if not self.initialize_camera():
            return False
        
        print("🔍 人検知待機開始...")
        print("👤 ユーザーが通りかかるのをお待ちしています...")
        
        try:
            while True:
                ret, frame = self.camera.read()
                if not ret:
                    print("❌ カメラフレーム取得失敗")
                    time.sleep(0.1)
                    continue
                
                # 人検知
                person_found = self.detect_person(frame)
                
                # 検知バッファ更新
                self.detection_buffer.append(person_found)
                
                # バッファサイズ維持
                if len(self.detection_buffer) > self.buffer_size:
                    self.detection_buffer.pop(0)
                
                # 連続検知判定
                if len(self.detection_buffer) >= self.buffer_size:
                    recent_detections = sum(self.detection_buffer)
                    
                    if recent_detections >= self.required_detections:
                        print(f"✅ 人検知確定！({recent_detections}/{self.buffer_size}フレーム)")
                        print(f"🎯 {datetime.now().strftime('%H:%M:%S')} - ユーザー検知完了")
                        self.cleanup()
                        return True
                
                time.sleep(0.1)  # CPU負荷軽減
                
        except KeyboardInterrupt:
            print("\n🛑 検知中断")
            self.cleanup()
            return False
        except Exception as e:
            print(f"❌ 検知エラー: {e}")
            self.cleanup()
            return False
    
    def cleanup(self):
        """リソース解放"""
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
        print("🔍 PersonDetector 終了")

def launch_standby():
    """standby.py を起動"""
    try:
        print("🚀 standby.py を起動中...")
        
        # standby.py を実行
        result = subprocess.run([
            sys.executable, "standby.py"
        ], capture_output=True, text=True)
        
        print("✅ standby.py 実行完了")
        print("📋 実行結果:")
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("⚠️ エラー出力:", result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ standby.py 起動エラー: {e}")
        return False

def main():
    """メイン処理 - 検知→起動のループ"""
    print("🎯 CareTalker 人検知システム開始")
    print("🔄 検知→会話→検知のサイクルを開始します")
    
    while True:
        try:
            # 人検知開始
            detector = PersonDetector()
            person_detected = detector.wait_for_person()
            
            if person_detected:
                # standby.py を起動
                standby_success = launch_standby()
                
                if standby_success:
                    print("✅ 会話セッション完了")
                else:
                    print("❌ 会話セッション異常終了")
                
                # 少し待機してから次の検知サイクル
                print("⏳ 5秒後に次の検知サイクルを開始...")
                time.sleep(5)
                
            else:
                print("❌ 人検知失敗 - 3秒後に再試行")
                time.sleep(3)
                
        except KeyboardInterrupt:
            print("\n🛑 システム終了")
            break
        except Exception as e:
            print(f"❌ システムエラー: {e}")
            print("⏳ 5秒後に再試行...")
            time.sleep(5)

if __name__ == "__main__":
    main()