# Deploying / Moving to a New Server

The chatbot runs in Docker on port `8002`. Only two things are not in git and
must be carried over from the old server:

| Item | In git? | Notes |
|---|---|---|
| Code | Yes | Clone from GitHub (`main`) |
| `.env` (`GROK_API_KEY`, `GOOGLE_API_KEY`, `CHAT_API_KEY`, `ADMIN_API_KEY`, `REDIS_URL`, `CORS_ORIGINS`, ...) | No | Copy it |
| `chroma_db/` (component index + chat memory) | No | Copy it to keep memory, or rebuild the index |

Services that point at the chatbot and must be updated after the move:

- **serey-api** production `.env`: `AI_CHATBOT_BASE_URL`
- **fe-serey-web** production env: `AI_CHATBOT_BASE_URL`, `NEXT_PUBLIC_NEW_WAVE_API_END_POINT`

## 1. Old server: package the data

```bash
cd /path/to/SEREY-chatbot          # find it with: docker ps / pm2 ls / ps aux | grep uvicorn
cat .env | grep -E 'REDIS_URL|CORS_ORIGINS'   # note these, see step 3
tar czf chatbot-data.tgz .env chroma_db
scp chatbot-data.tgz root@NEW_SERVER_IP:/root/
```

## 2. New server: install Docker, get the code, unpack the data

```bash
curl -fsSL https://get.docker.com | sh
git clone https://github.com/TeHenglay/SEREY-chatbot.git /opt/serey-chatbot
cd /opt/serey-chatbot
tar xzf /root/chatbot-data.tgz -C /opt/serey-chatbot
```

## 3. Check `.env` for the new server

- `REDIS_URL`: the categorize endpoint treats Redis as the source of truth
  (serey-api clears `serey:categories:*` there), so point it at **the same
  Redis serey-api uses**. Inside Docker, `localhost` is the container itself:
  - Redis on another server: `REDIS_URL=redis://REDIS_HOST:6379`
  - Redis on this same server: `REDIS_URL=redis://host.docker.internal:6379`
    (Redis must listen on more than `127.0.0.1` for this to work)
  - If Redis can't be reached the app still runs, using an in-memory cache.
- `CORS_ORIGINS`: your real site domains, comma-separated.
- Leave `ENABLE_DOCS` unset in production.

## 4. Start it

```bash
docker compose up -d --build
docker compose logs -f             # wait for "Application startup complete"
```

## 5. Verify

```bash
curl http://localhost:8002/health
curl http://localhost:8002/ready
```

If the components collection is missing or empty (e.g. you did not copy
`chroma_db/`), build it once:

```bash
docker compose exec chatbot python scripts/index_components.py
```

Knowledge sync runs automatically on startup and daily afterwards.

## 6. Firewall

Only serey-api (and the frontend server, if it calls the chatbot directly)
needs to reach port 8002:

```bash
ufw allow OpenSSH
ufw allow from SEREY_API_SERVER_IP to any port 8002
ufw allow from FRONTEND_SERVER_IP to any port 8002   # only if needed
ufw enable
```

Note: Docker-published ports can bypass ufw. If you need a strict lock-down,
change the port mapping to `"127.0.0.1:8002:8000"` and put nginx in front, or
use the cloud provider's firewall.

Optional: put nginx + HTTPS in front with a domain like `ai.serey.io`, so the
next move is only a DNS change.

## 7. Point everything at the new server

- serey-api: `AI_CHATBOT_BASE_URL=http://NEW_SERVER_IP:8002`, then restart serey-api.
- Frontend: update `AI_CHATBOT_BASE_URL` and `NEXT_PUBLIC_NEW_WAVE_API_END_POINT`,
  then **rebuild** and redeploy (`NEXT_PUBLIC_*` is baked in at build time).

## 8. Test, then shut down the old server

Build a page through the real site and check `docker compose logs` on the new
server shows `POST /api/builder/chat 200`. Keep `chatbot-data.tgz` as a backup,
then turn off the old server.

## Updating later

```bash
cd /opt/serey-chatbot && git pull && docker compose up -d --build
```
