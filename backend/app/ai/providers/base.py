from typing import Protocol

from civicmesh_ai.schemas import Extraction, ExtractionRequest


class ExtractionProvider(Protocol):
    async def extract(self, request: ExtractionRequest) -> Extraction: ...
