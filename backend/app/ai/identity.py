"""Validate server-supplied context, without pretending to authenticate JWTs here."""

from uuid import UUID

from civicmesh_ai.errors import AIError


def owner(state: dict) -> UUID:
    """Require an owner identifier already verified and authorized by the backend."""
    try:
        return UUID(state["owner_id"])
    except (KeyError, ValueError, TypeError):
        raise AIError("owner_context_required", "Verified owner context is required.") from None
