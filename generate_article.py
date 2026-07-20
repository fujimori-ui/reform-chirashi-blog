#!/usr/bin/env python3
"""毎週1本、ブログ記事をClaudeで自動作成するスクリプト。

ネタ帳(topics.json)から順番にテーマを1つ取り、記事を書いて _posts/ に保存する。
進行状況は state.json の next_topic に記録する。GitHub Actions から毎週月曜に呼ばれる。
"""

import argparse
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOPICS_PATH = os.path.join(HERE, "topics.json")
STATE_PATH = os.path.join(HERE, "state.json")
POSTS_DIR = os.path.join(HERE, "_posts")

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """あなたはブログ「小さな工務店の集客ノート」(運営: JibuLabo/ジブラボ)の執筆者です。
読者は、リフォーム・建築の一人親方や、スタッフ数名の小さな工務店の社長さん。
チラシと地域密着で地元から仕事をもらう方法を、やさしく実務的に伝えます。

## ブログの軸(『5000世帯からはじめるリフォーム経営塾』とチラシ集客 reform-chirashi.jp の考え方)
- 商圏は約5000世帯の狭いエリアに絞り、ご近所に顔を出し続けて「一番に思い出される存在」になる。
- 安売り・値引き・価格競争はしない。「安いから」ではなく「信頼できるから」で選ばれる。
- 「◯◯%OFF」の商品チラシではなく、暮らしに役立つ「How toチラシ」で信頼を積む。
- 小さな工事を入口に、OB客・紹介・口コミで仕事が回る仕組みを作る。
- 下請けマインド(「お客様に合わせます」「いくらでも安く」)を捨て、自分の商圏と得意で勝負する。
- 参考動画が指定されたら、その主張の方向性に沿って書く。ただし動画に無い数字・事例・実話は作らない。

## 書き方のルール
- やさしい日本語。専門用語・カタカナ語はなるべく避け、使うときは一言でかみくだく。
- 文体は「です・ます」。面倒見のいい参謀のような、丁寧だが堅すぎない口調。
- 長さは1500〜2200字。見出し(## と ###)で区切り、最後は必ず「## まとめ」で箇条書き+ひと押しの一文。
- 具体的な言葉例・手順・目安を入れ、読んだその週に1つ実行できる内容にする。

## 絶対に守ること(信頼を守るルール)
- 架空の事例・作り話・でっちあげの数字や統計は絶対に書かない。
- 「必ず儲かる」「絶対に反響が出る」などの誇張・断定・成果の約束をしない。
- 制度や相場など変わりうる情報は断定せず、「最新は窓口で確認を」と添える。
- 記事の最後に宣伝やリンクを書かない(案内はページのテンプレートが自動で付くため、本文は役立つ内容だけにする)。

## 出力形式(この形式だけを出力。前置き・説明・コードブロックは不要)
1行目: 記事タイトル(32字以内。読者の悩み・興味が入った具体的なもの)
2行目: 記事の説明文(50〜90字。検索結果に出る紹介文)
3行目: ---
4行目以降: 記事本文(Markdown。タイトルの繰り返しは書かず、いきなり本文から)"""

ILLUST_PROMPT = """あなたはフラットデザインのイラストレーターです。ブログ記事のアイキャッチ用に、記事の内容をひと目でイメージできるSVGイラストを1枚作ってください。

## 必ず守ること
- 出力はSVGコードのみ。前置き・説明・コードブロックは不要。
- <svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630"> で始める。
- 文字・数字・アルファベットは一切入れない(<text>要素は禁止)。絵だけで内容を伝える。
- 使う色はこのパレットだけ: 紺#14395C 青#1B6FB0 水色#2E9BD6 淡青#BFDDF2 うす青#EAF3FA 黄#F6C453 珊瑚#E8756D 緑#5BBB7B 白#ffffff 肌#F2C9A0
- 背景は白。雰囲気づけに、淡い色(#EAF3FA や #BFDDF2)のゆるやかな曲線を上下に2〜3本入れる。
- 太めの輪郭のシンプルな図形(rect/circle/path)で、フラットで親しみやすい絵にする。
- 主役のモチーフ(家・チラシ・人・ハート・お金など記事に合うもの)を中央に大きく1〜3個。ごちゃごちゃさせない。
- グラデーションやフィルタは使わない(単色塗りのみ)。
- 最後に <rect y="614" width="1200" height="16" fill="#1B6FB0"/> の帯を置いて </svg> で閉じる。

## 題材(この記事の内容を絵にする)
タイトル: {title}
説明: {desc}
"""


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def existing_titles():
    """既存記事のタイトル一覧(重複防止のためプロンプトに渡す)。"""
    titles = []
    if not os.path.isdir(POSTS_DIR):
        return titles
    for name in sorted(os.listdir(POSTS_DIR)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(POSTS_DIR, name), encoding="utf-8") as f:
            for line in f:
                m = re.match(r'^title:\s*"?(.+?)"?\s*$', line.strip())
                if m:
                    titles.append(m.group(1))
                    break
    return titles


