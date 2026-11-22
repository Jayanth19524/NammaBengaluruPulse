"""
BWSSB adapter — attempts to fetch supply disruption data from public BWSSB/BBMP feeds.
Degrades gracefully to empty list on any error. Never raises.
"""
import logging
from typing import List
import httpx
from .base import WaterAdapter, RawWaterData

logger = logging.getLogger(__name__)

# BWSSB does not currently publish a machine-readable public API.
# This stub is wired to a placeholder URL and degrades gracefully.
# When a real endpoint is available, replace BWSSB_API_URL and parse the response.
BWSSB_API_URL = "https://bwssb.gov.in/api/disruptions"  # placeholder


class BWSSBAdapter(WaterAdapter):
    @property
    def name(self) -> str:
        return "bwssb_api"

    async def fetch(self, lat: float, lng: float, radius_m: float) -> List[RawWaterData]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    BWSSB_API_URL,
                    params={"lat": lat, "lng": lng, "radius": radius_m},
                )
                resp.raise_for_status()
                # Parse real response here when API is available
                return []
        except Exception as exc:
            logger.warning(
                "[BWSSBAdapter] fetch failed, degrading to empty: %s", exc
            )
            return []
