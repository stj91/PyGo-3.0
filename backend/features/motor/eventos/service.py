"""Servicio de eventos: valida, sella la fecha, descarta dobles clics e inserta."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from . import repository
from .validacion import es_duplicado, validar_evento

VENTANA_DUPLICADO_SEGUNDOS = 1


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def registrar_cliente(cuerpo: dict, usuario: Dict[str, Any]) -> Dict[str, Any]:
    """Registra un evento enviado por el navegador y devuelve `{id, tipo, fecha}`.

    Si es un doble clic (mismo evento hace menos de un segundo) no inserta nada y
    devuelve el existente.
    """
    evento = {**validar_evento(cuerpo, str(usuario["id"]), "cliente"), "fecha": _ahora()}
    desde = evento["fecha"] - timedelta(seconds=VENTANA_DUPLICADO_SEGUNDOS)
    previos = repository.recientes(evento["usuario_id"], evento["tipo"], desde)
    existente = _primer_duplicado(evento, previos)
    if existente is not None:
        return {"id": existente.get("id"), "tipo": existente.get("tipo"), "fecha": existente.get("fecha")}
    return repository.insertar(evento)


def _primer_duplicado(evento, previos) -> Optional[dict]:
    return next(
        (p for p in previos if es_duplicado(evento, [p], VENTANA_DUPLICADO_SEGUNDOS)),
        None,
    )


def registrar_servidor(usuario_id: str, tipo: str, **campos) -> None:
    """Registra un evento originado en el servidor.

    `campos` son los del `Evento` (objeto_tipo, objeto_id, curso_id, valor,
    datos, sesion_id). Valida con `origen="servidor"` e inserta; la `fecha` la
    pone el servidor. Lanza si la entrada no es válida (los ganchos ya lo
    capturan). Lo usan 01 ganchos, 03 inscripción y 08.
    """
    cuerpo = {**campos, "usuario_id": usuario_id, "tipo": tipo}
    evento = validar_evento(cuerpo, str(usuario_id), "servidor")
    repository.insertar({**evento, "fecha": _ahora()})
