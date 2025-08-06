import hashlib

def getserial():
    # /proc/cpuinfo ファイルからシリアル番号を取得
    cpuserial = "0000000000000000"
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line[0:6] == 'Serial':
                    cpuserial = line[10:26]
    except:
        cpuserial = "ERROR000000000"
    return cpuserial

def hash_serial(serial):
    # SHA-256でハッシュ化して16進文字列に変換
    hashed = hashlib.sha256(serial.encode()).hexdigest()
    return hashed

def get_user_id():
    """
    ユーザーIDをファイルから取得
    """
    with open("userid.txt") as f:
        return f.read().strip()

if __name__ == "__main__":
    print(get_user_id())