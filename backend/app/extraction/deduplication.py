"""
Contact and company deduplication utilities.
"""
from app.utils.deduplication import (
    generate_contact_dedup_key,
    generate_company_dedup_key,
    normalize_name
)

__all__ = [
    "generate_contact_dedup_key",
    "generate_company_dedup_key",
    "normalize_name"
]
