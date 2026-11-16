"""Catálogo de eventos y su validación. Funciones puras: sin E/S ni reloj."""

import json
import math
import re
from typing import Any, Dict, Literal, Optional, Sequence

from core.errors import ForbiddenError, ValidationError

from ..tipos import Evento

#: tipo -> (origen permitido, objeto_tipo, rango de `valor` o None). Única fuente de verdad.
TIPOS = {
    "sesion_inicio":            ("cliente",  None,            None),
    "curso_vista":              ("cliente",  "curso",         None),
    "tema_abierto":             ("cliente",  "tema",          None),
    "busqueda":                 ("cliente",  None,            None),
    "valoracion":               ("cliente",  "curso",         (1, 5)),
    "recomendacion_mostrada":   ("servidor", "recomendacion", None),
    "recomendacion_clic":       ("servidor", "recomendacion", None),
    "recomendacion_descartada": ("servidor", "recomendacion", None),
    "curso_inscripcion":        ("servidor", "curso",         None),
    "quiz_intento":             ("servidor", "tema",          (0, 1)),
    "tema_completado":          ("servidor", "tema",          None),
    "curso_completado":         ("servidor", "curso",         (0, 100)),
    "diagnostico":              ("servidor", None,            (0, 1)),
}

ORIGENES_CURSO = frozenset({"catalogo", "recomendacion", "dashboard", "busqueda", "ruta"})
DISPOSITIVOS = frozenset({"movil", "tablet", "escritorio"})

MAX_TEXTO_BUSQUEDA = 100
MAX_BYTES_DATOS_SERVIDOR = 4096
#: `eventos.valor` es numeric(10,3): por encima de esto Postgres rechaza la fila.
MAX_VALOR_ABSOLUTO = 1_000_000

_RECOMENDACION_ID = re.compile(r"^r-[0-9a-f-]{8,40}\Z")
_SESION_ID = re.compile(r"^[A-Za-z0-9-]{1,40}\Z")


def es_recomendacion_id(valor: Any) -> bool:
    """True si `valor` tiene la forma de un id de recomendación (`r-…`). **Pura.**"""
    return isinstance(valor, str) and _RECOMENDACION_ID.match(valor) is not None


def _en(valor: Any, permitidos: frozenset) -> bool:
    return isinstance(valor, str) and valor in permitidos


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _entero_positivo(cuerpo: dict, campo: str) -> Optional[int]:
    valor = cuerpo.get(campo)
    if valor is None:
        return None
    if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0:
        return valor
    raise ValidationError(f"`{campo}` debe ser un entero positivo.", campos=[campo])


def _valor(cuerpo: dict, rango: Optional[tuple]) -> Optional[float]:
    valor = cuerpo.get("valor")
    if valor is None:
        if rango is not None:
            raise ValidationError("Este evento requiere `valor`.", campos=["valor"])
        return None
    if not _es_numero(valor):
        raise ValidationError("`valor` debe ser un número.", campos=["valor"])
    minimo, maximo = rango if rango is not None else (-MAX_VALOR_ABSOLUTO, MAX_VALOR_ABSOLUTO)
    if not minimo <= valor <= maximo:
        raise ValidationError(f"`valor` debe estar entre {minimo} y {maximo}.", campos=["valor"])
    return valor


def _sesion_id(cuerpo: dict) -> Optional[str]:
    valor = cuerpo.get("sesion_id")
    if valor is None:
        return None
    if isinstance(valor, str) and _SESION_ID.match(valor):
        return valor
    raise ValidationError("`sesion_id` no es válido.", campos=["sesion_id"])


