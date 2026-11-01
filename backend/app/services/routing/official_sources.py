"""Verified official source retrieval with strict Anti-SSRF and DNS-rebinding protection."""

import asyncio
import ipaddress
import socket
import urllib.parse
from datetime import datetime, timezone
from uuid import UUID

import httpx
from backend.app.core.config import get_settings
from backend.app.core.errors import ServiceUnavailableError, ValidationError
from backend.app.database.models import Authority, SourceChunk, SourceDocument
from backend.app.schemas.common import Category, ConfirmedLocation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

settings = get_settings()

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("::ffff:0:0/96"),
]


def is_safe_ip(ip_str: str) -> bool:
    """Validate that an IP is globally routable and not private or reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_global and not ip.is_multicast and not any(ip in net for net in BLOCKED_IP_NETWORKS)
    except ValueError:
        return False


def validated_target(url: str) -> tuple[urllib.parse.SplitResult, str]:
    """Validate URL scheme and resolve target host to verify it is not an internal service (Anti-SSRF)."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() not in ("http", "https"):
        raise ValidationError(f"Invalid URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

    if not parsed.hostname:
        raise ValidationError("URL must contain a valid hostname.")

    if parsed.username or parsed.password:
        raise ValidationError("URL must not contain credentials.")

    try:
        addr_info = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        if not addr_info:
            raise ValidationError("Target host has no addresses.")
        for _, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            if not is_safe_ip(ip_str):
                raise ValidationError(f"Target host '{parsed.hostname}' resolves to restricted IP: {ip_str}")
    except socket.gaierror as e:
        raise ValidationError(f"Failed to resolve hostname '{parsed.hostname}': {str(e)}") from None

    return parsed, addr_info[0][4][0]


def validate_url_safe(url: str) -> str:
    """Validate URL and every resolved address without making an HTTP request."""
    validated_target(url)
    return url


class SafeFetcher:
    """HTTP client that enforces SSRF checks on initial request and each redirect hop."""

    @staticmethod
    async def fetch_page(url: str, timeout_seconds: float = 10.0) -> str:
        current_url = url
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False, trust_env=False) as client:
            for _ in range(4):
                parsed, address = await asyncio.to_thread(validated_target, current_url)
                # Connect to the vetted address, retaining the original HTTP Host and TLS SNI.
                # No second DNS lookup can redirect the connection into a private service.
                host = f"[{address}]" if ":" in address else address
                authority = f"{host}:{parsed.port}" if parsed.port else host
                pinned_url = urllib.parse.urlunsplit(parsed._replace(netloc=authority, fragment=""))
                async with client.stream("GET", pinned_url, headers={"Host": parsed.netloc},
                    extensions={"sni_hostname": parsed.hostname}) as response:
                    if response.is_redirect:
                        next_url = response.headers.get("location")
                        if not next_url:
                            raise ValidationError("Redirect response missing Location header.")
                        current_url = urllib.parse.urljoin(current_url, next_url)
                        continue
                    response.raise_for_status()
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > 4 * 1024 * 1024:
                            raise ValidationError("Official source exceeds the 4 MiB fetch limit.")
                        chunks.append(chunk)
                    return b"".join(chunks).decode("utf-8", errors="replace")
        raise ValidationError("Too many redirects during safe fetch.")


class OfficialSourcePassage:
    def __init__(
        self,
        document_id: UUID,
        authority_id: UUID,
        authority_name: str,
        jurisdiction: str,
        url: str,
        retrieved_at: datetime,
        verified_at: datetime,
        supporting_passage: str,
    ):
        self.document_id = document_id
        self.authority_id = authority_id
        self.authority_name = authority_name
        self.jurisdiction = jurisdiction
        self.url = url
        self.retrieved_at = retrieved_at if retrieved_at.tzinfo else retrieved_at.replace(tzinfo=timezone.utc)
        self.verified_at = verified_at if verified_at.tzinfo else verified_at.replace(tzinfo=timezone.utc)
        self.supporting_passage = supporting_passage

    def to_dict(self) -> dict:
        return {
            "document_id": str(self.document_id),
            "authority_id": str(self.authority_id),
            "authority_name": self.authority_name,
            "jurisdiction": self.jurisdiction,
            "url": self.url,
            "retrieved_at": self.retrieved_at.isoformat(),
            "verified_at": self.verified_at.isoformat(),
            "supporting_passage": self.supporting_passage,
        }


class OfficialSourceService:
    @staticmethod
    async def get_authority_sources(
        *,
        report_id: UUID,
        owner_id: UUID,
        category: Category,
        location: ConfirmedLocation,
        db: AsyncSession,
        limit: int = 10,
        pilot_locality_name: str | None = None,
        pilot_latitude: float | None = None,
        pilot_longitude: float | None = None,
        pilot_radius_meters: float | None = None,
    ) -> list[OfficialSourcePassage]:
        """Retrieve verified authority document passages relevant to the report."""
        locality = settings.PILOT_LOCALITY_NAME if pilot_locality_name is None else pilot_locality_name
        if not locality.strip():
            raise ServiceUnavailableError("Pilot locality is not configured.")
        from backend.app.services.matching.incident_matcher import haversine_distance_meters
        center_lat = settings.PILOT_LATITUDE if pilot_latitude is None else pilot_latitude
        center_lon = settings.PILOT_LONGITUDE if pilot_longitude is None else pilot_longitude
        radius = settings.PILOT_RADIUS_METERS if pilot_radius_meters is None else pilot_radius_meters
        if center_lat is None or center_lon is None:
            return []  # A locality name alone cannot establish geographic jurisdiction.
        if haversine_distance_meters(location.latitude, location.longitude, center_lat, center_lon) > radius:
            return []
        category_term = "garbage" if category == "garbage" else "water"
        stmt = (
            select(SourceChunk, SourceDocument, Authority)
            .join(SourceDocument, SourceChunk.document_id == SourceDocument.id)
            .join(Authority, SourceDocument.authority_id == Authority.id)
            .where(
                Authority.jurisdiction == locality
            )
            .where(
                SourceDocument.title.ilike(f"%{category_term}%")
                | SourceChunk.content.ilike(f"%{category_term}%")
            )
            .order_by(SourceDocument.retrieved_at.desc(), SourceChunk.chunk_index.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

        passages: list[OfficialSourcePassage] = []
        for chunk, doc, auth in rows:
            passages.append(
                OfficialSourcePassage(
                    document_id=doc.id,
                    authority_id=auth.id,
                    authority_name=auth.name,
                    jurisdiction=auth.jurisdiction,
                    url=doc.url,
                    retrieved_at=doc.retrieved_at,
                    verified_at=doc.verified_at,
                    supporting_passage=chunk.content,
                )
            )
        return passages
