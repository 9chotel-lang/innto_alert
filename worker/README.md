# Worker

Cloudflare Worker は `/state` と `/ingest` を提供し、KV に state JSON を保存します。

## セットアップ

```bash
cd worker
npm create cloudflare@latest . -- --existing-script
npm install
```

`wrangler.toml` の `kv_namespaces` を実IDで置換してください。

```bash
wrangler secret put WORKER_TOKEN
wrangler secret put ONESIGNAL_REST_API_KEY
wrangler secret put ONESIGNAL_APP_ID
```

## デプロイ

```bash
wrangler deploy
```

## エンドポイント

- `GET /state` : 現在 state を返却
- `POST /ingest` : Bearer 必須。snapshot を受け取り state を更新

`POST /ingest` の Authorization ヘッダ:

```
Authorization: Bearer <WORKER_TOKEN>
```
