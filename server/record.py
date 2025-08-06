#!/usr/bin/env python3
"""
record.py - Firebase認証情報埋め込み版
"""

import os
from datetime import datetime
import requests
import json

def get_user_id():
    """serial.pyでハッシュ化されたユーザーID取得"""
    try:
        with open("userid.txt", "r") as f:
            user_id = f.read().strip()
        print(f"✅ デバイスID: {user_id}")
        return user_id
    except Exception as e:
        print(f"❌ ユーザーID取得エラー: {e}")
        print("💡 先に 'python serial.py' を実行してください")
        return None

def download_user_data(user_id, api_base_url="https://record-b-sucmscarza-an.a.run.app"):
    """Cloud Run APIサーバー経由でユーザーデータ取得"""
    url = f"{api_base_url}/record/{user_id}"
    try:
        print(f"🌐 APIからユーザーデータ取得中: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                user_data = result.get("data", {})
                print(f"✅ データ取得成功: {user_data.get('Name-f', '不明')}さん")
                return user_data
            else:
                print(f"❌ APIエラー: {result.get('message')}")
                return None
        else:
            print(f"❌ APIリクエスト失敗: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"❌ API取得エラー: {e}")
        return None

def download_medical_record(user_id, api_base_url="https://record-b-sucmscarza-an.a.run.app"):
    """Cloud Run APIサーバー経由でカルテデータ取得"""
    url = f"{api_base_url}/users/{user_id}"
    try:
        print(f"🌐 APIからカルテデータ取得中: {url}")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                medical_data = result.get("data", {})
                print(f"✅ カルテデータ取得成功")
                return medical_data
            else:
                print(f"❌ APIエラー: {result.get('message')}")
                return None
        else:
            print(f"❌ APIリクエスト失敗: {response.status_code} {response.text}")
            return None
    except Exception as e:
        print(f"❌ API取得エラー: {e}")
        return None

def save_json(data, filename):
    """指定ファイル名でdataディレクトリにJSON保存。既存ファイルがあれば削除"""
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, filename)
        print("削除対象パス:", file_path)
        print("削除前にファイル存在:", os.path.exists(file_path))
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print("🗑️ 既存の{}を削除しました".format(filename))
            except Exception as e:
                print(f"❌ 削除エラー: {e}")
        print("削除後にファイル存在:", os.path.exists(file_path))
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 {filename} 保存完了（生データ）")
    except Exception as e:
        print(f"❌ {filename} 保存エラー: {e}")

def main():
    user_id = get_user_id()
    if not user_id:
        return
    user_data = download_user_data(user_id)
    if user_data:
        save_json(user_data, "user_profile.json")
        print(f"✅ {user_data.get('Name-f', 'ユーザー')}さんの情報を更新完了")
    medical_data = download_medical_record(user_id)
    if medical_data:
        save_json(medical_data, "medical_record.json")
        print(f"✅ カルテデータの保存完了")

if __name__ == "__main__":
    main()