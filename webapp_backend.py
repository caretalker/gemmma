from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore, storage
import os
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app)  # CORSを有効化

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase Admin SDKの初期化
try:
    cred = credentials.Certificate('firebase-key.json')
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'caretalker-b8557.firebasestorage.app'  # 新しいバケット名に更新
    })
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization error: {str(e)}")
    raise

# Firestoreクライアントの取得
db = firestore.client()

@app.route('/login', methods=['POST'])
def login():
    try:
        # リクエストからデータを取得
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'リクエストデータが不正です'
            }), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # 入力値の検証
        if not email or not password:
            return jsonify({
                'success': False,
                'message': 'メールアドレスとパスワードを入力してください'
            }), 400
        
        # メールアドレスの形式チェック
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'message': 'メールアドレスの形式が正しくありません'
            }), 400
        
        logger.info(f"Login attempt for email: {email}")
        
        # Firestoreからクライアントデータを取得
        clients_ref = db.collection('client')
        clients = clients_ref.stream()
        
        # メールアドレスとパスワードをチェック
        for client in clients:
            client_data = client.to_dict()
            client_serial = client.id
            
            # データベースのメールアドレスも正規化して比較
            db_email = client_data.get('family', '').strip().lower()
            db_password = client_data.get('family_pass', '')
            
            if db_email == email and db_password == password:
                logger.info(f"Login successful for serial: {client_serial}")
                # ログイン成功
                return jsonify({
                    'success': True,
                    'message': 'ログインに成功しました',
                    'serial': client_serial
                }), 200
        
        logger.warning(f"Login failed for email: {email}")
        # ログイン失敗
        return jsonify({
            'success': False,
            'message': 'メールアドレスまたはパスワードが間違っています'
        }), 401
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'サーバーエラーが発生しました。しばらく時間をおいて再度お試しください。'
        }), 500

@app.route('/profile/<client_id>', methods=['GET'])
def get_profile(client_id):
    try:
        logger.info(f"Getting profile for client_id: {client_id}")
        
        # Firestoreからプロフィールデータを取得
        doc_ref = db.collection('record').document(client_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return jsonify({
                'success': False,
                'message': 'プロフィールデータが見つかりません'
            }), 404
        
        profile_data = doc.to_dict()
        
        # 性別の変換（int → 文字列）
        sex_map = {1: '男性', 2: '女性', 3: 'その他'}
        sex_value = profile_data.get('sex', 1)
        
        # レスポンス用にデータを整形
        formatted_data = {
            'lastName': profile_data.get('Name-l', ''),
            'firstName': profile_data.get('Name-f', ''),
            'lastNameKana': profile_data.get('Name-l-f', ''),
            'firstNameKana': profile_data.get('Name-f-f', ''),
            'age': profile_data.get('Age', 0),
            'gender': sex_map.get(sex_value, '男性'),
            'address': profile_data.get('adress', ''),
            'familyAddress': profile_data.get('family-adress', ''),
            'emergency': profile_data.get('family-telephonenumber', ''),
            'medication': profile_data.get('medicine', ''),
            'medicationFreq': profile_data.get('frequency', ''),
            'illness': profile_data.get('disease', ''),
            'allergy': profile_data.get('allergy', ''),
            'hobby': profile_data.get('hobby', ''),
            'destination': profile_data.get('main', ''),
            'trashDays': profile_data.get('garbage', ''),
            'dayServiceFreq': profile_data.get('service', ''),
            'otherInfo': profile_data.get('others', '')
        }
        
        logger.info(f"Profile retrieved successfully for client_id: {client_id}")
        return jsonify({
            'success': True,
            'data': formatted_data
        }), 200
        
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'プロフィール取得中にエラーが発生しました'
        }), 500