def _datos_cliente(tipo: str, datos: dict) -> dict:
    """Solo las claves permitidas para el tipo; el resto se descarta sin error."""
    if tipo == "curso_vista":
        origen = datos.get("origen")
        recomendacion_id = datos.get("recomendacion_id")
        return {
            **({"origen": origen} if _en(origen, ORIGENES_CURSO) else {}),
            **({"recomendacion_id": recomendacion_id} if es_recomendacion_id(recomendacion_id) else {}),
        }
    if tipo == "busqueda":
        texto = datos.get("texto")
        return {"texto": texto[:MAX_TEXTO_BUSQUEDA]} if isinstance(texto, str) else {}
    if tipo == "sesion_inicio":
        dispositivo = datos.get("dispositivo")
        return {"dispositivo": dispositivo} if _en(dispositivo, DISPOSITIVOS) else {}
    return {}


def _datos_servidor(datos: dict) -> dict:
    try:
        serializado = json.dumps(datos, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("`datos` no es serializable a JSON.", campos=["datos"]) from exc
    if len(serializado.encode("utf-8")) > MAX_BYTES_DATOS_SERVIDOR:
        raise ValidationError("`datos` supera los 4 KB.", campos=["datos"])
    return json.loads(serializado)


def validar_evento(
    cuerpo: dict, usuario_id_autenticado: str, origen: Literal["cliente", "servidor"]
) -> Evento:
    """Valida y normaliza un evento. **Pura.**

    Devuelve un `Evento` nuevo (sin `fecha`, la pone el servicio). Lanza
    `ValidationError` si el evento no es válido y `ForbiddenError` si el
    `usuario_id` del cuerpo no es el autenticado. No muta `cuerpo`.
    """
    if not isinstance(cuerpo, dict):
        raise ValidationError("El evento debe ser un objeto JSON.")

    tipo = cuerpo.get("tipo")
    if not isinstance(tipo, str) or tipo not in TIPOS:
        raise ValidationError("Tipo de evento desconocido.", campos=["tipo"])
    origen_permitido, objeto_tipo, rango = TIPOS[tipo]
    if origen == "cliente" and origen_permitido == "servidor":
        raise ValidationError("Este evento solo lo registra el servidor.", campos=["tipo"])

    usuario_id = cuerpo.get("usuario_id")
    if usuario_id is not None and str(usuario_id) != str(usuario_id_autenticado):
        raise ForbiddenError("No puedes registrar eventos de otro usuario.")

    datos = cuerpo.get("datos")
    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ValidationError("`datos` debe ser un objeto.", campos=["datos"])
    datos = _datos_cliente(tipo, datos) if origen == "cliente" else _datos_servidor(datos)

    if objeto_tipo == "recomendacion" and not es_recomendacion_id(datos.get("recomendacion_id")):
        raise ValidationError(
            "`datos.recomendacion_id` no es válido.", campos=["datos.recomendacion_id"]
        )

    return {
        "usuario_id": str(usuario_id_autenticado),
        "tipo": tipo,
        "objeto_tipo": objeto_tipo,
        "objeto_id": _entero_positivo(cuerpo, "objeto_id"),
        "curso_id": _entero_positivo(cuerpo, "curso_id"),
        "valor": _valor(cuerpo, rango),
        "datos": datos,
        "sesion_id": _sesion_id(cuerpo),
    }


def es_duplicado(evento: Evento, recientes: Sequence[Evento], ventana_segundos=1) -> bool:
    """True si `recientes` ya contiene este evento dentro de la ventana (doble clic). **Pura.**

    Mismo usuario, tipo, `objeto_id` y `datos.recomendacion_id`.
    """
    return any(_mismo_evento(evento, otro, ventana_segundos) for otro in recientes)


def _clave_duplicado(evento: Dict[str, Any]) -> tuple:
    return (
        str(evento.get("usuario_id")),
        evento.get("tipo"),
        evento.get("objeto_id"),
        (evento.get("datos") or {}).get("recomendacion_id"),
    )


def _mismo_evento(evento: Evento, otro: Evento, ventana_segundos) -> bool:
    fecha, fecha_otro = evento.get("fecha"), otro.get("fecha")
    if fecha is None or fecha_otro is None:
        return False
    return (
        _clave_duplicado(evento) == _clave_duplicado(otro)
        and abs((fecha - fecha_otro).total_seconds()) <= ventana_segundos
    )
