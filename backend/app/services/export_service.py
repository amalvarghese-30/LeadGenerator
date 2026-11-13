import io
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase


def _sanitize_val(val: Any) -> Any:
    """Prevent CSV/Excel formula injection (=, +, -, @, \t, \r)."""
    if isinstance(val, str) and val.startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + val
    return val


def _stringify_dates(records: List[Dict]) -> List[Dict]:
    """Convert datetime fields to ISO strings for DataFrame and sanitize formulas."""
    out = []
    for r in records:
        clean = {}
        for k, v in r.items():
            if isinstance(v, datetime):
                clean[k] = v.isoformat()
            elif isinstance(v, dict):
                clean[k] = str(v)
            elif isinstance(v, list):
                clean[k] = ", ".join(str(i) for i in v)
            else:
                clean[k] = _sanitize_val(v)
        out.append(clean)
    return out


async def export_leads_to_csv(db: AsyncIOMotorDatabase, filters: Optional[Dict] = None) -> bytes:
    query = filters or {}
    cursor = db.leads.find(query).sort("created_at", -1).limit(10000)
    docs = await cursor.to_list(length=10000)
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    records = _stringify_dates(docs)
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


async def export_leads_to_excel(db: AsyncIOMotorDatabase, filters: Optional[Dict] = None) -> bytes:
    query = filters or {}
    cursor = db.leads.find(query).sort("created_at", -1).limit(10000)
    docs = await cursor.to_list(length=10000)
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    records = _stringify_dates(docs)
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Leads", index=False)
    return buf.getvalue()


async def export_providers_to_csv(db: AsyncIOMotorDatabase, filters: Optional[Dict] = None) -> bytes:
    query = filters or {}
    cursor = db.providers.find(query).sort("created_at", -1).limit(10000)
    docs = await cursor.to_list(length=10000)
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    records = _stringify_dates(docs)
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


async def export_contacts_to_csv(db: AsyncIOMotorDatabase, filters: Optional[Dict] = None) -> bytes:
    query = filters or {}
    cursor = db.contacts.find(query).sort("created_at", -1).limit(10000)
    docs = await cursor.to_list(length=10000)
    for d in docs:
        d["id"] = str(d.pop("_id", ""))
    records = _stringify_dates(docs)
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