@app.route('/profile/<client_id>', methods=['PUT'])
def update_profile(client_id):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'リクエストデータが不正です'
            }), 400
        
        logger.info(f"Updating profile for client_id: {client_id}")
        
        # 性別の変換（文字列 → int）
        sex_map = {'男性': 1, '女性': 2, 'その他': 3}
        
        # Firestore用にデータを変換
        firestore_data = {
            'Name-l': data.get('lastName', ''),
            'Name-f': data.get('firstName', ''),
            'Name-l-f': data.get('lastNameKana', ''),
            'Name-f-f': data.get('firstNameKana', ''),
            'Age': int(data.get('age', 0)),
            'sex': sex_map.get(data.get('gender', '男性'), 1),
            'adress': data.get('address', ''),
            'family-adress': data.get('familyAddress', ''),
            'family-telephonenumber': data.get('emergency', ''),
            'medicine': data.get('medication', ''),
            'frequency': data.get('medicationFreq', ''),
            'disease': data.get('illness', ''),
            'allergy': data.get('allergy', ''),
            'hobby': data.get('hobby', ''),
            'main': data.get('destination', ''),
            'garbage': data.get('trashDays', ''),
            'service': data.get('dayServiceFreq', ''),
            'others': data.get('otherInfo', '')
        }
        
        # Firestoreでプロフィールを更新
        doc_ref = db.collection('record').document(client_id)
        doc_ref.set(firestore_data, merge=True)
        
        logger.info(f"Profile updated successfully for client_id: {client_id}")
        return jsonify({
            'success': True,
            'message': 'プロフィールが正常に更新されました'
        }), 200
        
    except Exception as e:
        logger.error(f"Update profile error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'プロフィール更新中にエラーが発生しました'
        }), 500

@app.route('/report/<client_id>/<year_month>', methods=['GET'])
def get_report(client_id, year_month):
    try:
        logger.info(f"Getting report for client_id: {client_id}, year_month: {year_month}")
        
        # 年月の形式チェック (YYYY-MM)
        try:
            # 年月をパースして形式を確認
            parsed_date = datetime.strptime(year_month, '%Y-%m')
            logger.info(f"Parsed date: {parsed_date}")
        except ValueError as ve:
            logger.error(f"Date parsing error: {str(ve)}")
            return jsonify({
                'success': False,
                'message': '日付の形式が正しくありません (YYYY-MM形式で入力してください)'
            }), 400
        
        # Firebase Storageからファイルを取得
        try:
            bucket = storage.bucket()
            file_path = f"users/{client_id}/report/{year_month}.txt"
            logger.info(f"Attempting to retrieve file: {file_path}")
            logger.info(f"Using bucket: {bucket.name}")
            
            blob = bucket.blob(file_path)
            logger.info(f"Blob created: {blob.name}")
            
            # ファイルが存在するかチェック
            if not blob.exists():
                logger.info(f"Report not found: {file_path}")
                # デバッグ: バケット内のファイル一覧を取得
                try:
                    blobs = bucket.list_blobs(prefix=f"users/{client_id}/")
                    existing_files = [b.name for b in blobs]
                    logger.info(f"Existing files for client {client_id}: {existing_files}")
                except Exception as list_error:
                    logger.error(f"Error listing files: {str(list_error)}")
                
                return jsonify({
                    'success': False,
                    'message': 'レポートが見つかりません',
                    'not_found': True
                }), 404
            
            # ファイルの内容を取得
            content = blob.download_as_text(encoding='utf-8')
            
            logger.info(f"Report retrieved successfully: {file_path}")
            return jsonify({
                'success': True,
                'content': content,
                'file_path': file_path
            }), 200
            
        except Exception as storage_error:
            logger.error(f"Storage error: {str(storage_error)}")
            # Storageエラーの場合もファイルが見つからないとして処理
            return jsonify({
                'success': False,
                'message': 'レポートが見つかりません',
                'not_found': True
            }), 404
        
    except Exception as e:
        logger.error(f"Get report error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'レポート取得中にエラーが発生しました'
        }), 500

