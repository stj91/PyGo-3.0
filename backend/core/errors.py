"""Jerarquía de errores de la aplicación.

Las excepciones son necesariamente clases en Python, pero se usan como simples
portadoras de datos: toda la lógica de traducción a HTTP vive en funciones puras
(`error_payload`, `error_status`) al final del módulo.
"""

from typing import Any, Dict, Optional, Sequence


class AppError(Exception):
    """Error esperado del dominio, traducible a una respuesta HTTP."""

    status_code = 500
    code = "APP_ERROR"
    default_message = "Error interno del servidor."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        code: Optional[str] = None,
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        cause: Any = None,
    ) -> None:
        resolved = message or self.default_message
        super().__init__(resolved)
        self.message = resolved
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        self.cause = cause


class ValidationError(AppError):
    """Entrada inválida o campos obligatorios ausentes."""

    status_code = 400
    code = "VALIDATION_ERROR"
    default_message = "Campos obligatorios incompletos."

    def __init__(self, message: Optional[str] = None, campos: Sequence[str] = (), **kwargs) -> None:
        super().__init__(message, details={"campos": list(campos)}, **kwargs)


class WeakPasswordError(ValidationError):
    """La contraseña no cumple la política mínima."""

    code = "WEAK_PASSWORD"
    default_message = "La contraseña es demasiado débil."


class UnauthorizedError(AppError):
    """Falta el token o no es válido."""

    status_code = 401
    code = "UNAUTHORIZED"
    default_message = "Autenticación requerida."


class InvalidCredentialsError(UnauthorizedError):
    """Email o contraseña incorrectos."""

    code = "INVALID_CREDENTIALS"
    default_message = "Credenciales inválidas."


class ForbiddenError(AppError):
    """Autenticado, pero sin permiso sobre el recurso solicitado."""

    status_code = 403
    code = "FORBIDDEN"
    default_message = "No tienes permiso para acceder a este recurso."


class NotFoundError(AppError):
    """El recurso no existe."""

    status_code = 404
    code = "NOT_FOUND"
    default_message = "Recurso no encontrado."


class ConflictError(AppError):
    """El recurso ya existe o choca con el estado actual."""

    status_code = 409
    code = "CONFLICT"
    default_message = "El recurso ya existe."


class EmailAlreadyRegisteredError(ConflictError):
    """El email ya tiene una cuenta asociada."""

    code = "EMAIL_ALREADY_REGISTERED"
    default_message = "Ya existe una cuenta registrada con este email."


class RegistrationFailedError(AppError):
    """Fallo no recuperable durante el registro."""

    code = "REGISTRATION_FAILED"
    default_message = "No se pudo completar el registro."


class MethodNotAllowedError(AppError):
    """Método HTTP no soportado por el endpoint."""

    status_code = 405
    code = "METHOD_NOT_ALLOWED"
    default_message = "Método no permitido."


class DataAccessError(AppError):
    """Fallo al hablar con Supabase. Lo lanza la capa de repositorio."""

    status_code = 503
    code = "DATA_ACCESS_ERROR"
    default_message = "Error de acceso a datos."

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        operation: Optional[str] = None,
        upstream_status: Optional[int] = None,
        upstream_code: Optional[str] = None,
        **kwargs,
    ) -> None:
        super().__init__(message, **kwargs)
        self.operation = operation
        self.upstream_status = upstream_status
        self.upstream_code = upstream_code


# --- Funciones puras de traducción a HTTP -----------------------------------

#: Códigos de Supabase/PostgREST que significan "el email ya está registrado".
_DUPLICATE_CODES = frozenset({"email_exists", "user_already_exists", "23505"})
_DUPLICATE_FRAGMENTS = (
    "already been registered",
    "already registered",
    "duplicate key",
    "already exists",
)

#: Códigos y mensajes que significan "credenciales incorrectas".
_INVALID_CREDENTIAL_CODES = frozenset(
    {"invalid_credentials", "invalid_grant", "email_not_confirmed"}
)
_INVALID_CREDENTIAL_FRAGMENTS = ("invalid login credentials", "invalid email or password")


def _haystack(error: DataAccessError) -> str:
    return f"{error.message} {error.upstream_code or ''}".lower()


def is_duplicate_email(error: Any) -> bool:
    """True si un `DataAccessError` indica un email ya registrado."""
    if not isinstance(error, DataAccessError):
        return False
    if (error.upstream_code or "") in _DUPLICATE_CODES:
        return True
    return any(fragment in _haystack(error) for fragment in _DUPLICATE_FRAGMENTS)


def is_invalid_credentials(error: Any) -> bool:
    """True si un `DataAccessError` indica credenciales incorrectas."""
    if not isinstance(error, DataAccessError):
        return False
    if (error.upstream_code or "") in _INVALID_CREDENTIAL_CODES:
        return True
    if error.upstream_status in (400, 401):
        return any(f in _haystack(error) for f in _INVALID_CREDENTIAL_FRAGMENTS)
    return False


def error_payload(error: AppError) -> Dict[str, Any]:
    """Cuerpo JSON para el cliente. Conserva la clave `error` que espera el frontend."""
    return {
        "success": False,
        "error": error.message,
        "code": error.code,
        **({k: v for k, v in error.details.items() if v} if error.details else {}),
    }


def error_status(error: AppError) -> int:
    """Código HTTP asociado al error."""
    return error.status_code
