# FeedbackIQ — AI-Powered Customer Feedback & Support Ticket Analyzer

A proof-of-concept that ingests customer messages, filters out non-qualifying ones (spam, greetings, promotions), classifies the rest, and stores structured results in SQLite with CSV/JSON export.

**Stack:** Python 3.11+ · FastAPI · SQLAlchemy · SQLite · React + Vite · optional Google Gemini

---

## How it works

```
 CSV / JSON / UI / API  ──►  Filter  ──►  Analyze  ──►  SQLite  ──►  Dashboard + CSV/JSON export
                              │             │
                       rejected (reason)    Gemini (if key set)
                       not stored           └─ falls back to rule-based engine
```

1. **Ingestion** – Read a local CSV or JSON file, submit a single message or batch through the API, or upload a file in the web UI (max 2 MB / 100 messages per request).
2. **Filtering** (`app/services/filtering.py`) – Rejects empty messages, standalone greetings and pleasantries (e.g. "Hello, hope you are having a nice day!"), and promotional/spam text (e.g. "Buy now! 50% off!"). A greeting followed by a real request ("Hi team, please add dark mode…") is still accepted. Rejected messages are reported with a reason and are **not** stored.
3. **Analysis** (`app/services/analyzer.py`) – Each valid message gets:

   | Field | Values |
   |---|---|
   | Category | Bug Report · Feature Request · Billing Issue · General Inquiry |
   | Priority | Low · Medium · High · Urgent |
   | Sentiment | Positive · Neutral · Negative |
   | Product / feature | Main product or feature mentioned (e.g. "Checkout") |
   | Suggested reply | Short, polite draft for an agent to review |

   - **Default (no API key):** transparent keyword/rule-based classifier with category-specific reply templates. Runs offline.
   - **AI mode:** if `GEMINI_API_KEY` is set, Gemini returns schema-validated JSON (enum-constrained category/priority/sentiment; the prompt treats the customer message as data, not instructions). Any API failure or invalid response automatically falls back to the rule-based engine, so intake never breaks.
4. **Storage & output** – Accepted tickets are saved to SQLite (`customer_feedback.db`). Results can be exported as CSV/JSON from the dashboard or API, and the sample script writes `outputs/sample_output.{csv,json}`.
5. **Auth** – Signup/login with hashed passwords and bearer tokens protect the ticket endpoints.

---

## Quick start

### Fastest check (no server, no API key)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/process_sample.py
```

Reads `sample_feedback.csv` and writes `outputs/sample_output.csv` and `outputs/sample_output.json`.

### Full app

**Backend** (project root):

```bash
cp .env.example .env               # Windows: copy .env.example .env
# edit .env: set AUTH_SECRET to a long random string
uvicorn app.main:app --reload
```

API: <http://127.0.0.1:8000> · Swagger docs: <http://127.0.0.1:8000/docs>

**Frontend** (second terminal):

```bash
cd frontend
cp .env.example .env               # Windows: copy .env.example .env
npm install
npm run dev
```

Open <http://localhost:5173>, create an account, then use **Analyze feedback** (single message or CSV/JSON upload).

### Configuration (`.env`)

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL | `sqlite:///./customer_feedback.db` |
| `AUTH_SECRET` | Token signing secret — **change it** | placeholder |
| `TOKEN_TTL_SECONDS` | Token lifetime | `86400` |
| `CORS_ORIGINS` | Allowed frontend origins | `http://localhost:5173,http://127.0.0.1:5173` |
| `GEMINI_API_KEY` | Optional; enables AI analysis | empty (rule-based) |
| `GEMINI_MODEL` | Gemini model name | set to a model available on your account |

---

## Input formats

**CSV** – needs a `message` column; other columns are ignored.

```csv
message
"The payment page crashes on checkout. Please fix ASAP!"
"Hello!"
```

**JSON** – array of strings, array of `{"message": ...}` objects, or `{"messages": [...]}` (see `samples/sample_feedback.json`).

---

## Sample results

Produced by `python scripts/process_sample.py` (rule-based mode). The first three rows are the assessment's test tickets:

| # | Message | Result |
|---|---|---|
| 1 | "The payment page crashes every time I click 'Checkout' on Chrome. Please fix this ASAP!" | **Bug Report · Urgent · Negative** · Checkout |
| 2 | "Hi team, it would be awesome if you could add a dark mode to the mobile app." | **Feature Request · Medium · Positive** · Dark Mode |
| 3 | "Hello, hope you are having a nice day!" | **Ignored** – greeting/pleasantry |
| 4 | "Buy now! Limited time offer! Get 50% off today!" | **Ignored** – promotional/spam |
| 5 | "I was charged twice for my monthly subscription and need a refund." | **Billing Issue · High · Negative** · Subscription |

All three expected outcomes from the assessment match. Full output with suggested replies: [`outputs/sample_output.csv`](outputs/sample_output.csv), [`outputs/sample_output.json`](outputs/sample_output.json).

---

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/signup`, `/auth/login` | Create account / get bearer token |
| GET | `/auth/me` | Current user |
| POST | `/tickets/analyze` | Analyze one message |
| POST | `/tickets/batch` | Analyze up to 100 messages |
| POST | `/tickets/import/csv`, `/tickets/import/json` | Multipart upload, field name `file` |
| GET | `/tickets`, `/tickets/{id}` | List (search/filter) / fetch tickets |
| PATCH / DELETE | `/tickets/{id}` | Update status / delete |
| GET | `/analytics`, `/activity` | Aggregates and activity history |
| GET | `/tickets/export/csv`, `/tickets/export/json` | Export stored tickets |
| GET | `/health` | Health check |

Ticket endpoints require `Authorization: Bearer <token>`.

---

## Project structure

```
app/
  main.py              FastAPI routes
  schemas.py           Pydantic models
  db/                  SQLAlchemy engine and models
  services/
    filtering.py       Spam / greeting / promo filter
    analyzer.py        Rule-based + Gemini analysis
    auth.py            Password hashing, tokens
frontend/              React + Vite dashboard
scripts/process_sample.py   Offline sample run
samples/, sample_feedback.csv   Test input
outputs/               Sample structured output
tests/                 46 pytest tests
```

## Tests

```bash
pytest -q        # 46 passed
```

Covers the analyzer, filtering rules, edge cases, and the API.

---

## Limitations

- The default classifier is keyword-based: it is transparent and fast, but can misjudge sarcasm, mixed intent, or unusual wording. AI mode improves this but is not infallible.
- The spam filter uses a fixed phrase/pattern list, not a trained model.
- Suggested replies are drafts and should be reviewed by a person before sending.
- Designed as a PoC: SQLite, single-process, no rate limiting or email integration.

## Possible next steps

Multilingual support, a trained spam classifier, duplicate-ticket detection, PostgreSQL, and helpdesk integrations (Zendesk, Freshdesk).
