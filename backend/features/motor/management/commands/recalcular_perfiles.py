"""manage.py recalcular_perfiles: batch nocturno del perfil (paquete 04).

Por usuario: intereses inferidos, abandono de inscripciones inactivas y foto en
`perfiles`. `--simular` calcula e imprime sin escribir nada. El fallo de un
usuario se registra y el batch sigue.
"""

import logging
import uuid

from django.core.management.base import BaseCommand, CommandError

from features.motor.catalogo import cargar_catalogo
from features.motor.perfil import repository, service

logger = logging.getLogger(__name__)

#: Usuarios por página.
TAMANO_PAGINA = 100


class Command(BaseCommand):
    help = "Recalcula los perfiles de todos los usuarios (batch nocturno)."

    def add_arguments(self, parser):
        parser.add_argument("--usuario", help="UUID de un único usuario.")
        parser.add_argument(
            "--simular", action="store_true", help="Calcula e imprime un resumen sin escribir nada."
        )

    def handle(self, *args, **options):
        simular = options["simular"]
        unico = options.get("usuario")
        if unico:
            try:
                unico = str(uuid.UUID(unico))
            except ValueError as exc:
                raise CommandError("--usuario debe ser un UUID.") from exc
        catalogo = cargar_catalogo()
        procesados = fallidos = 0

        for usuario_id in self._usuarios(unico):
            try:
                resumen = service.recalcular_perfil(usuario_id, catalogo, simular=simular)
            except Exception:
                fallidos += 1
                logger.exception("recalcular_perfiles: fallo con el usuario %s", usuario_id)
                self.stdout.write(f"{usuario_id}: ERROR")
                continue
            procesados += 1
            self.stdout.write(
                f"{usuario_id}: nivel={resumen['nivel']} inferido={resumen['nivel_inferido']} "
                f"intereses_inferidos={resumen['intereses_inferidos']} "
                f"abandonados={resumen['abandonados']}"
            )

        modo = " (simulado, sin escrituras)" if simular else ""
        self.stdout.write(f"Total: {procesados} procesados, {fallidos} con error{modo}.")

    @staticmethod
    def _usuarios(unico):
        if unico:
            yield unico
            return
        ultimo = None
        while True:
            pagina = repository.listar_usuarios(ultimo, TAMANO_PAGINA)
            yield from pagina
            if len(pagina) < TAMANO_PAGINA:
                return
            ultimo = pagina[-1]
