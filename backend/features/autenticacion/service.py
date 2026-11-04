"""Lógica de negocio de autenticación.

No conoce Django ni Supabase: recibe diccionarios, devuelve diccionarios y lanza
errores de dominio. Las reglas puras (validación, normalización) están separadas
de la orquestación con efectos.
"""

import logging
import re
from typing import Any, Dict

from core.errors import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    NotFoundError,
    RegistrationFailedError,
    ValidationError,
    WeakPasswordError,
    is_duplicate_email,
    is_invalid_credentials,
)
from core.functional import clean_text
from core.http import require_fields

from . import repository

logger = logging.getLogger(__name__)

NIVEL_INICIAL = "Principiante"
META_DIARIA_POR_DEFECTO_MINUTOS = 30
TEMA_INTERFAZ_POR_DEFECTO = "modo_claro"
LONGITUD_MINIMA_PASSWORD = 8
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# --- Reglas puras -----------------------------------------------------------


def normalizar_email(email: Any) -> str:
    """Email en minúsculas y sin espacios, para comparar y almacenar."""
    return str(email or "").strip().lower()


def validar_registro(datos: Dict[str, Any]) -> None:
    """Valida los datos de registro. Lanza `ValidationError` o `WeakPasswordError`."""
    require_fields(datos, ("email", "password", "nombre"))

    if not EMAIL_REGEX.match(normalizar_email(datos.get("email"))):
        raise ValidationError("El email no tiene un formato válido.", campos=["email"])

    if len(str(datos.get("password"))) < LONGITUD_MINIMA_PASSWORD:
        raise WeakPasswordError(
            f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.",
            campos=["password"],
        )


def validar_login(credenciales: Dict[str, Any]) -> None:
    """Valida las credenciales de acceso."""
    require_fields(credenciales, ("email", "password"), "Email y contraseña requeridos.")


def construir_perfil(usuario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
    """Fila a insertar en `usuarios` a partir de los datos de registro. Pura."""
    return {
        "id": usuario_id,
        "nombre": str(datos["nombre"]).strip(),
        "email": normalizar_email(datos["email"]),
        "carrera_area_estudio": clean_text(datos.get("carrera_area_estudio")),
        "centro_universitario": clean_text(datos.get("centro_universitario")),
        "nivel_asignado": NIVEL_INICIAL,
    }


def preferencias_iniciales(usuario_id: str) -> Dict[str, Any]:
    """Preferencias por defecto de un usuario nuevo. Pura.

    `tema_interfaz` es el enum real del esquema (`modo_claro`/`modo_oscuro`); el
    backend Node insertaba un campo `modo_oscuro` que no existe como columna.
    """
    return {
        "usuario_id": usuario_id,
        "meta_diaria_minutos": META_DIARIA_POR_DEFECTO_MINUTOS,
        "tema_interfaz": TEMA_INTERFAZ_POR_DEFECTO,
    }


# --- Orquestación -----------------------------------------------------------


def _revertir_cuenta_auth(usuario_id: str) -> None:
    """Deshace la cuenta de Auth creada cuando un paso posterior falla.

    Sin esto un registro a medias deja una cuenta huérfana que bloquearía el
    email para siempre. No propaga su propio fallo: el error original del
    registro es el relevante para el cliente.
    """
    try:
        repository.eliminar_cuenta_auth(usuario_id)
    except Exception:
        logger.exception(
            "No se pudo revertir la cuenta de Auth %s tras un registro fallido", usuario_id
        )


def registrar_usuario(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Registra un usuario: cuenta en Auth, perfil, preferencias y sesión.

    Devuelve `{"token": ..., "usuario": ...}`.
    """
    validar_registro(datos)

    email = normalizar_email(datos["email"])
    nombre = str(datos["nombre"]).strip()
    password = datos["password"]

    # 1. Cuenta en Supabase Auth.
    try:
        cuenta = repository.crear_cuenta_auth(email=email, password=password, nombre=nombre)
    except Exception as error:
        if is_duplicate_email(error):
            raise EmailAlreadyRegisteredError(cause=error) from error
        raise

    usuario_id = cuenta.get("id")
    if not usuario_id:
        raise RegistrationFailedError("Supabase no devolvió el identificador de la cuenta.")

    try:
        # 2. Perfil público con el nivel inicial.
        usuario = repository.insertar_usuario(construir_perfil(usuario_id, datos))

        # 3. Preferencias iniciales. No es crítico: el registro sigue siendo
        #    válido sin ellas y el usuario puede ajustarlas más tarde.
        try:
            repository.insertar_preferencias(preferencias_iniciales(usuario_id))
        except Exception:
            logger.exception("Error inicializando preferencias de %s", usuario_id)

        # 4. Sesión, para devolver un token usable de inmediato.
        sesion = repository.autenticar(email=email, password=password)
        if not sesion.get("token"):
            raise RegistrationFailedError(
                "La cuenta se creó pero no se pudo iniciar sesión. "
                "Intenta iniciar sesión manualmente."
            )

        return {"token": sesion["token"], "usuario": usuario}
    except Exception as error:
        _revertir_cuenta_auth(usuario_id)
        if is_duplicate_email(error):
            raise EmailAlreadyRegisteredError(cause=error) from error
        raise


def iniciar_sesion(credenciales: Dict[str, Any]) -> Dict[str, Any]:
    """Autentica al usuario y devuelve su token junto al perfil completo."""
    validar_login(credenciales)

    try:
        sesion = repository.autenticar(
            email=normalizar_email(credenciales["email"]),
            password=credenciales["password"],
        )
    except Exception as error:
        if is_invalid_credentials(error):
            raise InvalidCredentialsError(cause=error) from error
        raise

    if not sesion.get("token"):
        raise InvalidCredentialsError()

    usuario = repository.buscar_usuario_con_preferencias(sesion["user"].get("id"))
    if not usuario:
        raise NotFoundError("No se encontró el perfil asociado a esta cuenta.")

    return {"token": sesion["token"], "usuario": usuario}
