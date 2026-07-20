# 小さな工務店の集客ノート

JibuLabo（ジブラボ）のブログ。チラシと地域密着で地元から仕事をもらう方法を、小さな工務店の社長さん向けにやさしく解説する。Jekyllでビルドし、エックスサーバー(jibulabo.jp)へ自動アップロードして公開。

- 公開URL: https://jibulabo.jp/blog/
- 毎週月曜の朝、`weekly-article` ワークフローがClaudeで記事を1本作って自動追加する
- 記事追加やmainへのpushのたびに `deploy` ワークフローがビルド→FTPSでエックスサーバーの `/jibulabo.jp/public_html/blog/` へ全ファイル上書きアップロードする(削除はしないので、記事を消したらサーバー側も手で消すこと)
- FTPパスワードはリポジトリのSecret `FTP_PASSWORD` に登録(ホスト sv17104.xserver.jp / ユーザー jibulabo はdeploy.ymlに直書き)
- ネタ帳は `topics.json`(順番に消化、進行は `state.json`)。ネタを足すときは topics.json に追記するだけ
- 記事は `_posts/*.md`。手で書いた記事もここに置けばそのまま公開される
- 記事下の案内(チラシ集客LP・書籍プレゼント)は `_includes/cta.html` で一括変更
- デザインは jibulabo.jp と同じ配色・フォント。`assets/style.css` で調整

## ルール

- 架空の事例・でっちあげの数字・誇張表現は書かない(生成プロンプトにも明記済み)
- 記事本文に宣伝は書かない。案内はテンプレートが自動で付ける
