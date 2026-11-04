"""Verificación de identidad y autorización por recurso.

El backend Express original no autenticaba ningún endpoint: cualquier llamante
podía leer o modificar los datos de cualquier usuario pasando su `usuario_id`,
y además lo hacía con la service-role key, que salta las políticas RLS de
Supabase. Este módulo cierra ese hueco.

Dos piezas distintas, deliberadamente separadas:

* `require_user`  -> *autenticación*: el token existe y Supabase lo valida.
* `require_self`  -> *autorización*: el usuario autenticado es el dueño del
                     recurso que se está leyendo o modificando.

El token se valida contra Supabase (su emisor). No se inventa criptografía ni se
acepta un token por el simple hecho de venir presente en la cabecera.
"""

import hashlib
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache

from . import supabase
from .errors import DataAccessError, ForbiddenError, UnauthorizedError

logger = logging.getLogger(__name__)

_BEARER_PREFIX = "bearer "
_CACHE_PREFIX = "pygo:auth:"


def bearer_token(request) -> Optional[str]:
    """Extrae el token `Authorization: Bearer <token>`. Función pura."""
    header = request.META.get("HTTP_AUTHORIZATION", "") or ""
    if not header.lower().startswith(_BEARER_PREFIX):
        return None
    token = header[len(_BEARER_PREFIX) :].strip()
    return token or None


def _cache_key(token: str) -> str:
    """Clave de caché derivada del token. Nunca se almacena el token en claro."""
    return _CACHE_PREFIX + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _verify_token(token: str) -> Dict[str, Any]:
    """Valida el token contra Supabase y devuelve el usuario.

    Resultado memoizado unos segundos para no añadir una llamada de red por cada
    petición. El TTL es corto a propósito: un token revocado deja de servir en
    cuanto expira la entrada.
    """
    key = _cache_key(token)
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        user = supabase.auth_get_user(token)
    except DataAccessError as error:
        # No poder verificar nunca equivale a dejar pasar: se deniega.
        if error.upstream_status in (400, 401, 403):
            raise UnauthorizedError("Token inválido o expirado.", cause=error) from error
        logger.error("No se pudo verificar el token contra Supabase: %s", error.message)
        raise

    if not user.get("id"):
        raise UnauthorizedError("Token inválido o expirado.")

    cache.set(key, user, settings.AUTH_CACHE_SECONDS)
    return user


def require_user(request) -> Dict[str, Any]:
    """Devuelve el usuario autenticado o lanza 401.

    El resultado se memoiza en el objeto `request` para que varias llamadas
    dentro de la misma vista no revaliden el token.
    """
    cached = getattr(request, "_pygo_user", None)
    if cached is not None:
        return cached

    token = bearer_token(request)
    if not token:
        raise UnauthorizedError("Falta la cabecera Authorization con el token de sesión.")

    user = _verify_token(token)
    setattr(request, "_pygo_user", user)
    return user


def require_self(request, usuario_id: Any) -> Dict[str, Any]:
    """Exige que el usuario autenticado sea `usuario_id`.

    Es la comprobación a nivel de acción: autenticarse no basta, hay que ser el
    dueño del recurso. Sin esto, un usuario con sesión válida podría leer o
    sobrescribir la configuración y el progreso de cualquier otro.
    """
    user = require_user(request)
    if str(user.get("id")) != str(usuario_id):
        raise ForbiddenError("No puedes acceder a los datos de otro usuario.")
    return user


def optional_user(request) -> Optional[Dict[str, Any]]:
    """Usuario autenticado si hay token válido; `None` si no se envió ninguno.

    Para endpoints de contenido público que enriquecen la respuesta cuando hay
    sesión. Un token presente pero inválido sigue siendo un 401: ignorarlo
    convertiría un fallo de autenticación en un éxito silencioso.
    """
    return require_user(request) if bearer_token(request) else None
