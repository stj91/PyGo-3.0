"""Límites de `POST /api/eventos`: tamaño del cuerpo y eventos por minuto por usuario.

El contador vive en la caché de Django (por proceso con la LocMemCache por
defecto). No es atómico entre peticiones simultáneas: frena un bucle o un abuso,
no garantiza el número exacto.
"""

import hashlib
import time
from typing import List, Optional, Sequence, Tuple

from django.core.cache import cache

from core.errors import AppError, ValidationError

MAX_BYTES_CUERPO = 8 * 1024
MAX_EVENTOS_POR_MINUTO = 120
VENTANA_SEGUNDOS = 60

_CACHE_PREFIX = "pygo:motor:eventos:"


class DemasiadasPeticionesError(AppError):
    """El usuario superó el límite de eventos por minuto."""

    status_code = 429
    code = "RATE_LIMITED"
    default_message = "Demasiados eventos en poco tiempo. Inténtalo más tarde."


def exigir_tamano(request) -> None:
    """400 si el cuerpo supera `MAX_BYTES_CUERPO`, antes de parsearlo."""
    try:
        declarado = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        declarado = 0
    if declarado > MAX_BYTES_CUERPO or len(request.body or b"") > MAX_BYTES_CUERPO:
        raise ValidationError("El evento supera el tamaño máximo de 8 KB.")


def consumir(
    marcas: Sequence[float], ahora: float, limite: int, ventana: float
) -> Tuple[bool, List[float]]:
    """Ventana deslizante. **Pura.** Devuelve (permitido, marcas nuevas)."""
    vigentes = [m for m in marcas if ahora - m < ventana]
    if len(vigentes) >= limite:
        return False, vigentes
    return True, [*vigentes, ahora]


def _clave(usuario_id: str) -> str:
    return _CACHE_PREFIX + hashlib.sha256(str(usuario_id).encode("utf-8")).hexdigest()


def exigir_cupo(usuario_id: str, ahora: Optional[float] = None) -> None:
    """429 si el usuario ya registró `MAX_EVENTOS_POR_MINUTO` en el último minuto."""
    clave = _clave(usuario_id)
    permitido, marcas = consumir(
        cache.get(clave) or [],
        time.time() if ahora is None else ahora,
        MAX_EVENTOS_POR_MINUTO,
        VENTANA_SEGUNDOS,
    )
    cache.set(clave, marcas, VENTANA_SEGUNDOS)
    if not permitido:
        raise DemasiadasPeticionesError()
