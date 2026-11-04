"""Acceso a datos de autenticación. Única capa que habla con Supabase."""

from typing import Any, Dict, Optional

from core import supabase
from core.supabase import eq

#: Columnas del perfil junto a sus preferencias embebidas.
PERFIL_COLUMNS = "*, usuario_preferencias(*)"


def crear_cuenta_auth(*, email: str, password: str, nombre: str) -> Dict[str, Any]:
    """Crea la cuenta en Supabase Auth con el email ya confirmado."""
    return supabase.auth_create_user(
        email=email,
        password=password,
        user_metadata={"nombre": nombre},
    )


def eliminar_cuenta_auth(usuario_id: str) -> None:
    """Elimina una cuenta de Auth. Compensa un registro que falló a medias."""
    supabase.auth_delete_user(usuario_id)


def autenticar(*, email: str, password: str) -> Dict[str, Any]:
    """Valida credenciales contra Supabase. Devuelve `{token, refresh_token, user}`."""
    return supabase.auth_sign_in(email=email, password=password)


def insertar_usuario(perfil: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta el perfil en la tabla pública `usuarios`."""
    return supabase.insert("usuarios", perfil, operation="insertar_usuario")


def insertar_preferencias(preferencias: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Crea la fila inicial de preferencias del usuario."""
    return supabase.insert(
        "usuario_preferencias",
        preferencias,
        returning=False,
        operation="insertar_preferencias",
    )


def buscar_usuario_con_preferencias(usuario_id: str) -> Optional[Dict[str, Any]]:
    """Perfil del usuario con sus preferencias, o `None` si no existe."""
    return supabase.select_one(
        "usuarios",
        columns=PERFIL_COLUMNS,
        filters=(eq("id", usuario_id),),
        operation="buscar_usuario_con_preferencias",
    )
