"""Pequeña librería de utilidades funcionales.

Todas las funciones son puras: no mutan sus argumentos ni tocan estado global.
Las estructuras se tratan como inmutables (se devuelven copias nuevas).
"""

from functools import reduce
from typing import Any, Callable, Dict, Iterable, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def pipe(value: Any, *fns: Callable) -> Any:
    """Aplica `fns` de izquierda a derecha sobre `value`.

    >>> pipe(" 3 ", str.strip, int, lambda n: n * 2)
    6
    """
    return reduce(lambda acc, fn: fn(acc), fns, value)


def compose(*fns: Callable) -> Callable:
    """Devuelve la composición de derecha a izquierda: compose(f, g)(x) == f(g(x))."""
    return lambda value: reduce(lambda acc, fn: fn(acc), reversed(fns), value)


def merge(*dicts: Optional[Dict]) -> Dict:
    """Une diccionarios en uno nuevo; los últimos ganan. Ignora `None`."""
    return {k: v for d in dicts if d for k, v in d.items()}


def pluck(key: str, default: Any = None) -> Callable[[Optional[Dict]], Any]:
    """Devuelve un getter de `key` apto para composición."""
    return lambda d: (d or {}).get(key, default)


def find(predicate: Callable[[T], bool], items: Iterable[T], default: Any = None) -> Any:
    """Primer elemento que cumple `predicate`, o `default`."""
    return next((item for item in items if predicate(item)), default)


def first(items: Optional[Sequence[T]], default: Any = None) -> Any:
    """Primer elemento de una secuencia, o `default` si está vacía o es `None`."""
    return items[0] if items else default


def index_by(key: str, rows: Iterable[Dict]) -> Dict[Any, Dict]:
    """Indexa filas por el valor de `key`. La última fila gana en caso de choque."""
    return {row.get(key): row for row in rows}


def omit_none(d: Dict) -> Dict:
    """Copia de `d` sin las claves cuyo valor es `None`."""
    return {k: v for k, v in d.items() if v is not None}


def pick(keys: Iterable[str], d: Dict) -> Dict:
    """Subconjunto de `d` limitado a `keys` presentes."""
    wanted = tuple(keys)
    return {k: d[k] for k in wanted if k in d}


def clean_text(value: Any) -> Optional[str]:
    """Recorta un texto; devuelve `None` si está vacío o no es texto."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def to_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Conversión total a entero: nunca lanza, devuelve `default` si no se puede."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def percentage(part: int, whole: int) -> int:
    """Porcentaje entero redondeado; 0 si `whole` es 0 (evita división por cero)."""
    return round((part / whole) * 100) if whole else 0


def partition(
    predicate: Callable[[T], bool], items: Iterable[T]
) -> Tuple[Tuple[T, ...], Tuple[T, ...]]:
    """Separa `items` en (cumplen, no cumplen)."""
    materialized = tuple(items)
    return (
        tuple(i for i in materialized if predicate(i)),
        tuple(i for i in materialized if not predicate(i)),
    )
