#!/usr/bin/env python3
"""jibulabo.jp の .htaccess に「http → https 自動転送」を入れる(1回きりの作業用)。

やること:
 1. サーバー上の /jibulabo.jp/public_html/.htaccess を取得(無ければ空として扱う)
 2. すでに転送ルールが入っていれば何もしない
 3. 元の内容を .htaccess.bak_YYYYMMDD としてサーバーに控える
 4. 転送ルールを先頭に足した .htaccess をアップロードする

環境変数: FTP_HOST / FTP_USER / FTP_PASSWORD / FTP_TARGET_DIR (例: /jibulabo.jp/public_html)
"""

import io
import os
from datetime import date
from ftplib import FTP_TLS, error_perm

MARK = "# --- https redirect (added by set_https_redirect.py) ---"
RULES = f"""{MARK}
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{{HTTPS}} !on
RewriteRule ^(.*)$ https://%{{HTTP_HOST}}%{{REQUEST_URI}} [R=301,L]
</IfModule>
# --- end https redirect ---

"""


def connect(host, user, password, tries=3):
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


def download(ftp, path):
    buf = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {path}", buf.write)
    except error_perm as e:
        print(f"{path} は取得できませんでした(無い場合はこれで正常): {e}")
        return None
    return buf.getvalue()


def upload(ftp, path, data: bytes):
    ftp.storbinary(f"STOR {path}", io.BytesIO(data))
    print(f"アップロードしました: {path} ({len(data)} bytes)")


def main():
    host = os.environ["FTP_HOST"]
    user = os.environ["FTP_USER"]
    password = os.environ["FTP_PASSWORD"]
    target = os.environ["FTP_TARGET_DIR"].rstrip("/")
    path = f"{target}/.htaccess"

    ftp = connect(host, user, password)

    original = download(ftp, path)
    if original is None:
        original = b""
    text = original.decode("utf-8", errors="replace")
    print("===== 現在の .htaccess =====")
    print(text if text.strip() else "(空、または未作成)")
    print("============================")

    if MARK in text:
        print("転送ルールはすでに入っています。何もしません。")
        ftp.quit()
        return

    if original:
        bak = f"{target}/.htaccess.bak_{date.today():%Y%m%d}"
        upload(ftp, bak, original)
        print(f"控えを作りました: {bak}")

    new_text = RULES + text
    upload(ftp, path, new_text.encode("utf-8"))
    print("===== 新しい .htaccess =====")
    print(new_text)
    print("============================")
    ftp.quit()
    print("完了")


if __name__ == "__main__":
    main()
