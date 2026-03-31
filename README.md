# Gojo Satoru — Golang 2026 Upgrade

This repository has been migrated from Python to a pure **Go** runtime for a lightweight 2026 deployment baseline.

## Stack
- Go 1.24 (standard library)
- FFmpeg runtime integration
- HTTP health and stream validation endpoints

## Run locally
```bash
go build ./...
BOT_TOKEN=demo MONGO_URL=demo go run .
```

## Required environment variables
- `BOT_TOKEN`
- `MONGO_URL`
- `OWNER_ID` (optional)
- `DEFAULT_RTMP_URL` (optional; defaults to Telegram RTMPS endpoint)
- `LOGGER_ID` (optional)
- `PORT` (optional; default `8080`)

## Deploy
```bash
docker build -t gojo-satoru .
docker run -e BOT_TOKEN=demo -e MONGO_URL=demo -p 8080:8080 gojo-satoru
```

## Endpoints
- `GET /healthz`
- `GET /stream/validate?input=<media_url>&rtmp=<rtmp_url>`
