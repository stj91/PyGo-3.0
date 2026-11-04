"""Plomería HTTP compartida: parseo de peticiones, respuestas y manejo de errores.

Las vistas son funciones puras de `(request, **kwargs) -> dict`. El decorador
`endpoint` se encarga de todo lo transversal (método permitido, serialización,
traducción de errores), de modo que ninguna vista repite bloques try/except.
"""

import json
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .errors import AppError, MethodNotAllowedError, ValidationError, error_payload
from .functional import omit_none

logger = logging.getLogger(__name__)


def ok(**data: Any) -> Dict[str, Any]:
    """Respuesta de éxito con la forma `{"success": true, ...}` que usa el frontend."""
    return {"success": True, **data}


def json_response(payload: Any, status: int = 200) -> JsonResponse:
    """Serializa `payload` a JSON preservando los caracteres acentuados."""
    return JsonResponse(
        payload,
        status=status,
        safe=not isinstance(payload, list),
        json_dumps_params={"ensure_ascii": False},
    )


def parse_json_body(request) -> Dict[str, Any]:
    """Cuerpo JSON de la petición como diccionario.

    Un cuerpo vacío equivale a `{}` (igual que `req.body ?? {}` en Express); un
    JSON corrupto o un literal no-objeto es un error de validación explícito.
    """
    raw = (request.body or b"").strip()
    if not raw:
        return {}

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("El cuerpo de la petición no es JSON válido.") from exc

    if not isinstance(parsed, dict):
        raise ValidationError("Se esperaba un objeto JSON en el cuerpo de la petición.")

    return parsed


def require_fields(data: Dict[str, Any], fields: Sequence[str], message: Optional[str] = None) -> None:
    """Valida presencia de campos obligatorios. Lanza `ValidationError` listándolos.

    Trata `None`, cadena vacía y listas/diccionarios vacíos como ausentes, igual
    que las comprobaciones de verdad del código Express original.
    """
    missing = [field for field in fields if not data.get(field)]
    if missing:
        raise ValidationError(message, campos=missing)


def _normalize(result: Any) -> Tuple[Any, int]:
    """Acepta `payload` o `(payload, status)` y devuelve siempre la tupla."""
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], int):
        return result
    return (result, 200)


def endpoint(*methods: str) -> Callable:
    """Convierte una función de dominio en una vista Django.

    Responsabilidades: validar el método, serializar el resultado y traducir
    errores. Los `AppError` viajan con su propio estado; cualquier otra excepción
    se registra y se responde como 500 genérico para no filtrar detalles internos.
    """
    allowed = tuple(m.upper() for m in methods) or ("GET",)

    def decorator(handler: Callable) -> Callable:
        @csrf_exempt
        @wraps(handler)
        def view(request, *args, **kwargs):
            try:
                if request.method not in allowed:
                    raise MethodNotAllowedError(
                        f"Método {request.method} no permitido en este endpoint."
                    )
                payload, status = _normalize(handler(request, *args, **kwargs))
                return json_response(payload, status)
            except AppError as error:
                if error.status_code >= 500:
                    logger.error(
                        "Error %s en %s: %s", error.code, request.path, error.message,
                        exc_info=error.cause or error,
                    )
                response = json_response(error_payload(error), error.status_code)
                if error.status_code == 405:
                    response["Allow"] = ", ".join(allowed)
                return response
            except Exception:
                logger.exception("Error inesperado en %s", request.path)
                return json_response(
                    {
                        "success": False,
                        "error": "Error interno del servidor.",
                        "code": "INTERNAL_ERROR",
                    },
                    500,
                )

        return view

    return decorator


def query_param(request, key: str, default: Any = None) -> Any:
    """Parámetro de query string, con `None` para cadenas vacías."""
    value = request.GET.get(key)
    return value if value not in (None, "") else default


def merged_input(request) -> Dict[str, Any]:
    """Cuerpo JSON y query string combinados (el cuerpo tiene prioridad)."""
    return omit_none({**request.GET.dict(), **parse_json_body(request)})


@csrf_exempt
def not_found(request, *args, **kwargs) -> HttpResponse:
    """Handler 404 en JSON, para que el frontend nunca reciba HTML."""
    return json_response(
        {"success": False, "error": "Endpoint no encontrado.", "code": "NOT_FOUND"},
        404,
    )


@csrf_exempt
def server_error(request, *args, **kwargs) -> HttpResponse:
    """Handler 500 en JSON."""
    return json_response(
        {"success": False, "error": "Error interno del servidor.", "code": "INTERNAL_ERROR"},
        500,
    )
