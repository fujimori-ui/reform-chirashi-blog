#!/usr/bin/env python3
"""記事のアイキャッチ画像(1200x630)を自動生成する。

ジブラボ(jibulabo.jp)と同じ配色: 紺 #14395C / 青 #1B6FB0 / 水色 #2E9BD6 / 淡青 #BFDDF2。
サイトの「風の流線」モチーフを背景に、タイトル文字を大きく載せるデザイン。

使い方:
    python make_eyecatch.py "記事タイトル" スラッグ名
→ assets/images/eyecatch/スラッグ名.png に保存
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
OUT_DIR = os.path.join(HERE, "assets", "images", "eyecatch")

W, H = 1200, 630
NAVY = (20, 57, 92)
BLUE = (27, 111, 176)
SKY = (46, 155, 214)
LIGHT = (191, 221, 242)
PALE = (234, 243, 250)
GRAY = (90, 107, 126)


def font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, f"ZenKakuGothicNew-{name}.ttf"), size)


def wrap(draw, text, fnt, max_width):
    """文字幅を測りながら行に分ける(日本語向け: 1文字ずつ詰める)。"""
    lines, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=fnt) <= max_width:
            line += ch
        else:
            lines.append(line)
            line = ch
    if line:
        lines.append(line)
    # 行頭禁則: 句読点や小さい文字が行の先頭に来たら前の行の末尾へ移す
    kinsoku = "。、！？…」』）｝〉》ゃゅょっぁぃぅぇぉんー・"
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in kinsoku:
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    return [ln for ln in lines if ln]


def draw_wave(draw, y_base, amp, period, color, width, phase=0.0):
    pts = [(x, y_base + amp * math.sin(2 * math.pi * (x / period) + phase)) for x in range(-10, W + 11, 8)]
    draw.line(pts, fill=color, width=width, joint="curve")


def make(title, slug):
    # 白背景に青系の文字・あしらい(ブルー×白デザイン)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # 背景: 右上にサイトと同じ「風の流線」(淡い青)
    draw_wave(d, 90, 34, 900, LIGHT, 5, phase=0.5)
    draw_wave(d, 150, 44, 1100, PALE, 7, phase=2.2)
    draw_wave(d, 55, 26, 760, (166, 207, 234), 4, phase=4.0)
    draw_wave(d, 560, 40, 1000, PALE, 6, phase=1.2)

    # 下辺: ブランドのグラデーション帯(青)
    bar_h = 16
    for x in range(W):
        t = x / W
        if t < 0.6:
            u = t / 0.6
            c = tuple(round(BLUE[i] + (SKY[i] - BLUE[i]) * u) for i in range(3))
        else:
            u = (t - 0.6) / 0.4
            c = tuple(round(SKY[i] + ((111, 194, 236)[i] - SKY[i]) * u) for i in range(3))
        d.line([(x, H - bar_h), (x, H)], fill=c)

    margin = 84

    # 上: ブログ名(ラベル) 青バー+青文字
    d.rounded_rectangle([margin, 78, margin + 10, 122], radius=5, fill=SKY)
    d.text((margin + 28, 80), "小さな工務店の集客ノート", font=font("Bold", 34), fill=BLUE)

    # 中央: タイトル(長さに応じて文字サイズを調整、最大3行) 紺文字
    max_w = W - margin * 2
    size = 76
    while size > 44:
        fnt = font("Black", size)
        lines = wrap(d, title, fnt, max_w)
        if len(lines) <= 3:
            break
        size -= 6
    line_h = round(size * 1.42)
    block_h = line_h * len(lines)
    y = 78 + 70 + ((H - 16 - 60) - (78 + 70) - block_h) // 2  # ラベル下〜下帯上の中央
    for ln in lines:
        d.text((margin, y), ln, font=fnt, fill=NAVY)
        y += line_h

    # 下: 運営者名(右下) グレー
    fnt_s = font("Medium", 26)
    label = "JibuLabo（ジブラボ）｜小さな工務店の、経営の参謀"
    tw = d.textlength(label, font=fnt_s)
    d.text((W - margin - tw, H - bar_h - 54), label, font=fnt_s, fill=GRAY)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{slug}.png")
    img.save(out, optimize=True)
    print(f"画像を保存しました: {os.path.relpath(out, HERE)}")
    return out


ILLUST_DIR = os.path.join(HERE, "assets", "images", "illust")


def make_from_illust(illust_name, slug, max_h=440, max_w=760):
    """購入済みの手描きタッチイラストを、ブランド背景(白+風の流線+青帯)に合成する。"""
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    # 背景: サイトと同じ「風の流線」
    draw_wave(d, 90, 34, 900, LIGHT, 5, phase=0.5)
    draw_wave(d, 150, 44, 1100, PALE, 7, phase=2.2)
    draw_wave(d, 55, 26, 760, (166, 207, 234), 4, phase=4.0)
    draw_wave(d, 560, 40, 1000, PALE, 6, phase=1.2)

    # イラストの後ろにうす青の円(サイトのカード風のやわらかさ)
    d.ellipse([W // 2 - 265, 80, W // 2 + 265, 610], fill=PALE)
    draw_wave(d, 560, 40, 1000, PALE, 6, phase=1.2)

    # イラスト本体(中央)
    illust = Image.open(os.path.join(ILLUST_DIR, f"{illust_name}.png")).convert("RGBA")
    scale = min(max_h / illust.height, max_w / illust.width)
    illust = illust.resize((round(illust.width * scale), round(illust.height * scale)), Image.LANCZOS)
    x = (W - illust.width) // 2
    y = 78 + (500 - illust.height) // 2
    img.paste(illust, (x, y), illust)

    # 下辺: ブランドのグラデーション帯(青)
    bar_h = 16
    for px in range(W):
        t = px / W
        if t < 0.6:
            u = t / 0.6
            c = tuple(round(BLUE[i] + (SKY[i] - BLUE[i]) * u) for i in range(3))
        else:
            u = (t - 0.6) / 0.4
            c = tuple(round(SKY[i] + ((111, 194, 236)[i] - SKY[i]) * u) for i in range(3))
        d.line([(px, H - bar_h), (px, H)], fill=c)

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{slug}.png")
    img.save(out, optimize=True)
    print(f"画像を保存しました: {os.path.relpath(out, HERE)}")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("使い方: python make_eyecatch.py \"記事タイトル\" スラッグ名")
    make(sys.argv[1], sys.argv[2])
