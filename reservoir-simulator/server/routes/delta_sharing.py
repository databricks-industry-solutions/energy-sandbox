from fastapi import APIRouter
from ..delta_sharing import get_sharing_status

router = APIRouter()


@router.get("/delta-sharing/status")
async def sharing_status():
    """Current Delta Sharing status (inbound + outbound)."""
    return get_sharing_status()
