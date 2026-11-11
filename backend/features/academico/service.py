"""Lógica de los catálogos académicos.

Dos responsabilidades: servir los catálogos al desplegable del registro y
validar que lo que manda el cliente existe de verdad. La validación vive aquí
—y no solo en el `<select>` del navegador— porque un cliente puede enviar
cualquier cosa sin pasar por el formulario.
"""

from typing import Any, Dict, Optional

from core.errors import ValidationError
from core.functional import to_int

from . import repository


# --- Reglas puras -----------------------------------------------------------


def normalizar_id(valor: Any) -> Optional[int]:
    """Convierte el valor recibido a entero, o `None` si no se puede. Pura.

    El `<select>` del navegador manda siempre cadenas ("4"), así que hay que
    normalizar antes de comparar o guardar.
    """
    return to_int(valor)


# --- Orquestación -----------------------------------------------------------


def obtener_centros() -> list:
    """Catálogo de centros para el desplegable."""
    return repository.listar_centros()


def obtener_carreras() -> list:
    """Catálogo de carreras para el desplegable."""
    return repository.listar_carreras()


def validar_centro(valor: Any) -> Optional[int]:
    """Devuelve el id del centro si existe y está activo.

    `None` cuando no se envió nada: el centro es opcional, porque `usuarios`
    contempla gente sin vínculo universitario (`estatus_universitario`). Un
    valor presente pero inexistente sí es un error: aceptarlo en silencio
    dejaría la fila con un dato inventado.
    """
    if valor in (None, ""):
        return None

    centro_id = normalizar_id(valor)
    if centro_id is None or not repository.buscar_centro(centro_id):
        raise ValidationError(
            "El centro universitario seleccionado no existe.", campos=["centro_id"]
        )
    return centro_id


def validar_carrera(valor: Any) -> Optional[int]:
    """Devuelve el id de la carrera si existe y está activa. Ver `validar_centro`."""
    if valor in (None, ""):
        return None

    carrera_id = normalizar_id(valor)
    if carrera_id is None or not repository.buscar_carrera(carrera_id):
        raise ValidationError(
            "La carrera seleccionada no existe.", campos=["carrera_id"]
        )
    return carrera_id