def today_jst():
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600))


def generate(topic, titles):
    import anthropic

    client = anthropic.Anthropic()
    user_prompt = (
        f"今回の記事のテーマ: {topic['theme']}\n"
        f"切り口のヒント: {topic['hint']}\n"
    )
    if topic.get("video_title"):
        user_prompt += f"参考動画(この主張に沿って書く): {topic['video_title']}\n"
    user_prompt += (
        "\nすでに公開済みの記事タイトル(内容をかぶらせない):\n"
        + "\n".join(f"- {t}" for t in titles)
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # 応答には本文以外のブロック(思考メモ等)が混ざることがあるので、本文だけ取り出す
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    if not text.strip():
        raise SystemExit(f"エラー: 本文ブロックが空でした。stop_reason={resp.stop_reason}")
    return text.strip()


def make_illustration(title, desc, slug):
    """記事の内容に合ったイラストをClaudeにSVGで描いてもらい、PNGに変換して保存する。"""
    import anthropic
    import cairosvg

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        messages=[{"role": "user", "content": ILLUST_PROMPT.format(title=title, desc=desc)}],
    )
    svg = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    svg = re.sub(r"^```(?:svg|xml)?\s*|\s*```$", "", svg)
    start = svg.find("<svg")
    end = svg.rfind("</svg>")
    if start < 0 or end < 0:
        raise ValueError("応答にSVGが見つかりませんでした")
    svg = svg[start:end + len("</svg>")]
    # 念のため: 文字要素が混ざっていたら取り除く(絵だけにする)
    svg = re.sub(r"<text\b[^>]*>.*?</text>", "", svg, flags=re.S)
    out_dir = os.path.join(HERE, "assets", "images", "eyecatch")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{slug}.png")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out, output_width=1200, output_height=630)
    return out


def parse_output(raw):
    """出力を タイトル/説明/本文 に分ける。"""
    text = raw.strip()
    text = re.sub(r"^```(?:markdown)?\s*|\s*```$", "", text)  # 万一のコードブロック除去
    lines = text.split("\n")
    if len(lines) < 4:
        raise SystemExit(f"エラー: 出力が短すぎます:\n{text[:200]}")
    title = lines[0].strip().lstrip("#").strip()
    desc = lines[1].strip()
    rest = lines[2:]
    if rest[0].strip() == "---":
        rest = rest[1:]
    body = "\n".join(rest).strip()
    if not title or not body:
        raise SystemExit("エラー: タイトルまたは本文が空です。")
    return title, desc, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="保存せず記事を表示するだけ")
    args = ap.parse_args()

    topics = load_json(TOPICS_PATH, [])
    state = load_json(STATE_PATH, {"next_topic": 0})
    idx = state.get("next_topic", 0)

    if idx >= len(topics):
        print(f"ネタ帳({len(topics)}本)を最後まで使い切りました。topics.jsonにネタを追加してください。今回は何もしません。")
        return

    topic = topics[idx]
    date = today_jst()
    filename = f"{date}-{topic['slug']}.md"
    path = os.path.join(POSTS_DIR, filename)
    if os.path.exists(path):
        print(f"きょうの記事({filename})はすでにあります。二重作成を防ぐため何もしません。")
        return

    print(f"[ネタ {idx + 1}/{len(topics)}] {topic['theme']}")
    titles = existing_titles()
    raw = generate(topic, titles)
    title, desc, body = parse_output(raw)

    front = (
        "---\n"
        "layout: post\n"
        f'title: "{title.replace(chr(34), "”")}"\n'
        f'description: "{desc.replace(chr(34), "”")}"\n'
        f"image: /assets/images/eyecatch/{topic['slug']}.png\n"
        + (f"video: {topic['video']}\n" if topic.get("video") else "")
        + "---\n\n"
    )
    content = front + body + "\n"

    if args.dry_run:
        print("=== dry-run(保存しません) ===")
        print(content)
        print(f"文字数(本文): {len(body)}")
        return

    os.makedirs(POSTS_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        make_illustration(title, desc, topic["slug"])
        print("アイキャッチ: 記事の内容に合わせたイラストを作成しました")
    except Exception as e:  # イラストに失敗しても記事は止めない(文字デザインで代用)
        print(f"イラスト作成に失敗したため、文字デザインで代用します: {e}")
        import make_eyecatch
        make_eyecatch.make(title, topic["slug"])
    state["next_topic"] = idx + 1
    save_json(STATE_PATH, state)
    print(f"記事を保存しました: _posts/{filename}")
    print(f"タイトル: {title}")


if __name__ == "__main__":
    main()
