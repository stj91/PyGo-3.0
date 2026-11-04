"""Lógica de configuración del perfil de usuario.

Sobre el esquema real: `usuario_preferencias` no tiene columna `modo_oscuro`
(el backend Node escribía ahí y fallaba siempre). El equivalente es el enum
`tema_interfaz`, con valores `modo_claro` / `modo_oscuro`, así que el booleano
que manda el frontend se traduce a ese enum.
"""

from typing import Any, Dict

from core import supabase
from core.functional import clean_text, pick, to_int
from core.supabase import eq

MENSAJE_OK = "Configuración de usuario actualizada correctamente."

TEMA_OSCURO = "modo_oscuro"
TEMA_CLARO = "modo_claro"

#: Campos que el cliente envía y que existen tal cual en `usuario_preferencias`.
CAMPOS_PREFERENCIAS_DIRECTOS = ("meta_diaria_minutos", "meta_semanal_minutos")

#: Campos que el cliente envía pero que no tienen columna en el esquema actual.
#: Se ignoran en silencio en lugar de hacer fallar toda la petición.
CAMPOS_SIN_COLUMNA = ("dificultad_adaptativa",)


# --- Reglas puras -----------------------------------------------------------


def tema_interfaz(modo_oscuro: Any) -> str:
    """Traduce el booleano `modo_oscuro` al enum `tema_interfaz`. Pura."""
    return TEMA_OSCURO if bool(modo_oscuro) else TEMA_CLARO


def cambios_preferencias(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Preferencias a persistir a partir de la petición. Pura.

    Sólo se tocan los campos enviados: ausente significa "no cambiar".
    """
    directos = {
        campo: to_int(datos[campo], 0)
        for campo in CAMPOS_PREFERENCIAS_DIRECTOS
        if campo in datos
    }

    tema = (
        {"tema_interfaz": tema_interfaz(datos["modo_oscuro"])}
        if "modo_oscuro" in datos
        else {}
    )

    return {**directos, **tema, **pick(("tema_interfaz",), datos)}


def cambios_perfil(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Campos del perfil a actualizar. Pura."""
    carrera = clean_text(datos.get("carrera_area_estudio"))
    return {"carrera_area_estudio": carrera} if carrera else {}


def ignorados(datos: Dict[str, Any]) -> list:
    """Campos recibidos que no tienen columna donde guardarse. Pura."""
    return [campo for campo in CAMPOS_SIN_COLUMNA if campo in datos]


# --- Orquestación -----------------------------------------------------------


def actualizar_configuracion(usuario_id: str, datos: Dict[str, Any]) -> Dict[str, Any]:
    """Actualiza perfil y preferencias del usuario con los campos enviados."""
    perfil = cambios_perfil(datos)
    if perfil:
        supabase.update(
            "usuarios",
            perfil,
            filters=(eq("id", usuario_id),),
            operation="actualizar_perfil",
        )

    preferencias = cambios_preferencias(datos)
    if preferencias:
        # `usuario_preferencias` tiene `usuario_id` como clave primaria, así que
        # el upsert de PostgREST resuelve el conflicto correctamente.
        supabase.upsert(
            "usuario_preferencias",
            {"usuario_id": usuario_id, **preferencias},
            operation="actualizar_preferencias",
        )

    respuesta: Dict[str, Any] = {"mensaje": MENSAJE_OK}

    sin_guardar = ignorados(datos)
    if sin_guardar:
        respuesta["ignorados"] = sin_guardar

    return respuesta
