"""Cliente funcional para la API REST de Supabase (PostgREST + GoTrue).

Sustituye al SDK `@supabase/supabase-js` usando sólo la librería estándar, de
modo que el backend no arrastra dependencias HTTP adicionales.

Diseño: un único `_request` hace la E/S y todo lo demás son funciones pequeñas
que construyen peticiones. Los filtros son valores componibles (`eq`, `in_`,
`is_`), no un constructor con estado encadenado.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.conf import settings

from .errors import DataAccessError
from .functional import first

logger = logging.getLogger(__name__)

#: Un filtro es un par (columna, expresión PostgREST), p.ej. ("id", "eq.4").
Filter = Tuple[str, str]

_REST_PREFIX = "/rest/v1"
_AUTH_PREFIX = "/auth/v1"


# --- Constructores de filtros (puros) ---------------------------------------


def eq(column: str, value: Any) -> Filter:
    """Igualdad: `column = value`."""
    return (column, f"eq.{value}")


def in_(column: str, values: Iterable[Any]) -> Filter:
    """Pertenencia: `column IN (values)`."""
    joined = ",".join(str(v) for v in values)
    return (column, f"in.({joined})")


def is_(column: str, value: str) -> Filter:
    """Comparación con `NULL`/booleanos: `column IS value`."""
    return (column, f"is.{value}")


# --- Transporte -------------------------------------------------------------


def _service_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Cabeceras con la service-role key. Nunca deben salir del servidor."""
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        **(extra or {}),
    }


