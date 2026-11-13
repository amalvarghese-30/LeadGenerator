import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def log_audit(
    db: AsyncIOMotorDatabase,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    request_ip: Optional[str] = None,
    request_method: Optional[str] = None,
    request_path: Optional[str] = None,
    response_status: Optional[int] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> None:
    """Write an audit log entry to the audit_logs collection."""
    try:
        doc = {
            "user_id": user_id,
            "username": username,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "changes": changes,
            "request_ip": request_ip,
            "request_method": request_method,
            "request_path": request_path,
            "response_status": response_status,
            "success": success,
            "error_message": error_message,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
        }
        await db.audit_logs.insert_one(doc)
    except Exception as e:
        # Audit logging must never crash the app
        logger.error(f"Failed to write audit log: {e}", exc_info=True)
