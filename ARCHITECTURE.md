# Ticket Analyzer — Architecture & Feature Documentation

> A deep-dive into how the Ticket Analyzer full-stack application works:
> every component, every request, and every Docker trick that makes the
> demo deployable on a single VM.

---

## 1. What it does

The Ticket Analyzer is a small but complete web application with three jobs:

1. **Accept** a support ticket from a user through a web form.
2. **Analyze** the ticket's emotional tone (positive vs. negative) using a
   real, pre-trained Hugging Face machine-learning model.
3. **Persist** the ticket and its sentiment to a relational database so
   the history survives page refreshes and container restarts.

The app is built as a workshop demo to illustrate the **complete
engineering path** from a Product Requirements Document (PRD) all the way
to a running service on a remote VM:

```
PRD  →  source code  →  container images  →  DockerHub  →  live deployment
```

---

## 2. High-level architecture

```
   ┌──────────────────────────────────────────────────────────────────┐
   │                      Browser (user's device)                     │
   └──────────────────────────────────────────────────────────────────┘
                                  │
                                  │  HTTP on port 3000
                                  ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  frontend container  —  Nginx serving a Vite-built React SPA     │
   │  · Static assets: /index.html, /assets/*.js, /assets/*.css       │
   │  · Reverse proxy: /api/*  →  http://backend:8000/*               │
   └──────────────────────────────────────────────────────────────────┘
                                  │
                                  │  HTTP on the internal Docker network
                                  ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  backend container  —  FastAPI + Uvicorn + HF DistilBERT SST-2    │
   │  · /health        : liveness probe                               │
   │  · POST /tickets  : create + analyze sentiment + persist         │
   │  · GET  /tickets  : list newest-first                            │
   │  · Model loaded ONCE at module import (not per request)          │
   └──────────────────────────────────────────────────────────────────┘
                                  │
                                  │  PostgreSQL wire protocol
                                  ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  db container  —  postgres:16-alpine                             │
   │  · Database: ticket_db                                           │
   │  · Table: tickets (auto-created by SQLAlchemy on backend start)  │
   │  · Volume: pgdata (named Docker volume, survives container       │
   │    restarts so tickets aren't lost)                              │
   └──────────────────────────────────────────────────────────────────┘
```

All three services share a single Docker Compose **bridge network**
called `ticket-net`. Containers find each other by service name
(`db`, `backend`, `frontend`) thanks to Docker's embedded DNS — no IP
addresses are hard-coded anywhere.

---

## 3. Feature inventory

The product spec defines five user-facing features. Each is implemented
end-to-end and is verifiable from the running system.

| # | Feature           | What the user sees                                | Where it's implemented                                                                                  |
| - | ----------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| 1 | Submit a ticket   | Form with title, message, optional category       | `frontend/src/App.jsx` (form UI), `frontend/src/api.js` (POST), `backend/app/main.py` (`POST /tickets`)  |
| 2 | Analyze sentiment | A `POSITIVE` / `NEGATIVE` label + confidence %    | `backend/app/sentiment.py` (DistilBERT SST-2 inference)                                                 |
| 3 | Persist ticket    | Tickets survive page refresh and container restart | `backend/app/models.py` (ORM), `backend/app/database.py` (engine), Postgres named volume `pgdata`       |
| 4 | View tickets      | A list of all tickets, newest first               | `frontend/src/App.jsx` (list UI), `backend/app/main.py` (`GET /tickets`)                                |
| 5 | Health check      | A simple `/health` endpoint                       | `backend/app/main.py` (`GET /health`), `frontend/nginx.conf` (proxied at `/api/health`)                 |

In addition, the implementation includes three infrastructure features
that the PRD requires for the live demo:

| Infra feature                       | Why it matters                                                                                                  | Where it lives                                          |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Model weights baked into image**  | First demo request is fast; container can run with no internet to `huggingface.co`                              | `backend/Dockerfile` (RUN step that calls `from_pretrained`) |
| **Nginx reverse proxy for /api**    | Browser only ever talks to port 3000, so no CORS configuration is needed; same image works on localhost and VM   | `frontend/nginx.conf`                                    |
| **Postgres healthcheck + depends_on** | Backend waits for Postgres to be ready, so the app doesn't crash on cold boot                                | `docker-compose.yml` (services.db.healthcheck)           |

---

## 4. Request walkthroughs

### 4.1 Submitting a ticket

The user types "My lab VM is not opening before the deadline." into the
form and clicks **Submit ticket**. Here is exactly what happens, step by
step:

