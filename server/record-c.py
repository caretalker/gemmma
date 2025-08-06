#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
record-c.py
RAG用文書生成システム
C:\CARE_TALKER\caretalker_jikkisyori\data\内のJSONファイルを統合してテキスト化
"""

import json
import os
import glob
from typing import Dict, List, Any
from datetime import datetime

class RecordCompiler:
    def __init__(self, data_dir: str = None):
        """
        RAG用文書生成システムの初期化
        
        Args:
            data_dir: データディレクトリのパス（デフォルト: ../data）
        """
        if data_dir is None:
            # 現在のファイルの位置から相対パスでdataディレクトリを指定
            current_dir = os.path.dirname(__file__)
            self.data_dir = os.path.join(current_dir, 'data')
        else:
            self.data_dir = data_dir
            
        print(f"データディレクトリ: {self.data_dir}")
    
    def load_json_files(self) -> Dict[str, Any]:
        """
        dataディレクトリ内のすべてのJSONファイルを読み込み
        
        Returns:
            Dict[str, Any]: ファイル名をキーとした辞書
        """
        json_data = {}
        
        # .jsonファイルを検索
        json_pattern = os.path.join(self.data_dir, "*.json")
        json_files = glob.glob(json_pattern)
        
        print(f"発見されたJSONファイル: {len(json_files)}件")
        
        for file_path in json_files:
            filename = os.path.basename(file_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    json_data[filename] = data
                    print(f"読み込み成功: {filename}")
            except Exception as e:
                print(f"読み込みエラー: {filename} - {e}")
        
        return json_data
    
    def compile_user_profile(self, user_data: Dict[str, Any]) -> str:
        """
        ユーザープロファイル情報をテキスト化
        
        Args:
            user_data: user_profile.jsonの内容
            
        Returns:
            str: テキスト化されたユーザー情報
        """
        text_parts = []
        
        # 基本情報
        name = user_data.get('name-f', '不明')
        age = user_data.get('age', '不明')
        text_parts.append(f"患者名: {name}さん（{age}歳）")
        
        # session_idを生成（名前と年齢から一意のセッションIDを作成）
        import hashlib
        session_string = f"{name}_{age}_{datetime.now().strftime('%Y%m%d')}"
        session_id = hashlib.md5(session_string.encode('utf-8')).hexdigest()[:16]
        # session_idはヘッダーに表示するので、ここでは追加しない
        
        # その他の情報があれば追加
        for key, value in user_data.items():
            if key not in ['name-f', 'age']:
                text_parts.append(f"{key}: {value}")
        
        return " / ".join(text_parts)
    
    def compile_medical_record(self, medical_data: Dict[str, Any]) -> str:
        """
        医療記録情報をテキスト化
        
        Args:
            medical_data: medical_record.jsonの内容
            
        Returns:
            str: テキスト化された医療情報
        """
        text_parts = []
        
        # user_idがある場合は追加
        user_id = medical_data.get('user_id', '')
        if user_id:
            text_parts.append(f"user_id: {user_id}")
        
        # 日付
        date = medical_data.get('date', '日付不明')
        text_parts.append(f"記録日: {date}")
        
        # 概要
        summary = medical_data.get('summary', '')
        if summary:
            text_parts.append(f"概要: {summary}")
        
        # バイタルサイン
        vitals = medical_data.get('vitals', {})
        if vitals:
            vital_texts = []
            if 'blood_pressure' in vitals:
                vital_texts.append(f"血圧: {vitals['blood_pressure']}")
            if 'pulse' in vitals:
                vital_texts.append(f"脈拍: {vitals['pulse']}bpm")
            if 'temperature' in vitals:
                vital_texts.append(f"体温: {vitals['temperature']}℃")
            
            if vital_texts:
                text_parts.append(f"バイタルサイン - {', '.join(vital_texts)}")
        
        # 服薬情報
        medications = medical_data.get('medications', [])
        if medications:
            med_text = "服薬中: " + ", ".join(medications)
            text_parts.append(med_text)
        
        # 備考
        notes = medical_data.get('notes', '')
        if notes:
            text_parts.append(f"備考: {notes}")
        
        return " / ".join(text_parts)
    
    def extract_session_id_from_rag_text(self, rag_text: str) -> str:
        """
        RAGテキストからsession_idを抽出
        
        Args:
            rag_text: 生成されたRAGテキスト
            
        Returns:
            str: 抽出されたsession_id（見つからない場合は空文字列）
        """
        import re
        
        # session_idパターンを検索（ヘッダー部分から）
        pattern = r'【session_ID】([a-f0-9]{16})'
        match = re.search(pattern, rag_text)
        
        if match:
            return match.group(1)
            
        return ""
    
    def get_user_session_info(self) -> Dict[str, str]:
        """
        現在のユーザーのセッション情報を取得
        
        Returns:
            Dict[str, str]: session_id, name, age を含む辞書
        """
        rag_text = self.generate_rag_text()
        session_id = self.extract_session_id_from_rag_text(rag_text)
        
        # ユーザープロファイルから名前と年齢を取得
        json_data = self.load_json_files()
        user_profile = json_data.get('user_profile.json', {})
        
        return {
            'session_id': session_id,
            'name': user_profile.get('name-f', '不明'),
            'age': str(user_profile.get('age', '不明'))
        }
    
    def compile_generic_json(self, filename: str, data: Dict[str, Any]) -> str:
        """
        汎用的なJSON情報をテキスト化
        
        Args:
            filename: ファイル名
            data: JSONデータ
            
        Returns:
            str: テキスト化された情報
        """
        text_parts = [f"ファイル: {filename}"]
        
        def flatten_dict(d: Dict[str, Any], prefix: str = "") -> List[str]:
            """辞書を再帰的にフラット化してテキスト化"""
            parts = []
            for key, value in d.items():
                full_key = f"{prefix}{key}" if prefix else key
                
                if isinstance(value, dict):
                    parts.extend(flatten_dict(value, f"{full_key}."))
                elif isinstance(value, list):
                    if value:  # 空でない場合
                        list_text = ", ".join(str(item) for item in value)
                        parts.append(f"{full_key}: {list_text}")
                else:
                    parts.append(f"{full_key}: {value}")
            
            return parts
        
        text_parts.extend(flatten_dict(data))
        return " / ".join(text_parts)
    
    def generate_rag_text(self) -> str:
        """
        すべてのJSONファイルを統合してRAG用テキストを生成
        
        Returns:
            str: RAG用の統合テキスト
        """
        # JSONファイルを読み込み
        json_data = self.load_json_files()
        
        if not json_data:
            return "利用可能なデータがありません。"
        
        text_sections = []
        session_id = ""
        
        # 各ファイルを適切にテキスト化し、session_idを抽出
        for filename, data in json_data.items():
            if filename == 'user_profile.json':
                # ユーザープロファイルからsession_idを直接生成
                name = data.get('name-f', '不明')
                age = data.get('age', '不明')
                import hashlib
                session_string = f"{name}_{age}_{datetime.now().strftime('%Y%m%d')}"
                session_id = hashlib.md5(session_string.encode('utf-8')).hexdigest()[:16]
                
                section = self.compile_user_profile(data)
                text_sections.append(f"【ユーザー情報】{section}")
                
            elif filename == 'medical_record.json':
                section = self.compile_medical_record(data)
                text_sections.append(f"【医療記録】{section}")
                
            else:
                # その他のJSONファイル
                section = self.compile_generic_json(filename, data)
                text_sections.append(f"【その他情報】{section}")
        
        # 統合テキストを生成
        rag_text = "\n\n".join(text_sections)
        
        # タイムスタンプとsession_idを追加
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"【CareTalker データ統合情報】生成日時: {timestamp}\n"
        if session_id:
            header += f"【session_ID】{session_id}\n\n"
        else:
            header += "\n"
        
        return header + rag_text
    
    def save_rag_text(self, output_path: str = None) -> str:
        """
        RAG用テキストを生成してファイルに保存
        
        Args:
            output_path: 出力ファイルパス（デフォルト: ../data/rag_text.txt）
            
        Returns:
            str: 生成されたRAG用テキスト
        """
        rag_text = self.generate_rag_text()
        
        if output_path is None:
            output_path = os.path.join(self.data_dir, "rag_text.txt")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rag_text)
            print(f"RAG用テキストを保存しました: {output_path}")
        except Exception as e:
            print(f"保存エラー: {e}")
        
        return rag_text
    

def main():
    """メイン関数"""
    print("CareTalker RAG文書生成システム")
    print("=" * 50)
    
    # RecordCompilerインスタンス作成
    compiler = RecordCompiler()
    
    # RAG用テキスト生成と保存
    rag_text = compiler.save_rag_text()
    
    print("\n生成されたRAG用テキスト:")
    print("-" * 50)
    print(rag_text)
    
    print("\nセッション情報:")
    print("-" * 30)
    
    # セッション情報テスト
    session_info = compiler.get_user_session_info()
    print(f"セッションID: {session_info['session_id']}")
    print(f"患者名: {session_info['name']}")
    print(f"年齢: {session_info['age']}")

if __name__ == "__main__":
    main()