@app.route('/conversation/<client_id>/<date>', methods=['GET'])
def get_conversation(client_id, date):
    try:
        logger.info(f"Getting conversation for client_id: {client_id}, date: {date}")
        
        # 日付の形式チェック (YYYY-MM-DD)
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
            year = parsed_date.year
            month = str(parsed_date.month).zfill(2)
            day = str(parsed_date.day).zfill(2)
            logger.info(f"Parsed date: {year}-{month}-{day}")
        except ValueError as ve:
            logger.error(f"Date parsing error: {str(ve)}")
            return jsonify({
                'success': False,
                'message': '日付の形式が正しくありません (YYYY-MM-DD形式で入力してください)'
            }), 400
        
        # Firebase Storageからファイルを取得
        try:
            bucket = storage.bucket()
            file_path = f"users/{client_id}/conversations/{year}-{month}/{day}.txt"
            logger.info(f"Attempting to retrieve file: {file_path}")
            
            blob = bucket.blob(file_path)
            
            # ファイルが存在するかチェック
            if not blob.exists():
                logger.info(f"Conversation not found: {file_path}")
                return jsonify({
                    'success': False,
                    'message': 'その日の会話記録が見つかりません',
                    'not_found': True
                }), 404
            
            # ファイルの内容を取得
            content = blob.download_as_text(encoding='utf-8')
            
            logger.info(f"Conversation retrieved successfully: {file_path}")
            return jsonify({
                'success': True,
                'content': content,
                'file_path': file_path,
                'date': date
            }), 200
            
        except Exception as storage_error:
            logger.error(f"Storage error: {str(storage_error)}")
            return jsonify({
                'success': False,
                'message': 'その日の会話記録が見つかりません',
                'not_found': True
            }), 404
        
    except Exception as e:
        logger.error(f"Get conversation error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '会話記録取得中にエラーが発生しました'
        }), 500

@app.route('/conversation-availability/<client_id>/<year_month>', methods=['GET'])
def get_conversation_availability(client_id, year_month):
    try:
        logger.info(f"Getting conversation availability for client_id: {client_id}, year_month: {year_month}")
        
        # 年月の形式チェック (YYYY-MM)
        try:
            parsed_date = datetime.strptime(year_month, '%Y-%m')
            year = parsed_date.year
            month = str(parsed_date.month).zfill(2)
            logger.info(f"Parsed year-month: {year}-{month}")
        except ValueError as ve:
            logger.error(f"Date parsing error: {str(ve)}")
            return jsonify({
                'success': False,
                'message': '日付の形式が正しくありません (YYYY-MM形式で入力してください)'
            }), 400
        
        # Firebase Storageからその月のファイル一覧を取得
        try:
            bucket = storage.bucket()
            prefix = f"users/{client_id}/conversations/{year}-{month}/"
            logger.info(f"Checking availability for prefix: {prefix}")
            
            # その月のファイル一覧を取得
            blobs = bucket.list_blobs(prefix=prefix)
            available_days = []
            
            for blob in blobs:
                # ファイル名から日付を抽出 (DD.txt)
                filename = blob.name.split('/')[-1]  # 最後の部分を取得
                if filename.endswith('.txt') and len(filename) == 6:  # DD.txt形式
                    day = filename[:2]
                    if day.isdigit():
                        available_days.append(int(day))
            
            logger.info(f"Available days for {year}-{month}: {available_days}")
            return jsonify({
                'success': True,
                'available_days': sorted(available_days),
                'year_month': year_month
            }), 200
            
        except Exception as storage_error:
            logger.error(f"Storage error: {str(storage_error)}")
            return jsonify({
                'success': True,
                'available_days': [],
                'year_month': year_month
            }), 200
        
    except Exception as e:
        logger.error(f"Get conversation availability error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '会話記録の可用性確認中にエラーが発生しました'
        }), 500

