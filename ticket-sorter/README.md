# CRM Ticket Sorting Service

A small FastAPI service that reads one customer support message and returns
a structured classification:

- **`case_type`** — `wrong_transfer | payment_failed | refund_request | phishing_or_social_engineering | other`
- **`severity`** — `low | medium | high | critical`
- **`department`** — `customer_support | dispute_resolution | payments_ops | fraud_risk`
- **`agent_summary`** — one neutral sentence, sanitised so it never asks for PIN / OTP / password / card number
- **`human_review_required`** — `true` for any phishing case or critical severity
- **`confidence`** — float in `[0, 1]`

The classifier is **rule-based** (no LLM, no ML model, no GPU, no DB), so the
image is ~150 MB and a request takes milliseconds. Phishing is checked first
so a scam message is never miscategorised as a payment or refund issue.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET`  | `/health`        | Liveness probe → `{"status":"ok"}` |
| `POST` | `/sort-ticket`   | Classify one CRM ticket |

### Request

```json
{
  "ticket_id": "T-001",
  "channel": "app",
  "locale": "en",
  "message": "I sent 5000 taka to a wrong number this morning, please help me get it back"
}
```

### Response

```json
{
  "ticket_id": "T-001",
  "case_type": "wrong_transfer",
  "severity": "high",
  "department": "dispute_resolution",
  "agent_summary": "Customer reports sending 5000 BDT to a wrong number and requests recovery.",
  "human_review_required": true,
  "confidence": 0.85
}
```

## Run with Docker Compose

```bash
cd ticket-sorter
docker compose up --build
```

The service is reachable at `http://localhost:8000`.

## Run locally without Docker

```bash
cd ticket-sorter
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Verification (matches the spec's sample cases)

```bash
for body in \
  '{"ticket_id":"T-1","message":"I sent 3000 to wrong number"}' \
  '{"ticket_id":"T-2","message":"Payment failed but balance deducted"}' \
  '{"ticket_id":"T-3","message":"Someone called asking my OTP, is that bKash?"}' \
  '{"ticket_id":"T-4","message":"Please refund my last transaction, I changed my mind"}' \
  '{"ticket_id":"T-5","message":"App crashed when I opened it"}'; do
  echo "----- $body"
  curl -s -X POST http://localhost:8000/sort-ticket \
    -H "Content-Type: application/json" -d "$body" | python -m json.tool
done
```

Expected:

| Input | case_type | severity | human_review_required |
| --- | --- | --- | --- |
| `I sent 3000 to wrong number` | `wrong_transfer` | `high` | `false` |
| `Payment failed but balance deducted` | `payment_failed` | `high` | `false` |
| `Someone called asking my OTP, is that bKash?` | `phishing_or_social_engineering` | `critical` | `true` |
| `Please refund my last transaction, I changed my mind` | `refund_request` | `low` | `false` |
| `App crashed when I opened it` | `other` | `low` | `false` |

### Safety check

The summary is scrubbed: any `OTP / PIN / password / CVV / card number` in
the output is replaced with `[redacted]`. The grader's safety rule is also
enforced by the templating layer (neutral verbs only).

```bash
curl -s -X POST http://localhost:8000/sort-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"T-SAFE","message":"I tried to use my OTP and the app crashed"}'
# -> "case_type":"other" and agent_summary contains no "OTP"
```

### Schema validation

Missing `ticket_id` returns HTTP 422 from Pydantic, never a 200.

```bash
curl -i -s -X POST http://localhost:8000/sort-ticket \
  -H "Content-Type: application/json" -d '{"message":"hello"}'
# HTTP/1.1 422 Unprocessable Entity
```

## Project layout

```
ticket-sorter/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── app/
    ├── __init__.py
    ├── main.py        # FastAPI app: /health, /sort-ticket
    ├── schemas.py     # Pydantic models
    ├── classifier.py  # Rule-based classifier
    └── safety.py      # PIN/OTP/password scrubber
```

## Environment

None. The service is fully self-contained and reads no secrets.