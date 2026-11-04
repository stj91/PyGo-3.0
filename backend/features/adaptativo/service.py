"""Reglas adaptativas de visibilidad en la interfaz.

Qué opciones de UI se ofrecen según el nivel alcanzado por el usuario.
"""

from typing import Any, Dict, Optional

from core import supabase
from core.errors import NotFoundError
from core.supabase import eq

NIVEL_PRINCIPIANTE = "Principiante"
NIVEL_AVANZADO = "Avanzado"


# --- Acceso a datos ---------------------------------------------------------


def buscar_nivel(usuario_id: str) -> Optional[Dict[str, Any]]:
    """Nivel asignado al usuario, o `None` si el usuario no existe."""
    return supabase.select_one(
        "usuarios",
        columns="nivel_asignado",
        filters=(eq("id", usuario_id),),
        operation="buscar_nivel",
    )


# --- Reglas puras -----------------------------------------------------------


def configuracion_ui(nivel: str) -> Dict[str, Any]:
    """Opciones disponibles para un nivel dado. Pura."""
    return {
        "nivel_activo": nivel,
        "modo_oscuro_disponible": nivel != NIVEL_PRINCIPIANTE,
        "ajuste_dificultad_disponible": nivel != NIVEL_PRINCIPIANTE,
        "certificaciones_disponibles": nivel == NIVEL_AVANZADO,
    }


# --- Orquestación -----------------------------------------------------------


def obtener_estado(usuario_id: str) -> Dict[str, Any]:
    """Configuración adaptativa de UI del usuario."""
    usuario = buscar_nivel(usuario_id)
    if not usuario:
        raise NotFoundError("Usuario no encontrado.")

    nivel = usuario.get("nivel_asignado") or NIVEL_PRINCIPIANTE
    return configuracion_ui(nivel)
