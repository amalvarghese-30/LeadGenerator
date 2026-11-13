"""
Contact verification workflow.

Verification lifecycle:
    discovered
        → source_reviewed        (human reviews the source page)
        → company_verified       (company identity confirmed)
        → contact_source_verified (contact details confirmed from source)
        → human_approved         (human gives final go-ahead for outreach)
        → rejected               (at any stage)

Rules:
- AI output NEVER auto-advances past "pending" / "discovered".
- Advancing requires a verifier_user_id (human action).
- Rejected contacts cannot be un-rejected via advance_stage().
- can_be_contacted() is the single gate for outreach eligibility.
"""
from datetime import datetime
from typing import Dict, List, Optional


class ContactVerifier:
    """
    Stateless helper that computes next-state transitions for contacts.

    Callers are responsible for persisting the returned dict back to the
    database — this class has no DB dependency and is fully testable without
    one.
    """

    # Ordered pipeline stages (rejected is a terminal side-exit)
    PIPELINE_STAGES: List[str] = [
        "discovered",
        "source_reviewed",
        "company_verified",
        "contact_source_verified",
        "human_approved",
    ]
    TERMINAL_STAGES: List[str] = ["human_approved", "rejected"]

    # ------------------------------------------------------------------
    # Stage transitions
    # ------------------------------------------------------------------

    def advance_stage(
        self,
        contact: Dict,
        verifier_user_id: str,
        notes: Optional[str] = None,
    ) -> Dict:
        """
        Advance the contact to the next verification stage.

        Does nothing (returns contact unchanged) if the contact is already
        at a terminal stage (human_approved or rejected).

        Args:
            contact:           The contact dict (read-only; a copy is returned).
            verifier_user_id:  ID of the human performing this action.
            notes:             Optional free-text verification notes.

        Returns:
            New contact dict with updated verification fields.
        """
        current = contact.get("contact_verification_status", "discovered")

        if current in self.TERMINAL_STAGES:
            # Cannot advance past terminal stages
            return dict(contact)

        try:
            idx = self.PIPELINE_STAGES.index(current)
        except ValueError:
            # Unknown stage — treat as discovered (index 0)
            idx = 0

        next_idx = min(idx + 1, len(self.PIPELINE_STAGES) - 1)
        next_stage = self.PIPELINE_STAGES[next_idx]

        return {
            **contact,
            "contact_verification_status": next_stage,
            "last_verified_by": verifier_user_id,
            "last_verified_at": datetime.utcnow().isoformat(),
            "verification_notes": notes,
        }

    def reject(
        self, contact: Dict, reason: str, user_id: str
    ) -> Dict:
        """
        Reject a contact at any stage.

        Args:
            contact:  The contact dict.
            reason:   Required rejection reason (stored for audit).
            user_id:  ID of the human performing this action.

        Returns:
            New contact dict with status = "rejected".
        """
        if not reason or not reason.strip():
            raise ValueError("A rejection reason is required.")

        return {
            **contact,
            "contact_verification_status": "rejected",
            "rejection_reason": reason.strip(),
            "rejected_by": user_id,
            "rejected_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Eligibility gate
    # ------------------------------------------------------------------

    def can_be_contacted(self, contact: Dict) -> bool:
        """
        Returns True only when ALL of the following hold:
        - contact_verification_status == "human_approved"
        - is_suppressed is not True
        - do_not_contact is not True

        This is the single authoritative check before initiating outreach.
        """
        return (
            contact.get("contact_verification_status") == "human_approved"
            and not contact.get("is_suppressed", False)
            and not contact.get("do_not_contact", False)
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def stage_index(self, stage: str) -> int:
        """Return the 0-based position of *stage* in the pipeline, or -1."""
        try:
            return self.PIPELINE_STAGES.index(stage)
        except ValueError:
            return -1

    def stages_remaining(self, contact: Dict) -> List[str]:
        """Return the pipeline stages that have not yet been reached."""
        current = contact.get("contact_verification_status", "discovered")
        idx = self.stage_index(current)
        if idx < 0:
            return list(self.PIPELINE_STAGES)
        return self.PIPELINE_STAGES[idx + 1:]
