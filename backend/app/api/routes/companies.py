from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.auth.dependencies import get_db, get_current_user
from app.crm.company_service import create_company, get_company, list_companies, update_company, delete_company
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse
from app.schemas.common import PaginatedResponse, paginate, build_skip_limit

router = APIRouter(prefix="/companies", tags=["Companies"])

def _fmt(doc: dict) -> dict:
    for f in ("created_at", "updated_at"):
        if doc.get(f) and hasattr(doc[f], "isoformat"):
            doc[f] = doc[f].isoformat()
    return doc

@router.get("", response_model=PaginatedResponse)
@router.get("/", response_model=PaginatedResponse, include_in_schema=False)
async def list_companies_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    search: Optional[str] = None,
    industry: Optional[str] = None,
    country: Optional[str] = None,
    provider_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    skip, limit = build_skip_limit(page, page_size)
    items, total = await list_companies(db, skip, limit, search, industry, country, provider_id)
    return paginate([_fmt(i) for i in items], total, page, limit)

@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_company_route(
    data: CompanyCreate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    doc = await create_company(db, data.model_dump(), str(user.get("_id", "")))
    return _fmt(doc)

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company_route(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_company(db, company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    return _fmt(doc)

@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company_route(
    company_id: str,
    data: CompanyUpdate,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    doc = await update_company(db, company_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    return _fmt(doc)

@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_route(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    success = await delete_company(db, company_id)
    if not success:
        raise HTTPException(status_code=404, detail="Company not found")

@router.get("/{company_id}/contact-channels")
async def get_company_contact_channels_route(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_company(db, company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    return {
        "company_id": company_id,
        "company_name": doc.get("name"),
        "website": doc.get("website"),
        "enrichment_status": doc.get("enrichment_status", "pending"),
        "last_enriched_at": doc.get("last_enriched_at"),
        "public_contact": doc.get("public_contact", {}),
        "public_contact_channels": doc.get("public_contact_channels", []),
        "social_profiles": doc.get("social_profiles", {}),
    }

@router.post("/{company_id}/enrich")
async def enrich_company_route(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    from app.enrichment.company_enrichment_service import CompanyEnrichmentService
    doc = await get_company(db, company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")
    
    service = CompanyEnrichmentService()
    enriched_doc = await service.enrich_company(db, company_id)
    return {
        "success": bool(enriched_doc),
        "company": _fmt(enriched_doc or doc),
    }

@router.get("/{company_id}/people")
async def get_company_people_route(
    company_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    doc = await get_company(db, company_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Company not found")

    cursor = db.contacts.find({
        "$or": [
            {"company_id": company_id},
            {"associated_companies.company_id": str(company_id)},
            {"company_name": doc.get("name")},
        ]
    })
    contacts = await cursor.to_list(100) if hasattr(cursor, "to_list") else []

    people = []
    seen_names = set()
    for c in contacts:
        name = c.get("full_name")
        if name and name.lower() not in seen_names:
            seen_names.add(name.lower())
            people.append({
                "id": str(c.get("_id", "")),
                "full_name": name,
                "designation": c.get("designation") or "Executive",
                "email": c.get("email"),
                "phone": c.get("phone"),
                "linkedin_url": c.get("linkedin_url"),
                "verification_status": c.get("verification_status") or c.get("contact_verification_status", "verified"),
                "evidence_quote": c.get("evidence_quote"),
                "source": c.get("source"),
            })

    for ap in (doc.get("associated_people") or []):
        if isinstance(ap, dict):
            name = ap.get("full_name")
            if name and name.lower() not in seen_names:
                seen_names.add(name.lower())
                people.append({
                    "id": ap.get("contact_id") or "",
                    "full_name": name,
                    "designation": ap.get("designation") or "Executive",
                    "linkedin_url": ap.get("linkedin_url"),
                    "verification_status": ap.get("verification_status", "source_verified"),
                    "confidence": ap.get("confidence", 0.8),
                })

    return {
        "company_id": company_id,
        "company_name": doc.get("name"),
        "total_people": len(people),
        "people": people,
    }
