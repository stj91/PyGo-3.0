"""Orden de gestión `migrar_sql`: aplica las migraciones SQL pendientes.

    python3 manage.py migrar_sql              # aplica lo pendiente
    python3 manage.py migrar_sql --listar     # solo muestra el estado
    python3 manage.py migrar_sql --sellar 0001  # registra sin ejecutar
    python3 manage.py migrar_sql --simular    # dice qué haría, sin tocar nada

No usa el ORM (el proyecto no tiene `DATABASES`): delega en `psql` a través de
`core.migraciones`.
"""

import os
from getpass import getpass
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import migraciones

DIRECTORIO = Path(settings.BASE_DIR) / "migrations"


class Command(BaseCommand):
    help = "Aplica las migraciones SQL de backend/migrations contra Supabase."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--listar",
            action="store_true",
            help="Muestra el estado de cada migración y termina.",
        )
        parser.add_argument(
            "--sellar",
            metavar="PREFIJO",
            help=(
                "Registra como aplicadas, SIN ejecutarlas, las migraciones cuya "
                "versión empiece por PREFIJO. Para líneas base sobre una base de "
                "datos que ya tiene ese esquema."
            ),
        )
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Enumera lo que se aplicaría sin ejecutar nada.",
        )
        parser.add_argument(
            "--dsn",
            help="Cadena de conexión libpq completa (ignora la configuración del .env).",
        )

    # --- Conexión ----------------------------------------------------------

    def _credenciales(self, dsn_explicito):
        """Resuelve (dsn, password) desde los argumentos, el entorno o el .env."""
        if dsn_explicito:
            return dsn_explicito, None

        host = settings.SUPABASE_DB_HOST
        user = settings.SUPABASE_DB_USER
        if not host or not user:
            raise CommandError(
                "Falta la configuración de conexión a Postgres. Define en backend/.env\n"
                "  SUPABASE_DB_HOST=aws-0-<region>.pooler.supabase.com\n"
                "  SUPABASE_DB_USER=postgres.<project-ref>\n"
                "Los valores exactos están en el dashboard de Supabase:\n"
                "  Project Settings -> Database -> Connection string -> Session pooler\n"
                "Usa el pooler y no db.<ref>.supabase.co: ese host solo publica IPv6."
            )

        dsn = migraciones.dsn_desde(
            {
                "host": host,
                "port": settings.SUPABASE_DB_PORT,
                "dbname": settings.SUPABASE_DB_NAME,
                "user": user,
            }
        )

        # Orden de preferencia: .env -> PGPASSWORD del entorno (convención de
        # libpq, útil en CI) -> preguntar por teclado. Preguntar es el último
        # recurso pero el más seguro: así la contraseña no vive en ningún sitio.
        password = (
            settings.SUPABASE_DB_PASSWORD
            or os.environ.get("PGPASSWORD")
            or None
        )
        if not password:
            password = getpass(f"Contraseña de {user}@{host}: ") or None
        return dsn, password

    # --- Presentación ------------------------------------------------------

    def _estado(self, disponibles, registradas) -> None:
        if not disponibles:
            self.stdout.write("No hay migraciones en backend/migrations.")
            return

        for m in disponibles:
            if m.version not in registradas:
                etiqueta = self.style.WARNING("PENDIENTE")
            elif registradas[m.version] != m.huella:
                etiqueta = self.style.ERROR("MODIFICADA TRAS APLICARSE")
            else:
                etiqueta = self.style.SUCCESS("aplicada")
            self.stdout.write(f"  {m.nombre:<34} {etiqueta}")

    # --- Ejecución ---------------------------------------------------------

    def handle(self, *args, **opciones) -> None:
        if not DIRECTORIO.is_dir():
            raise CommandError(f"No existe el directorio {DIRECTORIO}.")

        disponibles = migraciones.leer(DIRECTORIO)
        dsn, password = self._credenciales(opciones.get("dsn"))

        try:
            migraciones.asegurar_registro(dsn, password)
            registradas = migraciones.aplicadas(dsn, password)
        except RuntimeError as error:
            raise CommandError(str(error)) from error

        if opciones["listar"]:
            self._estado(disponibles, registradas)
            return

        # Un fichero ya aplicado que cambió significa que el repo y la base de
        # datos han divergido. Se avisa y se sigue: corregirlo automáticamente
        # sería adivinar.
        for m, anterior in migraciones.divergencias(disponibles, registradas):
            self.stderr.write(
                self.style.ERROR(
                    f"  {m.nombre}: aplicada con huella {anterior}, ahora es {m.huella}. "
                    "El fichero se editó después de aplicarse."
                )
            )

        if opciones["sellar"]:
            self._sellar(dsn, password, disponibles, registradas, opciones)
            return

        self._aplicar(dsn, password, disponibles, registradas, opciones)

    def _sellar(self, dsn, password, disponibles, registradas, opciones) -> None:
        prefijo = opciones["sellar"]
        objetivo = migraciones.seleccionar(disponibles, prefijo)
        if not objetivo:
            raise CommandError(f"Ninguna migración empieza por «{prefijo}».")

        for m in objetivo:
            if m.version in registradas:
                self.stdout.write(f"  {m.nombre} ya estaba registrada, se omite.")
                continue
            if opciones["simular"]:
                self.stdout.write(f"  {m.nombre} se sellaría (sin ejecutar).")
                continue
            migraciones.sellar(dsn, password, m)
            self.stdout.write(
                self.style.SUCCESS(f"  {m.nombre} SELLADA (registrada sin ejecutar).")
            )

    def _aplicar(self, dsn, password, disponibles, registradas, opciones) -> None:
        por_hacer = migraciones.pendientes(disponibles, registradas)
        if not por_hacer:
            self.stdout.write(self.style.SUCCESS("Todo al día: no hay migraciones pendientes."))
            return

        for m in por_hacer:
            if opciones["simular"]:
                self.stdout.write(f"  {m.nombre} se aplicaría.")
                continue
            self.stdout.write(f"  {m.nombre} ... ", ending="")
            self.stdout.flush()
            try:
                migraciones.aplicar(dsn, password, m)
            except RuntimeError as error:
                self.stdout.write(self.style.ERROR("FALLO"))
                raise CommandError(
                    f"{error}\n\nLas migraciones anteriores sí se aplicaron. "
                    f"Corrige {m.nombre} y vuelve a ejecutar la orden."
                ) from error
            self.stdout.write(self.style.SUCCESS("aplicada"))
