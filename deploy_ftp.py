"""ビルド済みのブログ(_siteフォルダ)をエックスサーバーへFTPSでアップロードする。

使い方(GitHub Actionsから呼ばれる):
    python deploy_ftp.py

必要な環境変数:
    FTP_HOST      例: sv17104.xserver.jp
    FTP_USER      例: jibulabo
    FTP_PASSWORD  エックスサーバーのFTPパスワード(GitHubのSecretsに登録)
    FTP_DIR       アップロード先 例: /jibulabo.jp/public_html/blog

方式: _site の全ファイルを毎回上書きアップロードする(削除はしない)。
ブログは小さいので全量アップロードで十分速い。
"""
import os
import sys
from ftplib import FTP_TLS, error_perm

LOCAL_DIR = "_site"


def ensure_dir(ftps, path):
    """アップロード先のフォルダを(無ければ)作る。"""
    parts = [p for p in path.split("/") if p]
    cur = ""
    for p in parts:
        cur += "/" + p
        try:
            ftps.mkd(cur)
        except error_perm:
            pass  # 既にあればOK


def main():
    host = os.environ["FTP_HOST"]
    user = os.environ["FTP_USER"]
    password = os.environ["FTP_PASSWORD"]
    remote_root = os.environ["FTP_DIR"].rstrip("/")

    if not os.path.isdir(LOCAL_DIR):
        sys.exit(f"エラー: {LOCAL_DIR} がありません。先に jekyll build してください。")

    ftps = FTP_TLS(host, timeout=60)
    ftps.login(user, password)
    ftps.prot_p()
    print(f"ログインOK: {host}")

    count = 0
    for dirpath, _dirnames, filenames in os.walk(LOCAL_DIR):
        rel = os.path.relpath(dirpath, LOCAL_DIR)
        remote_dir = remote_root if rel == "." else f"{remote_root}/{rel.replace(os.sep, '/')}"
        ensure_dir(ftps, remote_dir)
        for fn in filenames:
            local_path = os.path.join(dirpath, fn)
            remote_path = f"{remote_dir}/{fn}"
            with open(local_path, "rb") as f:
                ftps.storbinary(f"STOR {remote_path}", f)
            count += 1
    ftps.quit()
    print(f"アップロード完了: {count} ファイル → {remote_root}/")


if __name__ == "__main__":
    main()