def _decode_body(raw: bytes) -> Any:
    """Decodifica JSON de forma total: devuelve `None` si el cuerpo no es JSON."""
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _upstream_message(payload: Any, fallback: str) -> str:
    """Extrae el mensaje de error de las distintas formas que usa Supabase."""
    if isinstance(payload, dict):
        for key in ("message", "msg", "error_description", "error", "hint", "details"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return fallback


def _upstream_code(payload: Any) -> Optional[str]:
    """Extrae el código de error (PostgREST usa `code`, GoTrue `error_code`/`error`)."""
    if isinstance(payload, dict):
        for key in ("error_code", "code", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _request(
    method: str,
    path: str,
    *,
    operation: str,
    params: Optional[Sequence[Tuple[str, str]]] = None,
    body: Any = None,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Ejecuta una petición contra Supabase y devuelve el JSON decodificado.

    Única función del módulo con efectos de red. Cualquier fallo se traduce a
    `DataAccessError` conservando el estado y el código originales para que la
    capa de servicio pueda clasificarlo.
    """
    query = f"?{urllib.parse.urlencode(list(params))}" if params else ""
    url = f"{settings.SUPABASE_URL}{path}{query}"
    payload = json.dumps(body).encode("utf-8") if body is not None else None

    request = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers=_service_headers(headers),
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.SUPABASE_TIMEOUT_SECONDS) as response:
            return _decode_body(response.read())
    except urllib.error.HTTPError as exc:
        error_body = _decode_body(exc.read())
        raise DataAccessError(
            _upstream_message(error_body, f"Supabase respondió {exc.code} en {operation}."),
            operation=operation,
            upstream_status=exc.code,
            upstream_code=_upstream_code(error_body),
            cause=exc,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.error("Fallo de red hablando con Supabase en %s: %s", operation, exc)
        raise DataAccessError(
            "No se pudo contactar con el servicio de datos.",
            operation=operation,
            cause=exc,
        ) from exc


# --- PostgREST: lectura -----------------------------------------------------


def select(
    table: str,
    *,
    columns: str = "*",
    filters: Sequence[Filter] = (),
    order: Optional[str] = None,
    limit: Optional[int] = None,
    operation: Optional[str] = None,
) -> List[Dict]:
    """Consulta una tabla y devuelve siempre una lista (vacía si no hay filas).

    `columns` admite la sintaxis de recursos embebidos de PostgREST, p.ej.
    `"*,temas(id,titulo,lecciones(id,titulo))"`.
    """
    params: List[Tuple[str, str]] = [("select", columns), *filters]
    if order:
        params.append(("order", order))
    if limit is not None:
        params.append(("limit", str(limit)))

    rows = _request(
        "GET",
        f"{_REST_PREFIX}/{table}",
        operation=operation or f"select:{table}",
        params=params,
    )
    return rows if isinstance(rows, list) else []


def select_one(
    table: str,
    *,
    columns: str = "*",
    filters: Sequence[Filter] = (),
    order: Optional[str] = None,
    operation: Optional[str] = None,
) -> Optional[Dict]:
    """Primera fila que cumple los filtros, o `None`.

    Equivale al `.maybeSingle()` del SDK: ausencia de filas no es un error.
    """
    return first(
        select(
            table,
            columns=columns,
            filters=filters,
            order=order,
            limit=1,
            operation=operation or f"select_one:{table}",
        )
    )


def count_rows(
    table: str,
    *,
    filters: Sequence[Filter] = (),
    operation: Optional[str] = None,
) -> int:
    """Número de filas que cumplen los filtros (trae sólo la columna `id`)."""
    return len(
        select(
            table,
            columns="id",
            filters=filters,
            operation=operation or f"count:{table}",
        )
    )


# --- PostgREST: escritura ---------------------------------------------------


def insert(
    table: str,
    rows: Any,
    *,
    returning: bool = True,
    operation: Optional[str] = None,
) -> Optional[Dict]:
    """Inserta una fila (o lista de filas) y devuelve la primera insertada."""
    prefer = "return=representation" if returning else "return=minimal"
    result = _request(
        "POST",
        f"{_REST_PREFIX}/{table}",
        operation=operation or f"insert:{table}",
        body=rows if isinstance(rows, list) else [rows],
        headers={"Prefer": prefer},
    )
    return first(result) if isinstance(result, list) else result


def update(
    table: str,
    values: Dict,
    *,
    filters: Sequence[Filter],
    operation: Optional[str] = None,
) -> Optional[Dict]:
    """Actualiza las filas que cumplen `filters`.

    `filters` es obligatorio: un UPDATE sin filtro en PostgREST afectaría a toda
    la tabla.
    """
    if not filters:
        raise ValueError("update() requiere al menos un filtro para no afectar a toda la tabla.")

    result = _request(
        "PATCH",
        f"{_REST_PREFIX}/{table}",
        operation=operation or f"update:{table}",
        params=list(filters),
        body=values,
        headers={"Prefer": "return=representation"},
    )
    return first(result) if isinstance(result, list) else result


def upsert_where(
    table: str,
    *,
    match: Dict[str, Any],
    values: Dict[str, Any],
    operation: Optional[str] = None,
) -> Optional[Dict]:
    """Inserta o actualiza buscando primero la fila por `match`.

    Alternativa a `upsert()` para tablas cuya clave primaria es un `id` serial y
    que no declaran un índice único sobre las columnas de negocio. En ese caso un
    upsert de PostgREST no tiene con qué resolver el conflicto y acabaría
    insertando una fila nueva en cada llamada; esto comprueba y actualiza.

    No es atómico: dos peticiones simultáneas para la misma clave podrían crear
    dos filas. Para cerrarlo del todo hace falta un índice único en la base de
    datos y entonces `upsert(..., on_conflict=...)` ya sirve.
    """
    filters = tuple(eq(column, value) for column, value in match.items())
    existing = select_one(
        table, columns="id", filters=filters, operation=f"{operation or table}:lookup"
    )

    if existing and existing.get("id") is not None:
        return update(
            table,
            values,
            filters=(eq("id", existing["id"]),),
            operation=f"{operation or table}:update",
        )

    return insert(
        table, {**match, **values}, operation=f"{operation or table}:insert"
    )


def upsert(
    table: str,
    row: Dict,
    *,
    on_conflict: Optional[str] = None,
    operation: Optional[str] = None,
) -> Optional[Dict]:
    """Inserta o actualiza según la clave en conflicto.

    `on_conflict` nombra las columnas del índice único. Si se omite, PostgREST
    resuelve contra la clave primaria (mismo comportamiento que el `.upsert()`
    del SDK Node, que tampoco lo especificaba).
    """
    params = [("on_conflict", on_conflict)] if on_conflict else None
    result = _request(
        "POST",
        f"{_REST_PREFIX}/{table}",
        operation=operation or f"upsert:{table}",
        params=params,
        body=[row],
        headers={"Prefer": "resolution=merge-duplicates,return=representation"},
    )
    return first(result) if isinstance(result, list) else result


# --- GoTrue: autenticación --------------------------------------------------


def auth_create_user(*, email: str, password: str, user_metadata: Dict) -> Dict:
    """Crea la cuenta vía endpoint de administración, con el email ya confirmado."""
    created = _request(
        "POST",
        f"{_AUTH_PREFIX}/admin/users",
        operation="auth_create_user",
        body={
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": user_metadata,
        },
    )
    return created if isinstance(created, dict) else {}


def auth_delete_user(user_id: str) -> None:
    """Elimina una cuenta de Auth (se usa para compensar registros a medias)."""
    _request(
        "DELETE",
        f"{_AUTH_PREFIX}/admin/users/{urllib.parse.quote(str(user_id))}",
        operation="auth_delete_user",
    )


def auth_sign_in(*, email: str, password: str) -> Dict:
    """Autentica con email y contraseña.

    Normaliza la respuesta plana de GoTrue a la forma `{token, user}` para que la
    capa de servicio no dependa del formato del transporte.
    """
    data = _request(
        "POST",
        f"{_AUTH_PREFIX}/token",
        operation="auth_sign_in",
        params=[("grant_type", "password")],
        body={"email": email, "password": password},
    )
    payload = data if isinstance(data, dict) else {}
    return {
        "token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "user": payload.get("user") or {},
    }


def auth_get_user(access_token: str) -> Dict:
    """Valida un access token contra Supabase y devuelve su usuario.

    La verificación la hace el emisor del token, no este servicio: así no se
    inventa criptografía propia ni se confía en un token sin comprobar.
    """
    data = _request(
        "GET",
        f"{_AUTH_PREFIX}/user",
        operation="auth_get_user",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return data if isinstance(data, dict) else {}
