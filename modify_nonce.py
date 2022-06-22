import sqlite3
import os
import sys

db = sqlite3.connect("./local_data.db")
cur = db.cursor()
# database check
try:
    sql = """select * from last_txn where name = 'nonce'"""
    cur.execute(sql)
except:
    print("まず、auction_bot.pyを起動してください")
    os.system("pause")
    sys.exit()
# nonce check
nonce = list(cur)[0][2]
print("前回のbot取引のnonceは" + str(nonce) + "です")

# nonce setting
sql = """update last_txn set data = ? where name = 'nonce'"""
print("最新トランザクションのnonceを入力してください")
while 1:
    try:
        nonce = int(input())
        cur.execute(sql, (nonce,))
        db.commit()
        break
    except:
        print("数字で入力してください")
        continue

print("nonceは" + str(nonce) + "に設定されました")
os.system("pause")