@app.route('/daily-record/<client_id>/<date>', methods=['GET'])
def get_daily_record(client_id, date):
    try:
        logger.info(f"Getting daily record for client_id: {client_id}, date: {date}")
        
        # 日付の形式チェック (YYYY-MM-DD)
        try:
            parsed_date = datetime.strptime(date, '%Y-%m-%d')
            year = parsed_date.year
            month = str(parsed_date.month).zfill(2)
            day = str(parsed_date.day).zfill(2)
            logger.info(f"Parsed date: {year}-{month}-{day}")
        except ValueError as ve:
            logger.error(f"Date parsing error: {str(ve)}")
            return jsonify({
                'success': False,
                'message': '日付の形式が正しくありません (YYYY-MM-DD形式で入力してください)'
            }), 400
        
        # Firebase Storageからファイルを取得
        try:
            bucket = storage.bucket()
            file_path = f"users/{client_id}/record/{year}-{month}/{day}.txt"
            logger.info(f"Attempting to retrieve file: {file_path}")
            logger.info(f"Using bucket: {bucket.name}")
            
            blob = bucket.blob(file_path)
            logger.info(f"Blob created: {blob.name}")
            
            # ファイルが存在するかチェック
            if not blob.exists():
                logger.info(f"Daily record not found: {file_path}")
                return jsonify({
                    'success': False,
                    'message': 'その日の記録が見つかりません',
                    'not_found': True
                }), 404
            
            # ファイルの内容を取得
            content = blob.download_as_text(encoding='utf-8')
            
            logger.info(f"Daily record retrieved successfully: {file_path}")
            return jsonify({
                'success': True,
                'content': content,
                'file_path': file_path,
                'date': date
            }), 200
            
        except Exception as storage_error:
            logger.error(f"Storage error: {str(storage_error)}")
            # Storageエラーの場合もファイルが見つからないとして処理
            return jsonify({
                'success': False,
                'message': 'その日の記録が見つかりません',
                'not_found': True
            }), 404
        
    except Exception as e:
        logger.error(f"Get daily record error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '記録取得中にエラーが発生しました'
        }), 500

@app.route('/notifications/<client_id>', methods=['GET'])
def get_notifications(client_id):
    try:
        logger.info(f"Getting notifications for client_id: {client_id}")
        
        # Firebase Storageから通知ファイルを取得
        try:
            bucket = storage.bucket()
            file_path = f"users/{client_id}/notification/notifications.txt"
            logger.info(f"Attempting to retrieve file: {file_path}")
            
            blob = bucket.blob(file_path)
            
            # ファイルが存在するかチェック
            if not blob.exists():
                logger.info(f"Notifications file not found: {file_path}")
                return jsonify({
                    'success': True,
                    'notifications': []
                }), 200
            
            # ファイルの内容を取得
            content = blob.download_as_text(encoding='utf-8')
            
            # 通知をパース
            notifications = parse_notifications(content)
            
            logger.info(f"Notifications retrieved successfully: {len(notifications)} notifications")
            return jsonify({
                'success': True,
                'notifications': notifications
            }), 200
            
        except Exception as storage_error:
            logger.error(f"Storage error: {str(storage_error)}")
            return jsonify({
                'success': True,
                'notifications': []
            }), 200
        
    except Exception as e:
        logger.error(f"Get notifications error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '通知取得中にエラーが発生しました'
        }), 500

@app.route('/notifications/<client_id>/mark-read', methods=['PUT'])
def mark_notification_read(client_id):
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({
                'success': False,
                'message': '通知IDが指定されていません'
            }), 400
        
        logger.info(f"Marking notification as read for client_id: {client_id}, notification_id: {notification_id}")
        
        # Firebase Storageから通知ファイルを取得
        bucket = storage.bucket()
        file_path = f"users/{client_id}/notification/notifications.txt"
        blob = bucket.blob(file_path)
        
        if not blob.exists():
            return jsonify({
                'success': False,
                'message': '通知ファイルが見つかりません'
            }), 404
        
        # ファイルの内容を取得してパース
        content = blob.download_as_text(encoding='utf-8')
        notifications = parse_notifications(content)
        
        # 指定された通知を既読に変更
        updated = False
        for notification in notifications:
            if notification['id'] == notification_id:
                notification['status'] = 0  # 既読
                updated = True
                break
        
        if not updated:
            return jsonify({
                'success': False,
                'message': '指定された通知が見つかりません'
            }), 404
        
        # 更新された通知データを文字列に変換
        updated_content = format_notifications_to_text(notifications)
        
        # ファイルを更新
        blob.upload_from_string(updated_content, content_type='text/plain')
        
        logger.info(f"Notification marked as read successfully")
        return jsonify({
            'success': True,
            'message': '通知を既読にしました'
        }), 200
        
    except Exception as e:
        logger.error(f"Mark notification read error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '通知の既読処理中にエラーが発生しました'
        }), 500