```
Browser
  │
  │  1. fetch("/api/tickets", { method:"POST", body: { title, message, category } })
  ▼
Nginx (frontend container, port 3000)
  │
  │  2. Sees URL matches location /api/
  │  3. Strips /api prefix and proxies to http://backend:8000/tickets
  ▼
FastAPI (backend container, port 8000)
  │
  │  4. Pydantic validates the JSON body against TicketCreate schema
  │     (title: str required, message: str required, category: Optional[str])
  │
  │  5. Calls sentiment.analyze(payload.message)
  │     a. Tokenizer converts text → input_ids tensor (max 512 tokens)
  │     b. DistilBERT model runs forward pass → logits
  │     c. softmax(logits) → probabilities
  │     d. argmax → label index (0 = NEGATIVE, 1 = POSITIVE for SST-2)
  │     e. Lookup id2label → "POSITIVE" or "NEGATIVE"
  │     f. Defensive LABEL_0/1 → POSITIVE/NEGATIVE fixup (satisfies dry-run)
  │     Returns (label, confidence)
  │
  │  6. INSERT INTO tickets (title, message, category, sentiment, confidence)
  │     VALUES (...)
  │
  │  7. SQLAlchemy refreshes the row (populates id + created_at)
  │
  │  8. Pydantic serializes the ORM row → TicketOut JSON
  ▼
Browser
  │
  │  9. setTickets(newTicket) appends to the list, UI re-renders
```

For the example above, the response was:

```json
{
  "id": 1,
  "title": "Lab VM issue",
  "message": "My lab VM is not opening before the deadline.",
  "category": "lab",
  "sentiment": "NEGATIVE",
  "confidence": 0.987,
  "created_at": "2026-06-25T18:30:18.386524Z"
}
```

The `created_at` timestamp is generated by Postgres itself
(`server_default=func.now()`) so it is consistent across all rows
regardless of which FastAPI worker wrote them.

### 4.2 Listing tickets

```
Browser mount  →  App.jsx useEffect(() => { refresh() }, [])
  │
  │  fetch("/api/tickets")
  ▼
Nginx  →  FastAPI GET /tickets
  │
  │  SELECT * FROM tickets ORDER BY created_at DESC, id DESC
  ▼
Browser renders <ul className="ticket-list"> with color-coded sentiment badges
```

The double sort key (`created_at DESC, id DESC`) guarantees a stable
order even if two tickets somehow share a timestamp — newer IDs win.

### 4.3 Health check

```
curl http://localhost:3000/api/health
  → Nginx  →  FastAPI GET /health
  → {"status":"ok"}
```

The frontend Nginx exposes this at the same path so a Docker
`HEALTHCHECK` defined in either container can probe via the same route.

---

## 5. The AI integration

The "AI" part of the demo is intentionally small but real — it uses the
same model the production-grade Hugging Face pipeline uses.

### 5.1 The model

- **Name:** `distilbert-base-uncased-finetuned-sst-2-english`
- **Type:** DistilBERT (a 6-layer, 66 M-parameter distilled version of
  BERT) fine-tuned on the Stanford Sentiment Treebank v2 (SST-2).
- **Task:** Binary sentiment classification.
- **Output:** `POSITIVE` or `NEGATIVE` with a softmax confidence score.
- **Why this model:** Small enough to download in ~30 seconds, accurate
  enough for English text, and a canonical example in the Transformers
  documentation.

### 5.2 Where the model lives

The model weights are **baked into the backend Docker image**, not
downloaded at runtime. This is enforced in three places:

1. **Dockerfile build step** (writes the weights into the image):
   ```dockerfile
   ENV HF_HOME=/opt/hf-cache
   RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
       AutoTokenizer.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english'); \
       AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased-finetuned-sst-2-english')"
   ```
2. **Runtime env var** that disables network access:
   ```dockerfile
   ENV TRANSFORMERS_OFFLINE=1
   ```
3. **Backend code** that imports the model at module load time (so a
   missing weights file fails loudly at container start, not on the
   first user request):
   ```python
   _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
   _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
   ```

### 5.3 Why CPU-only torch?

The default PyPI `torch` wheel is **CUDA-enabled and ~2 GB**. For a
sentiment analysis demo that runs on a tiny VM, that's wasted disk and
memory. The Dockerfile installs torch from the CPU-only index:

```dockerfile
RUN pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.4.1
```

The resulting backend image is **~688 MB** instead of 2.5 GB.

### 5.4 Inference path (per request)

```python
def analyze(text: str) -> tuple[str, float]:
    inputs  = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = _model(**inputs)                              # ~50 ms on CPU
    probs   = outputs.logits.softmax(dim=-1).detach().tolist()[0]
    idx     = int(max(range(len(probs)), key=lambda i: probs[i]))
    raw     = _model.config.id2label[idx]                  # "POSITIVE" or "NEGATIVE"
    label   = _LABEL_FIXUP.get(raw, raw)                   # safety net
    conf    = float(probs[idx])
    return label, conf
```

