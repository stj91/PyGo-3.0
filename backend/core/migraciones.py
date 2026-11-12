"""Runner de migraciones SQL numeradas.

El proyecto no usa el ORM de Django (`DATABASES = {}`), así que `makemigrations`
no tiene de dónde partir: el esquema vive en Supabase y se creó fuera del código.
Este módulo aporta lo mínimo para versionarlo igualmente — ficheros `.sql`
numerados en `backend/migrations/` y una tabla `schema_migrations` que registra
lo ya aplicado.

Estilo, igual que el resto del backend: las decisiones son funciones puras
(`ordenar`, `pendientes`, `huella`, `divergencias`) y los efectos se concentran
en `_psql`, la única función que lanza un proceso.

La ejecución se delega a `psql` en lugar de usar un driver: el backend no tiene
dependencias de base de datos (habla con Supabase por REST) y añadir psycopg
solo para esto sería desproporcionado.
"""

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

#: Nombre esperado de una migración: 4 dígitos, guion bajo y descripción.
PATRON_NOMBRE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")

TABLA_REGISTRO = "public.schema_migrations"

DDL_REGISTRO = f"""
create table if not exists {TABLA_REGISTRO} (
  version     text        primary key,
  nombre      text        not null,
  huella      text        not null,
  aplicada_en timestamptz not null default now(),
  sellada     boolean     not null default false
);
"""


class Migracion(NamedTuple):
    """Una migración en disco."""

    version: str
    nombre: str
    ruta: Path
    huella: str


# --- Funciones puras --------------------------------------------------------


def huella(contenido: str) -> str:
    """Checksum del contenido de una migración.

    Permite detectar que un fichero ya aplicado se editó después, que es la forma
    silenciosa de que el repo y la base de datos dejen de coincidir.
    """
    return hashlib.sha256(contenido.encode("utf-8")).hexdigest()[:16]


def version_de(nombre: str) -> Optional[str]:
    """Número de versión de un nombre de fichero, o `None` si no encaja."""
    match = PATRON_NOMBRE.match(nombre)
    return match.group(1) if match else None


def ordenar(migraciones: Iterable[Migracion]) -> List[Migracion]:
    """Migraciones ordenadas por versión ascendente. Pura."""
    return sorted(migraciones, key=lambda m: m.version)


def pendientes(
    disponibles: Sequence[Migracion], aplicadas: Dict[str, str]
) -> List[Migracion]:
    """Migraciones que todavía no están registradas. Pura."""
    return [m for m in ordenar(disponibles) if m.version not in aplicadas]


def divergencias(
    disponibles: Sequence[Migracion], aplicadas: Dict[str, str]
) -> List[Tuple[Migracion, str]]:
    """Migraciones aplicadas cuyo fichero cambió desde entonces. Pura.

    Devuelve pares `(migración, huella_registrada)`.
    """
    return [
        (m, aplicadas[m.version])
        for m in ordenar(disponibles)
        if m.version in aplicadas and aplicadas[m.version] != m.huella
    ]


def seleccionar(disponibles: Sequence[Migracion], prefijo: str) -> List[Migracion]:
    """Migraciones cuya versión o nombre empieza por `prefijo`. Pura."""
    return [
        m
        for m in ordenar(disponibles)
        if m.version.startswith(prefijo) or m.nombre.startswith(prefijo)
    ]


def dsn_desde(valores: Dict[str, Any]) -> str:
    """Construye una cadena de conexión libpq a partir de valores sueltos. Pura.

    La contraseña queda fuera a propósito: viaja por `PGPASSWORD` en el entorno
    del subproceso para que no aparezca en la línea de órdenes ni en los logs.
    """
    campos = (
        ("host", valores.get("host")),
        ("port", valores.get("port") or "5432"),
        ("dbname", valores.get("dbname") or "postgres"),
        ("user", valores.get("user")),
        ("sslmode", valores.get("sslmode") or "require"),
    )
    return " ".join(f"{k}={v}" for k, v in campos if v)


def usuario_pooler(referencia: str) -> str:
    """Usuario del pooler de Supabase para una referencia de proyecto. Pura.

    Supavisor exige `postgres.<project-ref>`, no `postgres` a secas.
    """
    return f"postgres.{referencia}"


