*The following is the original minimal Product Requirement Document. It is the authoritative specification for what you build in the tasks above.*

**Product Requirement Document**

**Ticket Analyzer**

*Minimal full-stack engineering demo*

| Field | Detail |
| :---- | :---- |
| Workshop | FDE Capability Buildup |
| Demo Goal | Build locally, containerize, push, and deploy on Poridhi Lab VM |
| Core Stack | React/Vite, FastAPI, tiny Hugging Face model, PostgreSQL, Docker Compose |
| Scope | Minimal live demo focused on workflow, not feature depth |

## **1\. Product Overview**

Ticket Analyzer is a small full-stack application that accepts a support ticket, analyzes its sentiment using a tiny Hugging Face model, stores the ticket in PostgreSQL, and shows the ticket history in a simple frontend.

The purpose is to demonstrate the complete engineering path: PRD, frontend, backend, AI model integration, database persistence, Docker images, DockerHub, GitHub, and deployment on a Poridhi Lab VM.

## **2\. Demo Objective**

* Turn a PRD into a working full-stack application using Puku Editor.

* Use Puku CLI for local testing, Docker debugging, and deployment commands.

* Containerize the frontend and backend separately.

* Push source code to GitHub and images to DockerHub.

* Deploy the same application on a Poridhi Lab VM using Docker Compose.

## **3\. Minimal Scope**

| Area | Included | Not Included |
| :---- | :---- | :---- |
| Frontend | One page form and ticket list | Authentication, dashboard |
| Backend | Three API endpoints | Complex service layers |
| AI | Tiny sentiment model | Fine-tuning or LLM agents |
| Database | PostgreSQL persistence | Migrations or analytics |
| Deployment | Docker Compose on VM | Kubernetes or CI/CD |

## **4\. User Flow**

1. User opens the Ticket Analyzer frontend.

2. User enters a ticket title, message, and optional category.

3. Frontend sends the ticket to the FastAPI backend.

4. Backend runs sentiment analysis using the tiny model.

5. Backend saves the result in PostgreSQL.

6. Frontend refreshes the ticket list.

## **5\. Features**

| Feature | Requirement |
| :---- | :---- |
| Submit ticket | User can submit title, message, and optional category. |
| Analyze ticket | Backend returns sentiment label and confidence score. |
| Persist ticket | Every ticket is saved in PostgreSQL. |
| View tickets | Frontend displays latest saved tickets. |
| Health check | Backend exposes GET /health. |

## **6\. Architecture**

React Frontend  
    \-\> FastAPI Backend  
        \-\> Tiny Hugging Face Sentiment Model  
        \-\> PostgreSQL Database

* frontend: React production build served by Nginx on port 3000\.

* backend: FastAPI served by Uvicorn on port 8000\.

* db: PostgreSQL with a named Docker volume for persistence.

## **7\. API Requirements**

| Method | Endpoint | Purpose |
| :---- | :---- | :---- |
| GET | /health | Return backend status. |
| POST | /tickets | Create ticket and analyze sentiment. |
| GET | /tickets | List saved tickets. |

### **Example Request**

POST /tickets  
{  
  "title": "Lab VM issue",  
  "message": "My lab VM is not opening before the deadline.",  
  "category": "lab"  
}

### **Example Response**

{  
  "id": 1,  
  "title": "Lab VM issue",  
  "sentiment": "NEGATIVE",  
  "confidence": 0.999,  
  "created\_at": "2026-05-20T10:30:00"  
}

## **8\. Data Model**

| Field | Type | Notes |
| :---- | :---- | :---- |
| id | integer | Primary key |
| title | string | Ticket title |
| message | text | Ticket body |
| category | string | Optional category |
| sentiment | string | Model output label |
| confidence | float | Model confidence score |
| created\_at | timestamp | Created by backend |

## **9\. AI Model Requirement**

Use a very small Hugging Face sentiment classification model for the live demo. Suggested model:

distilbert-base-uncased-finetuned-sst-2-english

* Download model weights during Docker build, not at runtime. The backend Dockerfile must include a step that runs from\_pretrained() so the weights are baked into the image.

* Pin the HuggingFace cache directory with HF\_HOME and set TRANSFORMERS\_OFFLINE=1 at runtime so the container fails loudly during dry-run if weights are not present, instead of silently downloading on stage.

* Load the model into memory once at backend startup (not lazily on the first request) so the first ticket submission during the demo is fast.

* Use the model only to demonstrate AI integration inside a real app.

* Pre-build and push the backend image (with weights baked in) to DockerHub before the session.

## **10\. Repository Structure**

ticket-analyzer/  
├── PRD.md  
├── README.md  
├── docker-compose.yml  
├── backend/  
│   ├── Dockerfile  
│   └── app/  
└── frontend/  
    ├── Dockerfile  
    └── src/

## **11\. Environment Variables**

| Service | Variable | Example |
| :---- | :---- | :---- |
| backend | DATABASE\_URL | postgresql://postgres:postgres@db:5432/ticket\_db |
| backend | MODEL\_NAME | distilbert-base-uncased-finetuned-sst-2-english |
| backend | HF\_HOME | /opt/hf-cache |
| backend | TRANSFORMERS\_OFFLINE | 1 |
| frontend | VITE\_API\_BASE\_URL | /api  (Nginx in the frontend container reverse-proxies /api to the backend service) |

## **12\. Docker and Deployment Requirements**

* Backend image: \<dockerhub-username\>/ticket-analyzer-backend:v1

* Frontend image: \<dockerhub-username\>/ticket-analyzer-frontend:v1

* Database image: official postgres image

* Local command: docker compose up \--build

* Lab VM command: docker compose up \-d using DockerHub images

* Backend Dockerfile installs torch from the CPU-only index (--index-url https://download.pytorch.org/whl/cpu) to keep the image around 600-800 MB instead of 2+ GB.

* Backend Dockerfile bakes the model weights into the image using from\_pretrained() during build, with HF\_HOME set so the runtime container finds the cache.

* Backend creates the tickets table on startup via SQLAlchemy Base.metadata.create\_all(engine) so a fresh Postgres volume works without manual migrations.

* docker-compose.yml uses depends\_on with a Postgres healthcheck so the backend waits for the database to be ready before starting (prevents connection-refused crashes on cold boot).

* Frontend Nginx reverse-proxies /api to the backend service on the internal Docker network. This removes the need for CORS configuration and lets the same image work on localhost and on the Poridhi Lab VM without rebuilding.

* If a direct cross-origin setup is used instead of the reverse proxy, the backend must enable FastAPI CORSMiddleware allowing the frontend origin.

## **13\. Acceptance Criteria**

* Frontend opens successfully.

* GET /health returns status ok.

* User can submit a ticket from the frontend.

* Backend analyzes ticket sentiment.

* Ticket is saved in PostgreSQL.

* Refreshing the page still shows saved tickets.

* Images are pushed to DockerHub and code is pushed to GitHub.

* Application runs successfully on the Poridhi Lab VM.

* Dry-run: backend container starts with no network access to huggingface.co (proves model weights are baked into the image, not downloaded at runtime).

* Dry-run: with a fresh Postgres volume, the tickets table is created automatically on first start and POST /tickets succeeds.

* Dry-run: frontend successfully submits a ticket from a browser that is not on the VM’s localhost (validates the reverse-proxy / API base URL setup).

* Dry-run: sentiment output uses POSITIVE/NEGATIVE labels (not LABEL\_0/LABEL\_1), confirming the real distilbert-sst-2 model is being used.

*Ticket Analyzer PRD  |  Minimal AI Engineering Workshop Demo*