@app.route('/notifications/<client_id>/test', methods=['POST'])
def create_test_notifications(client_id):
    """テスト用の通知を作成するエンドポイント"""
    try:
        logger.info(f"Creating test notifications for client_id: {client_id}")
        
        # テスト用の通知データ
        test_notifications = [
            {
                'datetime': '2025-08-04-1400',
                'title': '服薬時間のお知らせ',
                'status': 1,
                'message': '○○さんは14:00に薬を服用する予定です。'
            },
            {
                'datetime': '2025-08-04-0930',
                'title': '介護予定の変更',
                'status': 1,
                'message': '担当者が△△さんに変更されました。'
            },
            {
                'datetime': '2025-08-03-1200',
                'title': '服薬完了',
                'status': 0,
                'message': '○○さんは12:00の服薬が完了しました。'
            }
        ]
        
        # 通知テキストを生成
        blocks = []
        for notification in test_notifications:
            header = f"{notification['datetime']}***{notification['title']}***{notification['status']}"
            block = f"{header}\n{notification['message']}"
            blocks.append(block)
        
        content = '\n**********\n'.join(blocks) + '\n**********'
        
        # Firebase Storageに保存
        bucket = storage.bucket()
        file_path = f"users/{client_id}/notification/notifications.txt"
        blob = bucket.blob(file_path)
        blob.upload_from_string(content, content_type='text/plain')
        
        logger.info(f"Test notifications created successfully at: {file_path}")
        return jsonify({
            'success': True,
            'message': 'テスト通知を作成しました',
            'file_path': file_path,
            'content': content
        }), 200
        
    except Exception as e:
        logger.error(f"Create test notifications error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'テスト通知の作成中にエラーが発生しました'
        }), 500
@app.route('/notifications/<client_id>/delete', methods=['DELETE'])
def delete_notification(client_id):
    try:
        data = request.get_json()
        notification_id = data.get('notification_id')
        
        if not notification_id:
            return jsonify({
                'success': False,
                'message': '通知IDが指定されていません'
            }), 400
        
        logger.info(f"Deleting notification for client_id: {client_id}, notification_id: {notification_id}")
        
        # Firebase Storageから通知ファイルを取得
        bucket = storage.bucket()
        file_path = f"users/{client_id}/notification/notifications.txt"
        blob = bucket.blob(file_path)
        
        if not blob.exists():
            return jsonify({
                'success': False,
                'message': '通知ファイルが見つかりません'
            }), 404
        
        # ファイルの内容を取得してパース
        content = blob.download_as_text(encoding='utf-8')
        notifications = parse_notifications(content)
        
        # 指定された通知を削除
        original_count = len(notifications)
        notifications = [n for n in notifications if n['id'] != notification_id]
        
        if len(notifications) == original_count:
            return jsonify({
                'success': False,
                'message': '指定された通知が見つかりません'
            }), 404
        
        # 更新された通知データを文字列に変換
        updated_content = format_notifications_to_text(notifications)
        
        # ファイルを更新
        blob.upload_from_string(updated_content, content_type='text/plain')
        
        logger.info(f"Notification deleted successfully")
        return jsonify({
            'success': True,
            'message': '通知を削除しました'
        }), 200
        
    except Exception as e:
        logger.error(f"Delete notification error: {str(e)}")
        return jsonify({
            'success': False,
            'message': '通知の削除処理中にエラーが発生しました'
        }), 500

