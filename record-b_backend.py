import os
from fastapi import FastAPI, HTTPException
from typing import Any
import firebase_admin
from firebase_admin import credentials, firestore, storage
import json

# サービスアカウントキーのファイル名を固定
FIREBASE_KEY_FILE = 'firebase-key.json'

if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_KEY_FILE)
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.environ.get('FIREBASE_STORAGE_BUCKET', 'caretalker-b8557.firebasestorage.app')
    })
db = firestore.client()
bucket = storage.bucket()

app = FastAPI()

@app.get("/record/{user_id}")
def get_user_profile(user_id: str) -> Any:
    """Firestoreからユーザープロファイル取得"""
    doc_ref = db.collection("record").document(user_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="ユーザープロファイルが見つかりません")
    user_data = doc.to_dict()
    print(f"✅ ユーザープロファイル取得成功: {user_id}")
    return {
        "status": "success",
        "message": "ユーザープロファイル取得成功",
        "data": user_data
    }

@app.get("/users/{user_id}")
def get_user_medical_record(user_id: str) -> Any:
    """Firebase Storageからユーザーカルテ（JSON）取得"""
    blob = bucket.blob(f"users/{user_id}/medical_record.json")
    print(f"Storageから取得しようとしているパス: users/{user_id}/medical_record.json")
    if not blob.exists():
        print("❌ Storage上にファイルが存在しません")
        raise HTTPException(status_code=404, detail="ユーザーカルテが見つかりません")
    json_content = blob.download_as_text()
    try:
        data = json.loads(json_content)
    except Exception:
        raise HTTPException(status_code=500, detail="カルテJSONのパースに失敗しました")
    print(f"✅ ユーザーカルテ取得成功: {user_id}")
    return {
        "status": "success",
        "message": "ユーザーカルテ取得成功",
        "data": data
    } 