def referencia_de_url(url: str) -> Optional[str]:
    """Extrae la referencia del proyecto de una URL de Supabase. Pura.

    >>> referencia_de_url("https://abcdefg.supabase.co")
    'abcdefg'
    """
    match = re.match(r"^https?://([a-z0-9]+)\.supabase\.(co|in)", (url or "").strip())
    return match.group(1) if match else None


# --- Efectos ----------------------------------------------------------------


def leer(directorio: Path) -> List[Migracion]:
    """Lee las migraciones del directorio, ignorando lo que no encaje en el patrón."""
    encontradas = []
    for ruta in sorted(directorio.glob("*.sql")):
        version = version_de(ruta.name)
        if version is None:
            continue
        encontradas.append(
            Migracion(
                version=version,
                nombre=ruta.name,
                ruta=ruta,
                huella=huella(ruta.read_text(encoding="utf-8")),
            )
        )
    return ordenar(encontradas)


def _psql(
    dsn: str,
    password: Optional[str],
    *,
    sql: Optional[str] = None,
    fichero: Optional[Path] = None,
) -> str:
    """Ejecuta SQL con `psql`. Única función del módulo con efectos externos.

    `ON_ERROR_STOP=1` es lo que convierte un error a mitad de un fichero en un
    fallo real en lugar de continuar con las órdenes siguientes.
    """
    orden = [
        "psql",
        dsn,
        "--no-psqlrc",
        "-v",
        "ON_ERROR_STOP=1",
        "-q",
        "-t",
        "-A",
    ]
    orden += ["-f", str(fichero)] if fichero else ["-c", sql or ""]

    entorno = {**os.environ}
    if password:
        entorno["PGPASSWORD"] = password

    resultado = subprocess.run(
        orden, capture_output=True, text=True, env=entorno, check=False
    )
    if resultado.returncode != 0:
        detalle = (resultado.stderr or resultado.stdout or "").strip()
        origen = fichero.name if fichero else "la consulta"
        raise RuntimeError(f"psql falló en {origen}:\n{detalle}")
    return resultado.stdout.strip()


def asegurar_registro(dsn: str, password: Optional[str]) -> None:
    """Crea la tabla de control si no existe."""
    _psql(dsn, password, sql=DDL_REGISTRO)


def aplicadas(dsn: str, password: Optional[str]) -> Dict[str, str]:
    """Versiones ya registradas, con su huella: `{version: huella}`."""
    salida = _psql(
        dsn,
        password,
        sql=f"select version, huella from {TABLA_REGISTRO} order by version;",
    )
    if not salida:
        return {}
    return dict(
        linea.split("|", 1) for linea in salida.splitlines() if "|" in linea
    )


def _registrar(
    dsn: str, password: Optional[str], migracion: Migracion, *, sellada: bool
) -> None:
    """Anota una migración como aplicada en la tabla de control."""
    _psql(
        dsn,
        password,
        sql=(
            f"insert into {TABLA_REGISTRO} (version, nombre, huella, sellada) "
            f"values ('{migracion.version}', '{migracion.nombre}', "
            f"'{migracion.huella}', {str(sellada).lower()}) "
            "on conflict (version) do update set "
            "nombre = excluded.nombre, huella = excluded.huella, "
            "sellada = excluded.sellada, aplicada_en = now();"
        ),
    )


def aplicar(dsn: str, password: Optional[str], migracion: Migracion) -> None:
    """Ejecuta una migración y la registra.

    El registro va después a propósito: si el SQL falla, la migración sigue
    pendiente y se puede reintentar tras corregir el fichero.
    """
    _psql(dsn, password, fichero=migracion.ruta)
    _registrar(dsn, password, migracion, sellada=False)


def sellar(dsn: str, password: Optional[str], migracion: Migracion) -> None:
    """Registra una migración como aplicada **sin ejecutarla**.

    Es lo que permite que una línea base conviva con una base de datos que ya
    tiene ese esquema: ejecutarla fallaría con 42P07 (`relation already
    exists`), y debe fallar. Sellarla declara «esto ya estaba aquí».
    """
    _registrar(dsn, password, migracion, sellada=True)