`_model.eval()` is called once at import time so the model is in
inference mode (disables dropout) for every request.

---

## 6. Frontend deep-dive

The frontend is intentionally tiny: a single React page with a form,
a ticket list, and minimal styling. No router, no state library, no UI
framework. The whole production bundle is ~74 KB of JavaScript.

### 6.1 Build pipeline

```
src/main.jsx  +  src/App.jsx  +  src/api.js  +  src/styles.css
                       │
                       │  vite build (production mode)
                       ▼
               dist/
                 ├── index.html
                 └── assets/
                       ├── index-XXXXXX.js     (React + app code, minified)
                       └── index-XXXXXX.css    (extracted CSS, minified)
```

`VITE_API_BASE_URL` is read at build time and injected as
`import.meta.env.VITE_API_BASE_URL`. The default is `/api`, which is
exactly the path the frontend Nginx expects to reverse-proxy.

### 6.2 Nginx config

```nginx
server {
    listen 3000;
    root /usr/share/nginx/html;

    # Reverse proxy /api/* → http://backend:8000/*
    # The trailing slash on proxy_pass strips the /api prefix so:
    #   /api/tickets → http://backend:8000/tickets
    #   /api/health  → http://backend:8000/health
    location /api/ {
        proxy_pass http://backend:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Static SPA assets (with fallback to index.html for SPA routing).
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

This is the key trick that lets the same image work on localhost and on
the Poridhi VM with zero configuration: the browser only ever opens a
connection to the same origin (port 3000), so CORS is never an issue.

---

## 7. Database

### 7.1 Schema

```sql
CREATE TABLE tickets (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR       NOT NULL,
    message     TEXT          NOT NULL,
    category    VARCHAR,                         -- nullable
    sentiment   VARCHAR       NOT NULL,          -- "POSITIVE" or "NEGATIVE"
    confidence  FLOAT         NOT NULL,          -- 0.0 - 1.0
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
```

The table is created automatically by
`Base.metadata.create_all(engine)` in `backend/app/main.py` — the very
first time the backend starts against a fresh Postgres volume. **No
manual migrations are required**, which is one of the workshop's
acceptance criteria.

### 7.2 Persistence

The Postgres container mounts a named Docker volume called `pgdata`
at `/var/lib/postgresql/data`. As long as that volume exists, tickets
survive `docker compose down` (without `-v`) and even `docker rm`
of the db container. Only `docker compose down -v` destroys data.

---

## 8. Docker orchestration

### 8.1 Local compose (`docker-compose.yml`)

Builds both images from source. Used during development and on the VM
when you want to test the full build chain.

```
services:
  db        ←  postgres:16-alpine (pulled from Docker Hub)
  backend   ←  built from ./backend (with HF weights baked in)
  frontend  ←  built from ./frontend (Vite build → Nginx)
```

**Startup ordering:**

```
db   starts → healthcheck passes  → backend starts
                                  → frontend starts
```

This ordering is enforced by `depends_on: db: { condition: service_healthy }`
so the backend never tries to connect to a half-initialized database.

### 8.2 VM compose (`docker-compose.vm.yml`)

Same shape as the local compose, but `backend` and `frontend` use
`image:` references instead of `build:`. The images are pulled from
your DockerHub account:

```yaml
backend:
  image: ${DOCKERHUB_USER:-<dockerhub-username>}/ticket-analyzer-backend:v1
frontend:
  image: ${DOCKERHUB_USER:-<dockerhub-username>}/ticket-analyzer-frontend:v1
```

On the VM you set `DOCKERHUB_USER=musfiqueahmed` and Docker pulls the
two pre-built images (688 MB + 21 MB). Total deploy time: ~10 seconds
on a fast link, vs ~5 minutes for a full source build.

### 8.3 Image naming convention

```
<dockerhub-username>/ticket-analyzer-backend:v1
<dockerhub-username>/ticket-analyzer-frontend:v1
```

The `:v1` tag makes it easy to push newer versions later (`:v2`,
`:v3`) and roll back by editing the compose file.

---

## 9. End-to-end demo flow

This is the sequence you'd walk through during the workshop to prove
the system works:

| # | Action                                                          | What it proves                                              |
| - | --------------------------------------------------------------- | ----------------------------------------------------------- |
| 1 | `docker compose up --build` on the VM                           | App builds and starts locally                               |
| 2 | Open `http://<vm-ip>:3000` in any browser on the network        | Frontend is reachable cross-host via Nginx reverse proxy    |
| 3 | Submit a ticket with negative text                              | HF model returns `NEGATIVE` with high confidence            |
| 4 | Submit a ticket with positive text                              | HF model returns `POSITIVE` with high confidence            |
| 5 | Refresh the page                                                | Tickets are still there (Postgres persistence works)        |
| 6 | `curl http://<vm-ip>:3000/api/tickets`                          | JSON list returns tickets newest-first with correct labels   |
| 7 | `docker compose down -v && docker compose up -d` then re-submit | Table auto-created, new ticket saved — no manual migration  |
| 8 | `docker run --network=none ...backend:v1 python -c ...`         | Container starts and runs inference without internet access |

Steps 7 and 8 are the **dry-run acceptance criteria** from the PRD —
they prove the image is self-contained and ready for production
deployment.

---

## 10. File-by-file reference

### Backend (Python)

| File                       | Responsibility                                                       |
| -------------------------- | -------------------------------------------------------------------- |
| `app/__init__.py`          | Empty marker — makes `app` a Python package                          |
| `app/database.py`          | SQLAlchemy engine, `SessionLocal`, `Base`, `get_db` dependency        |
| `app/models.py`            | `Ticket` ORM class — one table, seven columns                        |
| `app/schemas.py`           | Pydantic `TicketCreate` (input) and `TicketOut` (output) models      |
| `app/sentiment.py`         | Loads tokenizer + model at import time; `analyze()` function         |
| `app/main.py`              | FastAPI app, routes, CORS, `create_all` on startup, imports sentiment |
| `requirements.txt`         | Pinned Python deps (no torch — installed in Dockerfile)              |
| `Dockerfile`               | Multi-step: install CPU torch → deps → bake HF weights → app code    |

### Frontend (JavaScript / React)

| File                  | Responsibility                                                       |
| --------------------- | -------------------------------------------------------------------- |
| `package.json`        | Dependencies and npm scripts                                         |
| `vite.config.js`      | Vite + React plugin                                                  |
| `index.html`          | Single HTML page that mounts the React app                          |
| `src/main.jsx`        | ReactDOM root, mounts `<App />`                                      |
| `src/App.jsx`         | Form + ticket list UI + fetch wrappers                              |
| `src/api.js`          | `submitTicket()`, `listTickets()` using `VITE_API_BASE_URL`          |
| `src/styles.css`      | Single stylesheet — no UI framework                                  |
| `Dockerfile`          | Multi-stage: Node build → Nginx serve                                |
| `nginx.conf`          | Serves static + reverse-proxies `/api/*` to backend                  |

### Repo root

| File                       | Purpose                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `PRD.md`                   | The authoritative spec — single source of truth                      |
| `README.md`                | Quick-start commands for local + VM                                  |
| `ARCHITECTURE.md`          | This document                                                        |
| `docker-compose.yml`       | Local dev: builds from source                                        |
| `docker-compose.vm.yml`    | VM deploy: pulls pre-built images from DockerHub                     |
| `.gitignore`               | Standard Python + Node ignores                                       |

---

## 11. Key design decisions (and why)

| Decision                                                  | Why                                                                                                                                  |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Model loaded at module import, not lazily per request     | PRD §9 requires first demo request to be fast; guarantees weights are in memory before serving traffic                                |
| `TRANSFORMERS_OFFLINE=1` in runtime env                   | Makes missing weights fail loudly at startup instead of silently downloading at the worst possible time (during a live demo)         |
| CPU-only torch via dedicated index URL                    | Cuts backend image from ~2.5 GB to ~688 MB                                                                                           |
| Nginx reverse proxy instead of FastAPI CORS only          | Same image works on localhost and VM with zero config; browser only ever sees one origin                                              |
| Postgres healthcheck + `depends_on: condition: service_healthy` | Prevents backend crash on cold boot when DB is still initializing                                                                |
| `Base.metadata.create_all` on startup                     | Removes the need for a migration step in a minimal demo; fresh volume just works                                                     |
| `sentiment.py` defensive `LABEL_0/1 → POSITIVE/NEGATIVE` mapping | Even though SST-2 already returns the right labels, the mapping makes the dry-run acceptance criterion verifiable if anyone swaps in a different checkpoint |
| CORS middleware enabled anyway                            | Costs nothing, lets local testing work even if the reverse-proxy path is misconfigured                                                |
| ORM with `created_at` set by DB default                   | Avoids clock-skew issues across containers and gives consistent timestamps regardless of which worker handled the insert             |
| Named Docker volume for Postgres                          | Survives container restarts and even `docker rm` — only `down -v` destroys data                                                        |

---

## 12. Known limitations & out-of-scope items

These are explicitly out of scope per the PRD and have not been built:

- Authentication / user accounts
- Dashboard, charts, analytics
- Service layers, repositories, dependency injection frameworks
- Model fine-tuning, prompt engineering, LLM agents
- Database migrations, schema versioning
- Kubernetes manifests, CI/CD pipelines
- HTTPS / TLS termination (assumed handled by an external proxy)

The product is intentionally a **minimum end-to-end demo** of the
engineering path, not a feature-complete SaaS product.