def parse_notifications(content):
    """通知ファイルの内容をパースして通知リストを返す"""
    logger.info(f"Parsing notifications content (length: {len(content) if content else 0})")
    logger.info(f"Content preview: {content[:200] if content else 'None'}...")
    
    notifications = []
    if not content or content.strip() == '':
        logger.info("No content to parse")
        return notifications
    
    # **********で区切られた通知を分割
    notification_blocks = content.split('**********')
    logger.info(f"Split into {len(notification_blocks)} blocks")
    
    for i, block in enumerate(notification_blocks):
        block = block.strip()
        logger.info(f"Processing block {i}: '{block[:100]}...' (length: {len(block)})")
        
        if not block:
            logger.info(f"Block {i} is empty, skipping")
            continue
        
        lines = block.split('\n')
        logger.info(f"Block {i} has {len(lines)} lines")
        
        if len(lines) < 1:
            logger.info(f"Block {i} has no lines, skipping")
            continue
        
        # 最初の行から日時、タイトル、ステータスを抽出
        header_line = lines[0].strip()
        logger.info(f"Header line: '{header_line}'")
        
        # 形式: YYYY-MM-DD-HH-MM***タイトル***ステータス
        if '***' not in header_line:
            logger.warning(f"No *** separator found in header line: {header_line}")
            continue
        
        parts = header_line.split('***')
        logger.info(f"Header parts: {parts}")
        
        if len(parts) < 3:
            logger.warning(f"Header doesn't have 3 parts: {parts}")
            continue
        
        datetime_str = parts[0]
        title = parts[1]
        status_str = parts[2]
        status = int(status_str) if status_str.isdigit() else 1
        
        logger.info(f"Parsed: datetime='{datetime_str}', title='{title}', status={status}")
        
        # メッセージ内容（2行目以降）
        message = '\n'.join(lines[1:]).strip()
        logger.info(f"Message: '{message[:50]}...'")
        
        # 日時をパース
        try:
            # YYYY-MM-DD-HHMM形式をパース（ハイフンなしの時刻部分）
            if len(datetime_str.split('-')) == 4:  # YYYY-MM-DD-HHMM
                date_part, time_part = datetime_str.rsplit('-', 1)
                date_obj = datetime.strptime(date_part, '%Y-%m-%d')
                
                # HHMM形式の時刻をパース
                if len(time_part) == 4 and time_part.isdigit():
                    hour = int(time_part[:2])
                    minute = int(time_part[2:])
                else:
                    logger.warning(f"Invalid time format: {time_part}")
                    continue
                    
            else:
                logger.warning(f"Invalid datetime format: {datetime_str}")
                continue
            
            notification_datetime = date_obj.replace(hour=hour, minute=minute)
            
            notification = {
                'id': datetime_str,  # ユニークIDとして日時文字列を使用
                'title': title,
                'message': message,
                'status': status,  # 1: 未読, 0: 既読
                'datetime': notification_datetime.isoformat(),
                'display_time': f"{hour:02d}:{minute:02d}"
            }
            
            logger.info(f"Successfully parsed notification: {notification}")
            notifications.append(notification)
            
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse notification datetime: {datetime_str}, error: {e}")
            continue
    
    # 日時の降順でソート（新しい順）
    notifications.sort(key=lambda x: x['datetime'], reverse=True)
    
    logger.info(f"Parsed {len(notifications)} notifications total")
    return notifications

def format_notifications_to_text(notifications):
    """通知リストをテキストファイル形式に変換"""
    if not notifications:
        return ""
    
    # 日時の降順でソート（新しい順）
    notifications.sort(key=lambda x: x['datetime'], reverse=True)
    
    blocks = []
    for notification in notifications:
        # 日時文字列を再構築
        datetime_obj = datetime.fromisoformat(notification['datetime'])
        datetime_str = f"{datetime_obj.strftime('%Y-%m-%d')}-{datetime_obj.strftime('%H%M')}"
        
        header = f"{datetime_str}***{notification['title']}***{notification['status']}"
        block = f"{header}\n{notification['message']}"
        blocks.append(block)
    
    return '\n**********\n'.join(blocks) + '\n**********'

