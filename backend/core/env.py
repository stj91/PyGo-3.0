"""Carga de variables de entorno sin dependencias externas.

Reemplaza a `dotenv` del backend Node. El parseo es una función pura sobre texto,
de modo que es testeable sin tocar el sistema de ficheros.
"""

import os
from pathlib import Path
from typing import Dict, Iterable, Optional

_TRUTHY = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSY = frozenset({"0", "false", "f", "no", "n", "off", ""})


def _strip_quotes(value: str) -> str:
    """Quita un par de comillas envolventes, si existe."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_line(line: str) -> Optional[tuple]:
    """Convierte `CLAVE=valor` en una tupla. Devuelve `None` para líneas ignorables."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, _, raw_value = stripped.partition("=")
    key = key.strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()

    return (key, _strip_quotes(raw_value.strip())) if key else None


def parse_env(text: str) -> Dict[str, str]:
    """Parsea el contenido de un fichero `.env`. Función pura."""
    pairs = (_parse_line(line) for line in text.splitlines())
    return dict(pair for pair in pairs if pair is not None)


def read_env_file(path: Path) -> Dict[str, str]:
    """Lee y parsea un `.env`. Devuelve `{}` si no existe o no es legible."""
    try:
        return parse_env(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}


def load_env(paths: Iterable[Path]) -> Dict[str, str]:
    """Combina varios `.env` (los primeros tienen prioridad) con `os.environ` encima.

    El entorno real siempre gana sobre los ficheros, que es el comportamiento
    esperado al desplegar.
    """
    from_files: Dict[str, str] = {}
    for path in paths:
        for key, value in read_env_file(path).items():
            from_files.setdefault(key, value)

    return {**from_files, **os.environ}


def env_str(source: Dict[str, str], key: str, default: str = "") -> str:
    """Lee una variable de texto con valor por defecto."""
    value = source.get(key)
    return value if value not in (None, "") else default


def env_bool(source: Dict[str, str], key: str, default: bool = False) -> bool:
    """Lee una variable booleana tolerando `true/1/yes/on` y sus negativos."""
    raw = source.get(key)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUTHY:
        return True
    if normalized in _FALSY:
        return False
    return default


def env_list(source: Dict[str, str], key: str, default: tuple = ()) -> tuple:
    """Lee una lista separada por comas, descartando elementos vacíos."""
    raw = source.get(key)
    if not raw:
        return tuple(default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())
