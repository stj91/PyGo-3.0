"""manage.py activar_modelo <nombre> <version> [--forzar]: cambia el modelo activo.

Comprobaciones: el F1 de la candidata debe superar las dos líneas base y, si la
versión activa se entrenó con el mismo dataset (mismo SHA-256), no ser peor
que ella. Un dataset distinto o un modelo sintético exigen `--forzar`.

Cambio: se desactiva la versión activa y se activa la nueva (el índice único
parcial impide dos activas). Si la activación falla, se reactiva la anterior.
La API memoiza el modelo `CATALOGO_CACHE_SEGUNDOS`: el cambio tarda eso en verse.
"""

from typing import List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError


def decidir_activacion(
    candidata: dict, activa: Optional[dict], forzar: bool
) -> Tuple[List[str], List[str]]:
    """`(errores, avisos)` a partir de las métricas de ambas versiones. **Pura.**

    Superar las líneas base y no empeorar con el mismo dataset no se puede
    forzar; el dataset distinto y el origen sintético, sí.
    """
    errores: List[str] = []
    avisos: List[str] = []
    f1 = float(candidata.get("f1", 0.0))
    for clave, nombre in (("f1_baseline_mayoritaria", "clase mayoritaria"),
                          ("f1_baseline_regla", "regla de dominio")):
        base = candidata.get(clave)
        if base is None or f1 <= float(base):
            errores.append(f"F1 {f1:.3f} no supera la línea base '{nombre}' ({base}).")

    if activa is not None:
        if activa.get("dataset_sha256") == candidata.get("dataset_sha256"):
            f1_activa = float(activa.get("f1", 0.0))
            if f1 < f1_activa:
                errores.append(
                    f"F1 {f1:.3f} es peor que el de la versión activa ({f1_activa:.3f}) "
                    "con el mismo dataset."
                )
        elif forzar:
            avisos.append("La versión activa se entrenó con otro dataset; se fuerza el cambio.")
        else:
            errores.append("La versión activa se entrenó con otro dataset: usa --forzar.")

    if candidata.get("origen") != "real":
        avisos.append("ATENCIÓN: este modelo se entrenó con datos SINTÉTICOS.")
        if not forzar:
            errores.append("Un modelo sintético solo se activa con --forzar.")
    return errores, avisos


class Command(BaseCommand):
    help = "Activa una versión entrenada del modelo (desactiva la anterior)."

    def add_arguments(self, parser):
        parser.add_argument("nombre")
        parser.add_argument("version")
        parser.add_argument("--forzar", action="store_true")

    def handle(self, *args, **options):
        from core import supabase
        from core.errors import DataAccessError
        from core.supabase import eq

        nombre, version = options["nombre"], options["version"]
        columnas = "id,nombre,version,metricas,activo"
        candidata = supabase.select_one(
            "modelos", columns=columnas, filters=(eq("nombre", nombre), eq("version", version)),
            operation="motor:modelo:candidata",
        )
        if candidata is None:
            raise CommandError(f"No existe el modelo {nombre}@{version}.")
        if candidata.get("activo"):
            self.stdout.write(f"{nombre}@{version} ya está activo.")
            return
        activa = supabase.select_one(
            "modelos", columns=columnas, filters=(eq("nombre", nombre), eq("activo", "true")),
            operation="motor:modelo:activo",
        )

        errores, avisos = decidir_activacion(
            candidata.get("metricas") or {},
            (activa.get("metricas") or {}) if activa else None,
            options["forzar"],
        )
        for aviso in avisos:
            self.stdout.write(self.style.WARNING(aviso))
        if errores:
            raise CommandError(" ".join(errores))

        if activa:
            supabase.update("modelos", {"activo": False}, filters=(eq("id", activa["id"]),),
                            operation="motor:modelo:desactivar")
        try:
            supabase.update("modelos", {"activo": True}, filters=(eq("id", candidata["id"]),),
                            operation="motor:modelo:activar")
        except DataAccessError as exc:
            if activa:
                supabase.update("modelos", {"activo": True}, filters=(eq("id", activa["id"]),),
                                operation="motor:modelo:reactivar")
            raise CommandError(
                f"No se pudo activar {nombre}@{version} ({exc}); se mantiene la versión anterior."
            ) from exc

        anterior = f" (antes {activa['version']})" if activa else ""
        self.stdout.write(self.style.SUCCESS(f"Activo: {nombre}@{version}{anterior}."))
