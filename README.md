# Ticket Analyzer

A minimal full-stack demo: submit a support ticket, get its sentiment
analyzed by a tiny Hugging Face model, and see the history persisted in
PostgreSQL — all running in Docker Compose.

- **Frontend:** React + Vite, served by Nginx on port 3000.
- **Backend:** FastAPI + Uvicorn on port 8000.
- **AI:** `distilbert-base-uncased-finetuned-sst-2-english` (CPU-only).
- **DB:** PostgreSQL 16 with a named Docker volume.

> 📘 **Want to understand how it works in depth?** Read
> **[ARCHITECTURE.md](./ARCHITECTURE.md)** — it covers the full request
> flow, the AI integration, the Nginx reverse-proxy trick, the Docker
> orchestration, and every design decision with its rationale.

## Repository layout

```
.
├── PRD.md                  # source of truth for the spec
├── README.md               # this file — quick-start commands
├── ARCHITECTURE.md         # deep-dive: how it all works
├── docker-compose.yml      # local dev: builds from source
├── docker-compose.vm.yml   # VM deploy: pulls from DockerHub
├── backend/
│   ├── Dockerfile          # bakes HF model weights into the image
│   ├── requirements.txt
│   └── app/                # FastAPI app
└── frontend/
    ├── Dockerfile          # multi-stage: Vite build -> Nginx
    ├── nginx.conf          # reverse-proxies /api -> backend
    └── src/                # React app
```

## Prerequisites

- Docker Engine 24+ and the Docker Compose plugin.
- A DockerHub account (only required for the VM deploy step).

## Run locally (build from source)

```bash
docker compose up --build
```

First build takes a few minutes because the backend Dockerfile downloads
the DistilBERT SST-2 model weights into the image. Subsequent builds
reuse the cache.

Open http://localhost:3000 in a browser.

## API surface

| Method | Path       | Purpose                                      |
| ------ | ---------- | -------------------------------------------- |
| GET    | `/health`  | Health check.                                |
| POST   | `/tickets` | Create a ticket and analyze its sentiment.   |
| GET    | `/tickets` | List saved tickets, newest first.            |

Example:

```bash
curl -s -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Lab VM issue","message":"My lab VM is not opening before the deadline.","category":"lab"}'
```

The frontend Nginx container reverse-proxies `/api/*` to the backend
service on the internal Docker network, so the browser only ever talks
to port 3000. No CORS configuration is required in that mode.

## Push images to DockerHub (do this BEFORE the workshop)

The backend image is large and the HF download is slow, so pre-build it
once and push:

```bash
# Build
docker build -t <dockerhub-username>/ticket-analyzer-backend:v1 ./backend
docker build -t <dockerhub-username>/ticket-analyzer-frontend:v1 ./frontend

# Push
docker push <dockerhub-username>/ticket-analyzer-backend:v1
docker push <dockerhub-username>/ticket-analyzer-frontend:v1
```

## Deploy on the Poridhi Lab VM

On the VM, clone the repo (or copy `docker-compose.vm.yml`) and run:

```bash
DOCKERHUB_USER=<dockerhub-username> docker compose -f docker-compose.vm.yml up -d
```

Open `http://<vm-ip>:3000`.

## Dry-run validation

These four checks are the workshop acceptance criteria:

1. **Model weights are baked into the image**
   ```bash
   docker run --rm --network=none <dockerhub-username>/ticket-analyzer-backend:v1 \
     python -c "from app import sentiment; print('OK', sentiment.analyze('great work'))"
   ```
   The container starts and produces a sentiment without ever touching
   `huggingface.co` — `TRANSFORMERS_OFFLINE=1` would otherwise fail
   loudly.

2. **Fresh Postgres volume works without manual migrations**
   ```bash
   docker compose down -v
   docker compose up
   curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" \
     -d '{"title":"first","message":"hello world"}'
   ```
   `Base.metadata.create_all` creates the `tickets` table on startup.

3. **Cross-origin browser works via the reverse proxy**
   Open the frontend from any host on the same network — submissions
   succeed because the browser only ever sees the same origin
   (port 3000) and Nginx proxies `/api` to the backend.

4. **Sentiment labels are POSITIVE / NEGATIVE (not LABEL_0 / LABEL_1)**
   ```bash
   curl -s http://localhost:8000/tickets | python -m json.tool
   ```
   Confirms the real DistilBERT SST-2 model is loaded.

## Environment variables

| Service     | Variable                | Default                                                       |
| ----------- | ----------------------- | ------------------------------------------------------------- |
| backend     | `DATABASE_URL`          | `postgresql://postgres:postgres@db:5432/ticket_db`            |
| backend     | `MODEL_NAME`            | `distilbert-base-uncased-finetuned-sst-2-english`             |
| backend     | `HF_HOME`               | `/opt/hf-cache`                                               |
| backend     | `TRANSFORMERS_OFFLINE`  | `1`                                                           |
| frontend    | `VITE_API_BASE_URL`     | `/api`                                                        |

## License

Workshop demo — use freely.