@app.route('/debug/storage/<client_id>', methods=['GET'])
def debug_storage(client_id):
    """Firebase Storageの内容をデバッグするエンドポイント"""
    try:
        logger.info(f"Debug storage for client_id: {client_id}")
        
        bucket = storage.bucket()
        
        # 通知ファイルのパスをチェック
        notification_path = f"users/{client_id}/notification/notifications.txt"
        notification_blob = bucket.blob(notification_path)
        
        debug_info = {
            'client_id': client_id,
            'bucket_name': bucket.name,
            'notification_file': {
                'path': notification_path,
                'exists': notification_blob.exists(),
                'content': None
            },
            'user_files': []
        }
        
        # 通知ファイルが存在する場合、内容を取得
        if notification_blob.exists():
            try:
                content = notification_blob.download_as_text(encoding='utf-8')
                debug_info['notification_file']['content'] = content
                debug_info['notification_file']['content_length'] = len(content)
            except Exception as e:
                debug_info['notification_file']['error'] = str(e)
        
        # ユーザーディレクトリ内のファイル一覧を取得
        try:
            blobs = bucket.list_blobs(prefix=f"users/{client_id}/")
            debug_info['user_files'] = [blob.name for blob in blobs]
        except Exception as e:
            debug_info['user_files_error'] = str(e)
        
        return jsonify({
            'success': True,
            'debug_info': debug_info
        }), 200
        
    except Exception as e:
        logger.error(f"Debug storage error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'デバッグ中にエラーが発生しました: {str(e)}'
        }), 500

@app.route('/change-password/<client_id>', methods=['PUT'])
def change_password(client_id):
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'リクエストデータが不正です'
            }), 400
        
        old_password = data.get('oldPassword', '')
        new_password = data.get('newPassword', '')
        confirm_password = data.get('confirmPassword', '')
        
        # 入力値の検証
        if not old_password or not new_password or not confirm_password:
            return jsonify({
                'success': False,
                'message': 'すべてのフィールドを入力してください'
            }), 400
        
        # 新しいパスワードと確認パスワードの一致確認
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': '新しいパスワードと確認パスワードが一致しません'
            }), 400
        
        # パスワードの最小長チェック
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'パスワードは6文字以上で入力してください'
            }), 400
        
        logger.info(f"Password change attempt for client_id: {client_id}")
        
        # Firestoreからクライアントデータを取得
        client_ref = db.collection('client').document(client_id)
        client_doc = client_ref.get()
        
        if not client_doc.exists:
            return jsonify({
                'success': False,
                'message': 'ユーザーが見つかりません'
            }), 404
        
        client_data = client_doc.to_dict()
        current_password = client_data.get('family_pass', '')
        
        # 古いパスワードの確認
        if current_password != old_password:
            logger.warning(f"Invalid old password for client_id: {client_id}")
            return jsonify({
                'success': False,
                'message': '現在のパスワードが間違っています'
            }), 401
        
        # パスワードを更新
        client_ref.update({
            'family_pass': new_password
        })
        
        logger.info(f"Password updated successfully for client_id: {client_id}")
        return jsonify({
            'success': True,
            'message': 'パスワードが正常に変更されました'
        }), 200
        
    except Exception as e:
        logger.error(f"Change password error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'パスワード変更中にエラーが発生しました'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'OK',
        'message': 'ログインAPI サーバーは正常に稼働しています'
    }), 200

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'ログインAPI サーバーが稼働中です',
        'version': '1.0.0',
        'endpoints': {
            'login': '/login (POST)',
            'profile': '/profile/<client_id> (GET, PUT)',
            'report': '/report/<client_id>/<year_month> (GET)',
            'daily-record': '/daily-record/<client_id>/<date> (GET)',
            'conversation': '/conversation/<client_id>/<date> (GET)',
            'conversation-availability': '/conversation-availability/<client_id>/<year_month> (GET)',
            'notifications': '/notifications/<client_id> (GET)',
            'mark-notification-read': '/notifications/<client_id>/mark-read (PUT)',
            'delete-notification': '/notifications/<client_id>/delete (DELETE)',
            'change-password': '/change-password/<client_id> (PUT)',
            'health': '/health (GET)'
        }
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': '指定されたエンドポイントが見つかりません'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({
        'success': False,
        'message': '内部サーバーエラーが発生しました'
    }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
