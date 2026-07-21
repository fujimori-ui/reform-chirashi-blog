#!/usr/bin/env python3
"""site_ai/ の中身(AI事務員さんページ)をエックスサーバーの jibulabo.jp/ai/ へFTPSでアップロードする。

環境変数: FTP_HOST / FTP_USER / FTP_PASSWORD / FTP_TARGET_DIR (例: /jibulabo.jp/public_html/ai)
"""

import os
from ftplib import FTP_TLS, error_perm

HERE = os.path.dirname(os.path.abspath(__file__))
# LOCAL_DIR環境変数で対象フォルダを切り替えられる(既定=site_ai、トップページはsite_top)
LOCAL_DIR = os.path.join(HERE, os.environ.get("LOCAL_DIR", "site_ai"))


def ensure_dir(ftp, path):
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            ftp.mkd(cur)
        except error_perm:
            pass  # すでにある


def connect(host, user, password, tries=3):
    """接続がタイムアウトすることがあるので、少し待ってやり直す。"""
    import time
    for i in range(tries):
        try:
            ftp = FTP_TLS(host, timeout=60)
            ftp.login(user, password)
            ftp.prot_p()
            return ftp
        except OSError as e:
            if i == tries - 1:
                raise
            print(f"接続に失敗({e})。30秒待ってやり直します({i + 2}/{tries})")
            time.sleep(30)


def main():
    host = os.environ["FTP_HOST"]
    user = os.environ["FTP_USER"]
    password = os.environ["FTP_PASSWORD"]
    target = os.environ["FTP_TARGET_DIR"].rstrip("/")

    ftp = connect(host, user, password)
    ensure_dir(ftp, target)

    count = 0
    for name in sorted(os.listdir(LOCAL_DIR)):
        local = os.path.join(LOCAL_DIR, name)
        if not os.path.isfile(local):
            continue
        with open(local, "rb") as f:
            ftp.storbinary(f"STOR {target}/{name}", f)
        print(f"アップロードしました: {target}/{name}")
        count += 1
    ftp.quit()
    print(f"完了: {count}ファイル")


if __name__ == "__main__":
    main()
