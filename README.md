# innto_alert

innto の「稼働状況表CSV」から当月+次月の空室を抽出し、Cloudflare Worker へ送信、Web(PWA)で可視化+通知する構成です。

## 構成

- `scripts/` : 30分実行ジョブ本体（Playwright DL→CSV解析→WorkerへPOST）
- `worker/` : `/state`, `/ingest` を提供し KV に状態保存、通知判定
- `web/` : GitHub Pages 想定の静的PWA
- `.github/workflows/run_check.yml` : 30分 cron（動けばOKの補助）

## 1) ローカル（Windows優先）で run_check を動かす

### 事前準備

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install playwright
python -m playwright install chromium
```

環境変数は `scripts/sample_env.txt` をコピーして設定してください（認証情報のデフォルト値はありません）。

必須:
- `INNTO_HOTEL_ID`
- `INNTO_ACCOUNT`
- `INNTO_PASSWORD`
- `WORKER_INGEST_URL`
- `WORKER_TOKEN`

任意:
- `REPORT_URL`（デフォルト: `https://pms.innto.jp/#report/ope-status`）
- `DOWNLOAD_DIR`（未設定なら temp）
- `PLAYWRIGHT_HEADLESS`（省略時 true / デバッグ時 false）

### 実行

```powershell
python scripts/run_check.py
```

## 2) Worker デプロイ

```bash
cd worker
npm install -D wrangler typescript @cloudflare/workers-types
wrangler kv namespace create STATE_KV
wrangler kv namespace create STATE_KV --preview
# wrangler.toml の ID を置換
wrangler secret put WORKER_TOKEN
wrangler secret put ONESIGNAL_APP_ID
wrangler secret put ONESIGNAL_REST_API_KEY
wrangler deploy
```

### API 仕様

- `GET /state` : state JSON
- `POST /ingest` : Bearer 必須。snapshot を受信し `prev/curr` 更新

通知ルール:
- low_alert: `curr.today.vacant <= 10 && last_state != low`
- normal復帰: `curr.today.vacant >= 12`
- spike_alert: `abs(curr-prev)>=6 && 間隔<=70分 && spike通知から30分以上`

## 3) PWA 公開（GitHub Pages）

`web/app.js` の以下を実環境へ置換:
- `stateUrl`
- `ONESIGNAL_APP_ID`

Pages へ `web/` を公開してください。

UI機能:
- 当月/次月の「日→空室数」表
- 今日行の強調
- 低在庫バッジ（<=10）
- 更新ボタン
- 通知購読ボタン
- iOS注意文（ホーム画面追加が必要）

## 4) 通知確認

1. Webで通知購読
2. `run_check.py` を実行して `/ingest` へ送信
3. Worker の state (`/state`) で `flags` と `last_notify` を確認
4. OneSignal ダッシュボードでも配信結果を確認

## 5) GitHub Actions（任意）

`.github/workflows/run_check.yml` は30分 cron + 手動実行を定義しています。
Secrets 設定後に利用してください。Playwright/サイト依存で不安定な場合があります。
