from typing import Dict, Optional, Tuple


# Scoring weights (total = 100 pts)
WEIGHTS = {
    "customer_category_relevance": 20,
    "designation_relevance": 20,
    "evidence_of_relationship": 20,
    "business_presence": 15,
    "contact_route": 15,
    "source_freshness": 10,
}

# High-value designations
EXECUTIVE_TITLES = {
    "ceo", "cto", "coo", "cfo", "cpo", "cmo", "president", "founder",
    "co-founder", "managing director", "md", "director", "vp", "vice president",
    "head of", "chief",
}

SENIOR_TITLES = {
    "senior manager", "manager", "lead", "principal", "partner",
    "associate director", "regional",
}


def _score_designation(designation: Optional[str]) -> float:
    """Score 0-1 based on decision-making authority."""
    if not designation:
        return 0.3
    d = designation.lower()
    for title in EXECUTIVE_TITLES:
        if title in d:
            return 1.0
    for title in SENIOR_TITLES:
        if title in d:
            return 0.7
    return 0.4


def _score_business_presence(contact: Optional[Dict]) -> float:
    """Score 0-1 based on how findable the contact is."""
    if not contact:
        return 0.0
    score = 0.0
    urls = contact.get("professional_urls", {})
    contacts_dict = contact.get("business_contacts", {})
    if urls.get("linkedin"):
        score += 0.4
    if contacts_dict.get("email") or contacts_dict.get("work_email"):
        score += 0.4
    if urls.get("twitter") or urls.get("github"):
        score += 0.1
    if contacts_dict.get("phone") or contacts_dict.get("mobile"):
        score += 0.1
    return min(score, 1.0)


def _score_contact_route(contact: Optional[Dict]) -> float:
    """Score 0-1 based on reachability."""
    if not contact:
        return 0.0
    contacts_dict = contact.get("business_contacts", {})
    if contacts_dict.get("email") or contacts_dict.get("work_email"):
        return 1.0
    if contact.get("professional_urls", {}).get("linkedin"):
        return 0.6
    return 0.2


def calculate_lead_score(lead: Dict, contact: Optional[Dict] = None) -> Tuple[float, Dict[str, float]]:
    """
    Calculate a lead score 0-100 with breakdown.
    Returns (total_score, breakdown_dict)
    """
    breakdown: Dict[str, float] = {}

    # 1. Customer category relevance (placeholder — will be enriched by AI worker)
    cat_score = lead.get("score_breakdown", {}).get("customer_category_relevance", 0.5)
    breakdown["customer_category_relevance"] = round(cat_score * WEIGHTS["customer_category_relevance"], 2)

    # 2. Designation relevance
    designation = contact.get("designation") if contact else None
    desg_score = _score_designation(designation)
    breakdown["designation_relevance"] = round(desg_score * WEIGHTS["designation_relevance"], 2)

    # 3. Evidence of relationship (placeholder — enriched by crawler)
    evidence_score = lead.get("score_breakdown", {}).get("evidence_of_relationship", 0.0)
    breakdown["evidence_of_relationship"] = round(evidence_score * WEIGHTS["evidence_of_relationship"], 2)

    # 4. Business presence
    presence_score = _score_business_presence(contact)
    breakdown["business_presence"] = round(presence_score * WEIGHTS["business_presence"], 2)

    # 5. Contact route
    route_score = _score_contact_route(contact)
    breakdown["contact_route"] = round(route_score * WEIGHTS["contact_route"], 2)

    # 6. Source freshness (placeholder — set by discovery)
    freshness_score = lead.get("score_breakdown", {}).get("source_freshness", 0.5)
    breakdown["source_freshness"] = round(freshness_score * WEIGHTS["source_freshness"], 2)

    total = round(sum(breakdown.values()), 2)
    return total, breakdown
