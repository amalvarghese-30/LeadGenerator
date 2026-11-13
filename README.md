# LeadIntel CRM: Provider Intelligence & CRM Lead Discovery Platform

**LeadIntel CRM** is a production-ready, full-stack intelligence and CRM platform engineered to discover, crawl, analyze, extract, qualify, and manage business prospects derived from digital presence service providers (such as personal branding agencies, Google Knowledge Panel creators, and Entity SEO specialists).

The platform takes an initial reference company—such as **[The Person](https://theperson.in/)**—and discovers related service providers, crawls their public web properties, extracts publicly disclosed client case studies and testimonials, maps the associated companies and decision-makers (Founders, CEOs, Directors), and generates structured, evidence-backed CRM leads.

---

## 🏗️ Architecture & Technology Stack

```
                          ┌─────────────────────────┐
                          │   React 19 + Vite 8     │
                          │ TypeScript + Tailwind 4 │
                          └────────────┬────────────┘
                                       │ (REST /api)
                                       ▼
                          ┌─────────────────────────┐
                          │      FastAPI App        │
                          │ (Auth, CRM, Discovery)  │
                          └────┬───────────────┬────┘
                               │               │
        ┌──────────────────────┼───────────┐   │
        │                      │           │   ▼
        ▼                      ▼           ▼ ┌─────────────────────────┐
┌──────────────┐     ┌──────────────┐      │ │   MongoDB (Replica/DB)  │
│ DDGS Search  │     │ Web Crawler  │      │ │ 10+ Indexed Collections │
│ (Zero Paid)  │     │ (SSRF-Safe)  │      │ └─────────────────────────┘
└──────────────┘     └──────────────┘      │               ▲
        │                      │           │               │
        └──────────────┬───────┘           │               │
                       ▼                   │               │
             ┌──────────────────┐          │               │
             │ AI / NLP Engine  │          ▼               │
             │(Nemotron / spaCy)│   ┌─────────────────────┐│
             └─────────┬────────┘   │ Background Worker & ││
                       │            │ APScheduler Service ├┘
                       └───────────►│ (Distributed Lock)  │
                                    └─────────────────────┘
```

### Technology Highlights

- **Backend**: Python 3.11+ / FastAPI, Pydantic v2, Motor / PyMongo, Trafilatura, BeautifulSoup4, spaCy, APScheduler.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons, Recharts, React Router v6.
- **Database**: MongoDB with comprehensive compound & unique indexes.
- **Discovery**: Zero-paid-API search via `ddgs`, robots.txt parsing, sitemaps, RSS feeds, internal BFS crawler, WordPress REST CMS discovery, Common Crawl, and Internet Archive Wayback Machine.
- **Security**: Strict SSRF protection (private/loopback/cloud metadata IP blocking), password hashing with bcrypt, JWT authentication (access + refresh tokens), rate limiting, and Excel/CSV formula injection defense.
- **AI/NLP**: Optional NVIDIA Nemotron (NIM) inference with prompt injection sanitization and deterministic fallback via spaCy / heuristic NER. Hallucinated email detection guarantees zero guessed emails.

---

## 🚀 Quick Start (Docker Compose)

The easiest way to run the entire stack (MongoDB, FastAPI backend, background worker, and React frontend) is using Docker Compose:

```bash
# 1. Clone or navigate to the project directory
cd CRM

# 2. Copy the environment variables
cp .env.example .env

# 3. Launch all services
docker-compose up --build -d
```

Once running:
- **Frontend CRM UI**: [http://localhost](http://localhost) (or [http://localhost:5173](http://localhost:5173) in local dev)
- **Backend API & Swagger Docs**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 💻 Local Development Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11 - 3.14)
- Node.js 18+ (tested on Node.js 20+)
- MongoDB running locally on `localhost:27017`

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database indexes and seed data (seeds theperson.in + sample leads)
python -m app.database.seed

# Start backend dev server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server with proxy to port 8000
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🔑 Default Credentials & Seed Data

The database seeder (`app.database.seed`) automatically initializes:

- **Admin Account**:
  - Email: `admin@leadintel.local`
  - Password: `Admin@123456`
- **Initial Reference Provider**:
  - `The Person` ([https://theperson.in/](https://theperson.in/)) - Seeded with 10 core service categories, social links, contact channels, and sample client references.
- **Discovered Leads**:
  - Sample prospects in various pipeline stages (`proposal_sent`, `meeting_scheduled`, `contacted`, `discovered`) with full evidence quotes, confidence scores, and calculated lead scores (0-100).

---

## 🌟 Core Modules & Features

### 1. Multi-Source Discovery Engine (Zero Paid Search APIs)
- **DDGS Search**: Programmatic multi-query execution across provider categories without paid search API keys.
- **Direct Domain Crawl**: Automatically pulls and analyzes `robots.txt`, XML sitemaps, RSS/Atom feeds, and internal links up to configurable depth.
- **CMS Discovery**: Probes `/wp-json/wp/v2/` endpoints for public posts, case studies, and pages.
- **Archive Fallback**: Supports Wayback Machine and Common Crawl index queries.
- **Google Dorking Generator**: Generates targeted dorking operators for manual copy-paste research.
- **SSRF Defense**: Prevents crawlers from resolving to localhost, loopback (`127.0.0.1`), private networks (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), or cloud metadata (`169.254.169.254`).

### 2. AI & NLP Evidence Extraction
- **Reference Detection**: Identifies whether a page contains confirmed client case studies, testimonials, portfolio items, or guest features.
- **Named Entity Recognition**: Extracts professional names, designations, and company names.
- **Evidence Verification**: Every client reference requires a `source_url` and verbatim `evidence_quote`. Never defaults to "verified" without researcher review or source confirmation.
- **Strict Privacy**: Zero guessed or inferred emails. In accordance with ethical data boundaries, only explicitly published business contact channels are stored.
- **Prompt Injection Defense**: Sanitizes scraped text before passing to AI models; drops instructions attempting to alter verification status.

### 3. Comprehensive CRM Pipeline
- **12 CRM Stages**: `discovered` ➔ `profiled` ➔ `verified` ➔ `qualified` ➔ `contact_identified` ➔ `outreach_ready` ➔ `contacted` ➔ `in_dialogue` ➔ `meeting_scheduled` ➔ `proposal_sent` ➔ `won` / `lost` (or `disqualified` / `nurture`).
- **Interactive Kanban & Table Views**: Drag or click to advance leads, view score badges, and filter by stage, qualification, or provider.
- **0-100 Lead Scoring**: Deterministic multi-factor scoring based on target designation relevance (Founders/CEOs), company scale, client reference evidence strength, and published contact presence.
- **Activity & Task Management**: Full timeline tracking for emails, calls, notes, stage transitions, and follow-up reminders.
- **Suppression / Do-Not-Contact**: Opt-out support preventing outreach to suppressed contacts.

### 4. Formula-Injection Safe Exports & Reports
- **CSV & Excel Export**: All exported fields are sanitized against CSV/Excel formula injection (e.g., prepending `'` to entries starting with `=`, `+`, `-`, `@`, `|`, `%`).
- **Reports Dashboard**: Pipeline distribution charts, discovery volume metrics, provider breakdowns, and lead qualification conversion rates.

---

## 🧪 Running Automated Tests

Run the test suite from the `backend` directory:

```bash
cd backend
python -m pytest tests -v
```

### Verified Test Results (16/16 Passed):
- `tests/test_auth.py`: Password hashing, JWT access/refresh token lifecycle, invalid token rejection.
- `tests/test_crm.py`: Provider CRUD, Company/Contact deduplication, Lead scoring, 12-stage transitions, Do-Not-Contact suppression, CSV/Excel formula injection defense.
- `tests/test_discovery.py`: SSRF guard blocking localhost/private IPs, URL normalizer, Google dorking generation, DDGS graceful fallback.
- `tests/test_extraction.py`: Page classification, relationship taxonomy classification, evidence validation, prompt injection defense, model hallucinated email stripping.

---

## 📜 Compliance & Ethical Data Boundaries

LeadIntel CRM operates strictly within ethical boundaries:
1. Only publicly accessible business information is retrieved.
2. No CAPTCHAs or anti-bot protections are bypassed.
3. No inferred or guessed emails are generated.
4. Respects `robots.txt` directives and rate-limit delays.
5. All discovered client references maintain strict source attribution and evidence snippets.
