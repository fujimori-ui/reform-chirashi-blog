#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ブログの新しい記事を、株式会社JibuLabo のマイビジネス(Googleビジネスプロフィール)へ投稿する。

毎朝の daily-article → deploy のあとに動く。
 - _posts/ の中から「直近 DAYS 日」の記事を見て、まだマイビジネスに出ていないものを古い順に投稿する
 - 「出ている」かどうかは、マイビジネス側の投稿の「詳細」ボタンのURLで判定する(記録ファイル不要)
 - 本文 = 題名 + 記事の出だし + 「つづきはブログで」。写真 = アイキャッチ画像。ボタン = 記事URL

使い方:
  python3 jibulabo_gbp.py --dry        何を出すか表示するだけ
  python3 jibulabo_gbp.py              本番(未投稿ぶんを投稿)
  python3 jibulabo_gbp.py --days 7     さかのぼる日数を変える(既定 3)
  python3 jibulabo_gbp.py --list       マイビジネスの最近の投稿を表示
  python3 jibulabo_gbp.py --delete accounts/…/locations/…/localPosts/…   投稿を消す
"""
import datetime
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://jibulabo.jp/blog"
ACCOUNT = "accounts/117464630818381172478"
LOCATION = "locations/4064873075658306906"   # 株式会社JibuLabo
TOKEN_URL = "https://oauth2.googleapis.com/token"
V4 = "https://mybusiness.googleapis.com/v4"
JST = datetime.timezone(datetime.timedelta(hours=9))
MAX_PER_RUN = 3          # 1回に出す上限(毎朝3本の記事に合わせる)
BODY_LIMIT = 600         # 読みやすい長さに(マイビジネスの上限は1500字)
TAIL = "\n\n▼つづきはブログで(下の「詳細」ボタンからご覧ください)"
UA = "Mozilla/5.0 (jibulabo-gbp)"


def http(url, data=None, headers=None, method=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class ApiError(RuntimeError):
    pass


class GBP:
    def __init__(self):
        cid, sec, rt = (os.environ.get("GBP_CLIENT_ID"), os.environ.get("GBP_CLIENT_SECRET"),
                        os.environ.get("GBP_REFRESH_TOKEN"))
        if not (cid and sec and rt):
            f = os.path.join(os.path.expanduser("~"), "google_ads", "gbp_creds.json")
            if os.path.exists(f):
                j = json.load(open(f, encoding="utf-8"))
                cid, sec, rt = j["client_id"], j["client_secret"], j["refresh_token"]
        if not (cid and sec and rt):
            raise ApiError("マイビジネスの接続情報(GBP_CLIENT_ID/SECRET/REFRESH_TOKEN)がありません")
        data = urllib.parse.urlencode({"client_id": cid, "client_secret": sec, "refresh_token": rt,
                                       "grant_type": "refresh_token"}).encode()
        code, body = http(TOKEN_URL, data=data, timeout=30)
        j = json.loads(body.decode("utf-8", "ignore") or "{}")
        if "access_token" not in j:
            raise ApiError(f"トークン取得に失敗: {j.get('error')} {j.get('error_description')}")
        self.h = {"Authorization": f"Bearer {j['access_token']}"}

    def call(self, method, url, body=None, params=None):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        h = dict(self.h)
        if data is not None:
            h["Content-Type"] = "application/json; charset=utf-8"
        code, raw = http(url, data=data, headers=h, method=method)
        try:
            j = json.loads(raw.decode("utf-8", "ignore") or "{}")
        except Exception:
            j = {"raw": raw[:300].decode("utf-8", "ignore")}
        if code >= 300:
            msg = j.get("error", {}).get("message", "") if isinstance(j, dict) else ""
            raise ApiError(f"HTTP {code} {method} {url.split('?')[0]}: {msg or j}")
        return j

    def list_posts(self, n=100):
        j = self.call("GET", f"{V4}/{ACCOUNT}/{LOCATION}/localPosts", params={"pageSize": n})
        return j.get("localPosts", [])

    def create_post(self, summary, image_url, cta_url):
        body = {"languageCode": "ja", "summary": summary, "topicType": "STANDARD",
                "callToAction": {"actionType": "LEARN_MORE", "url": cta_url},
                "media": [{"mediaFormat": "PHOTO", "sourceUrl": image_url}]}
        return self.call("POST", f"{V4}/{ACCOUNT}/{LOCATION}/localPosts", body=body)

    def delete_post(self, name):
        return self.call("DELETE", f"{V4}/{name}")


# ---------------------------------------------------------------- ブログ側
def plain(md):
    """記事(Markdown)を、マイビジネス向けのふつうの文章にする"""
    out = []
    for line in md.splitlines():
        s = line.strip()
        if not s or s == "---" or s.startswith(("![", "<", "{%", "|")):
            if out and out[-1] != "":
                out.append("")
            continue
        if s.startswith("#"):
            s = "■" + s.lstrip("#").strip()
        s = re.sub(r"^[-*]\s+", "・", s)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)      # リンクは文字だけ残す
        s = re.sub(r"\*\*|__|`", "", s)
        s = re.sub(r"https?://\S+", "", s).strip()           # 本文にURLは入れない
        if s:
            out.append(s)
    return "\n".join(out).strip()


def read_post(path):
    name = os.path.basename(path)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.+)\.md$", name)
    if not m:
        return None
    y, mo, d, slug = m.groups()
    raw = open(path, encoding="utf-8").read()
    fm = re.match(r"---\n(.*?)\n---\n(.*)", raw, flags=re.S)
    if not fm:
        return None
    head, body = fm.groups()

    def field(key):
        mm = re.search(rf'^{key}:\s*"?(.*?)"?\s*$', head, flags=re.M)
        return mm.group(1).strip() if mm else ""

    image = field("image")
    return {"date": datetime.date(int(y), int(mo), int(d)), "slug": slug,
            "title": field("title"), "description": field("description"),
            "url": f"{SITE}/{y}/{mo}/{slug}/",
            "image": (SITE + image) if image.startswith("/") else image,
            "body": plain(body)}


def recent_posts(days):
    today = datetime.datetime.now(JST).date()
    limit = today - datetime.timedelta(days=days)
    posts = [p for p in (read_post(f) for f in glob.glob(os.path.join(HERE, "_posts", "*.md"))) if p]
    posts = [p for p in posts if limit <= p["date"] <= today]
    return sorted(posts, key=lambda p: (p["date"], p["slug"]))


def make_summary(p):
    parts = [f"【{p['title']}】"]
    if p["description"]:
        parts.append(p["description"])
    text = "\n\n".join(parts)
    room = BODY_LIMIT - len(text) - len(TAIL) - 2
    body = p["body"]
    if len(body) > room:
        cut = body[:room]
        # 文の切れ目(。か改行)で止める
        k = max(cut.rfind("。"), cut.rfind("\n"))
        body = cut[:k + 1].rstrip() if k > room * 0.5 else cut.rstrip() + "…"
    if body:
        text += "\n\n" + body
    return text + TAIL


def wait_public(url, tries=20):
    """アップロード直後は画像・記事がまだ見えないことがあるので待つ"""
    for i in range(tries):
        code, _ = http(url, method="GET", timeout=30)
        if code == 200:
            return True
        time.sleep(15)
    return False


def norm(u):
    return (u or "").replace("https://www.", "https://").rstrip("/")


def sync(days=3, dry=False):
    posts = recent_posts(days)
    if not posts:
        print(f"直近{days}日のブログ記事はありません。今回は何もしません。")
        return 0
    g = GBP()
    done = {norm(x.get("callToAction", {}).get("url")) for x in g.list_posts()}
    todo = [p for p in posts if norm(p["url"]) not in done][:MAX_PER_RUN]
    if not todo:
        print(f"直近{days}日の記事{len(posts)}本は、すべてマイビジネスに投稿済みです。")
        return 0
    ng = 0
    for p in todo:
        summary = make_summary(p)
        print(f"--- {p['date']} {p['title']}\n    {p['url']}\n    画像 {p['image']}  本文 {len(summary)}字")
        if dry:
            print(summary + "\n")
            continue
        if not (wait_public(p["url"]) and wait_public(p["image"])):
            print("    まだ記事か画像が公開されていません。次回に回します。")
            ng += 1
            continue
        try:
            r = g.create_post(summary, p["image"], p["url"])
            print("    投稿しました:", r.get("name"), r.get("state"), r.get("searchUrl", ""))
        except ApiError as e:
            print("    投稿に失敗:", e)
            ng += 1
        time.sleep(5)
    return ng


def main():
    a = sys.argv[1:]
    if "--list" in a:
        for x in GBP().list_posts(20):
            print(x.get("createTime", "")[:10], x.get("state"), x.get("name"),
                  (x.get("summary") or "").replace("\n", " ")[:40], x.get("callToAction", {}).get("url", ""))
        return
    if "--delete" in a:
        name = a[a.index("--delete") + 1]
        GBP().delete_post(name)
        print("消しました:", name)
        return
    days = int(a[a.index("--days") + 1]) if "--days" in a else 3
    ng = sync(days, dry="--dry" in a)
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
