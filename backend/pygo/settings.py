"""Configuración de Django para el backend PyGo.

Es una API JSON pura: no hay ORM, ni plantillas, ni admin, ni sesiones, así que
`INSTALLED_APPS` y `MIDDLEWARE` se quedan en lo mínimo imprescindible.
"""

import secrets
import sys
from pathlib import Path

from core.env import env_bool, env_list, env_str, load_env

BASE_DIR = Path(__file__).resolve().parent.parent

# Credenciales y configuración en backend/.env (ver .env.example). Las
# variables del entorno real siempre tienen prioridad sobre el fichero.
ENV = load_env((BASE_DIR / ".env",))

# --- Seguridad base ---------------------------------------------------------

# Sin SECRET_KEY en el entorno se genera una efímera por arranque: es seguro
# (no se publica ninguna clave en el repo) y suficiente porque no se firman
# sesiones ni cookies persistentes.
SECRET_KEY = env_str(ENV, "DJANGO_SECRET_KEY") or secrets.token_urlsafe(50)

DEBUG = env_bool(ENV, "DJANGO_DEBUG", default=False)

# Sólo loopback por defecto. Ampliar esta lista expone la API a otras máquinas.
ALLOWED_HOSTS = list(
    env_list(ENV, "DJANGO_ALLOWED_HOSTS", default=("127.0.0.1", "localhost", "[::1]"))
)

# --- Supabase ---------------------------------------------------------------

SUPABASE_URL = env_str(ENV, "SUPABASE_URL").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = env_str(ENV, "SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_TIMEOUT_SECONDS = int(env_str(ENV, "SUPABASE_TIMEOUT_SECONDS", "15"))

# Segundos que se memoiza la validación de un token (0 desactiva la caché).
AUTH_CACHE_SECONDS = int(env_str(ENV, "AUTH_CACHE_SECONDS", "60"))

# --- Postgres directo (solo para `manage.py migrar_sql`) --------------------

# La API no usa estas credenciales: habla con Supabase por REST. Son únicamente
# para el runner de migraciones, que necesita una conexión SQL de verdad.
#
# Debe apuntar al pooler (Supavisor), no a db.<ref>.supabase.co: ese host solo
# publica registro AAAA, así que desde una red sin IPv6 agota el tiempo de
# espera. El usuario del pooler es `postgres.<project-ref>`, no `postgres`.
SUPABASE_DB_HOST = env_str(ENV, "SUPABASE_DB_HOST")
SUPABASE_DB_PORT = env_str(ENV, "SUPABASE_DB_PORT", "5432")
SUPABASE_DB_NAME = env_str(ENV, "SUPABASE_DB_NAME", "postgres")
SUPABASE_DB_USER = env_str(ENV, "SUPABASE_DB_USER")
# Si se deja vacía, `migrar_sql` la pide por teclado y no toca el disco.
SUPABASE_DB_PASSWORD = env_str(ENV, "SUPABASE_DB_PASSWORD")

# El catálogo de cursos y el contenido de las lecciones se sirven sin sesión,
# igual que hacía el backend Node (el frontend no protege esas rutas). Ponerlo
# a true exige token también para leer contenido.
REQUIRE_AUTH_FOR_CONTENT = env_bool(ENV, "PYGO_REQUIRE_AUTH_FOR_CONTENT", default=False)

# Fallo temprano y explícito, como hacía src/config/supabase.js. Se omite en
# comandos de gestión que no necesitan credenciales.
_NEEDS_SUPABASE = not any(arg in sys.argv for arg in ("check", "collectstatic", "help", "--help"))
if _NEEDS_SUPABASE and not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
    raise RuntimeError(
        "Faltan variables de entorno requeridas para Supabase "
        "(SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY). "
        "Defínelas en backend/.env (copia backend/.env.example)."
    )

# --- Aplicación -------------------------------------------------------------

INSTALLED_APPS = [
    "corsheaders",
    # No declara modelos: está aquí solo para que Django encuentre la orden de
    # gestión `migrar_sql` en core/management/commands/.
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "pygo.urls"
WSGI_APPLICATION = "pygo.wsgi.application"
ASGI_APPLICATION = "pygo.asgi.application"

# Sin ORM: los datos viven en Supabase y se consultan vía su API REST.
DATABASES = {}

# Las rutas replican exactamente las de Express (sin barra final), así que no se
# redirige nada: un 301 en un POST rompería la petición.
APPEND_SLASH = False

# --- CORS -------------------------------------------------------------------

# Vite usa 5173 y salta a 5174, 5175... si el puerto está ocupado, así que se
# permiten varios. Sólo orígenes de loopback: nada de comodines.
CORS_ALLOWED_ORIGINS = list(
    env_list(
        ENV,
        "CORS_ALLOWED_ORIGINS",
        default=(
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
        ),
    )
)
CORS_ALLOW_CREDENTIALS = True

# --- Internacionalización ---------------------------------------------------

LANGUAGE_CODE = "es"
TIME_ZONE = env_str(ENV, "TIME_ZONE", "UTC")
USE_I18N = False
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Logging ----------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
