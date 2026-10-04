# Deployment guide

- **Frontend** → Vercel (static site, free).
- **Backend stack** (FastAPI + Keycloak + Postgres/pgvector + Ollama) → one AWS EC2 instance with Docker Compose.
  Caddy in front gives HTTPS automatically (required: the Vercel site is HTTPS, and browsers block calls to an HTTP API).

Why one VM and not Render/Railway: the local LLM (`qwen2.5:3b`) needs ~3–4 GB of RAM and Keycloak
another ~1 GB. Free PaaS tiers give 512 MB–1 GB.

## 1. Create the EC2 instance

1. Ubuntu 24.04, type **t3.large** (2 vCPU, 8 GB RAM), 30 GB gp3 disk.
2. Security group inbound: 22 (your IP only), 80 and 443 (0.0.0.0/0).
3. Allocate an **Elastic IP** and associate it (so the IP — and the domain — do not change on restart).
4. Stop the instance when you are not using it (you pay per hour while it runs).

## 2. Domain

No purchase needed: with Elastic IP `3.91.10.20` use `DOMAIN=3-91-10-20.sslip.io`.
The stack will be served at:

- API: `https://api.3-91-10-20.sslip.io`
- Keycloak: `https://auth.3-91-10-20.sslip.io`

(Alternative: a free DuckDNS name, e.g. `DOMAIN=hga-team.duckdns.org`.)

## 3. Install Docker and start the stack

```bash
ssh ubuntu@<ELASTIC_IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit     # log in again

git clone https://github.com/Nats306/HungerGamesAgent.git
cd HungerGamesAgent
cp .env.example .env
nano .env
```

Add / change in `.env`:

```
DOMAIN=3-91-10-20.sslip.io
FRONTEND_URL=https://hunger-games-agent.vercel.app
POSTGRES_PASSWORD=<strong password>
KEYCLOAK_ADMIN_PASSWORD=<strong password>
```

```bash
docker compose -f compose.yml -f compose.prod.yml up -d --build
docker compose logs -f ollama-pull          # wait for the model download
```

Load the knowledge base (scrape on your laptop, then copy `data/wiki` to the server, or run the scraper there):

```bash
scp -r data/wiki ubuntu@<ELASTIC_IP>:~/HungerGamesAgent/data/
docker compose exec backend python -m scripts.seed /data
```

Check: `curl https://api.<DOMAIN>/health` → `{"status":"ok"}`.

## 4. Keycloak: allow the production frontend

The realm is imported with `localhost` redirect URIs. In `https://auth.<DOMAIN>/admin`
(realm **hunger-games** → Clients → **hga-frontend**) add:

- Valid redirect URIs: `https://<your-app>.vercel.app/*`
- Valid post logout redirect URIs: `https://<your-app>.vercel.app/*`
- Web origins: `https://<your-app>.vercel.app`

Also change the passwords of the `demo` and `hga-admin` users.

## 5. Frontend on Vercel

1. Import the GitHub repo in Vercel, **Root Directory = `frontend`**, framework Vite.
2. Environment variables:

| Variable | Value |
|---|---|
| `VITE_API_URL` | `https://api.<DOMAIN>` |
| `VITE_KEYCLOAK_URL` | `https://auth.<DOMAIN>` |
| `VITE_KEYCLOAK_REALM` | `hunger-games` |
| `VITE_KEYCLOAK_CLIENT_ID` | `hga-frontend` |

3. Deploy. `vercel.json` rewrites every route to `index.html` (needed for the Keycloak redirect back).

## Environment variables (backend)

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | set by compose | Postgres connection |
| `KEYCLOAK_ISSUER` | set by compose | Must equal the `iss` claim of the tokens |
| `KEYCLOAK_JWKS_URL` | set by compose | Where signing keys are downloaded (internal URL) |
| `KEYCLOAK_AUDIENCE` | `hga-api` | Required `aud` claim (added by the realm's audience mapper) |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed frontend origins (comma-separated) |
| `OLLAMA_BASE_URL` | set by compose | Ollama server |
| `LLM_MODEL` | `qwen2.5:3b` | Ollama model |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | Sentence Transformers model |
| `SIMILARITY_THRESHOLD` | `0.80` | Minimum cosine similarity to use a chunk |
| `RETRIEVAL_TOP_K` | `6` | Chunks retrieved per query |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `150` | Text splitter settings (characters) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| API returns 401 `Invalid token: Invalid issuer` | `KEYCLOAK_ISSUER` differs from Keycloak's `KC_HOSTNAME`. Both must use the same public URL. |
| 401 `Invalid audience` | The `audience-hga-api` mapper is missing on the `hga-frontend` client. |
| Browser: CORS error | `FRONTEND_URL` / `CORS_ORIGINS` does not match the Vercel URL exactly (no trailing slash). |
| Keycloak "Invalid parameter: redirect_uri" | Step 4 not done. |
| Chat returns 503 | Ollama is not running or the model was not pulled: `docker compose logs ollama ollama-pull`. |
| Very slow answers | Normal on CPU (~5–15 s). A bigger instance or `qwen2.5:1.5b` reduces latency. |
| Caddy cannot get a certificate | Ports 80/443 closed in the security group, or DNS does not point to the IP yet. |
