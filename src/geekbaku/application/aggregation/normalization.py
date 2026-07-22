"""Normalization Engine (parte específica del Aggregation Engine).

`application/providers/normalizers.py` (Sprint 3+) ya normaliza Anime,
Episode, Season, Relation, tipo/estado/fuentes de external id y nombres
libres (género/estudio/productor) apenas se recibe la respuesta de UN
provider — eso no cambia acá. Lo que agrega este módulo es la validación de
Images (`thumbnail_url`/`banner_url`) al momento de FUSIONAR resultados de
varios providers: una URL de imagen rota o mal formada de un provider no
debería filtrarse a un resultado agregado. Reutiliza los Value Objects de
dominio `ImageUrl`/`VideoUrl` (usarlos no modifica el dominio) como única
fuente de verdad de qué es una URL válida — la misma regla que ya aplica
`catalog.Media`.
"""

from __future__ import annotations

from geekbaku.domain.catalog.value_objects import ImageUrl, VideoUrl
from geekbaku.domain.shared.errors import ValidationError


def normalize_image_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None
    try:
        return str(ImageUrl(raw_url))
    except ValidationError:
        return None


def normalize_video_url(raw_url: str | None) -> str | None:
    if raw_url is None:
        return None
    try:
        return str(VideoUrl(raw_url))
    except ValidationError:
        return None
