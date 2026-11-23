# Candid Digital — Backend

> Provider Intelligence & CRM Lead Discovery Platform — [candiddigital.in](https://candiddigital.in/)

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your values

# Run the API server
uvicorn app.main:app --reload
```

## Seed the Database

```bash
python -m app.database.seed
```

Default admin credentials after seeding:
- **Email:** admin@candiddigital.in
- **Password:** Admin@123456

## API Docs

Once running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- Health check: http://localhost:8000/api/health
