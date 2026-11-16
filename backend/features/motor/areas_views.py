"""GET /api/motor/areas: las áreas de interés que puede elegir el alumno."""

from core.http import endpoint, ok

from .catalogo import cargar_catalogo


def areas_publicas(catalogo) -> list:
    """`[{clave, nombre}]` de las áreas, por nombre. Pura."""
    return sorted(
        (
            {"clave": clave, "nombre": catalogo["conceptos"][clave]["nombre"]}
            for clave in catalogo["areas"]
            if clave in catalogo["conceptos"]
        ),
        key=lambda a: (a["nombre"], a["clave"]),
    )


@endpoint("GET")
def listar_areas(request):
    """GET /api/motor/areas

    Pública, como `/api/carreras`: es metadato del catálogo (nombres de áreas),
    sin datos de ningún usuario, y alimenta el diagnóstico inicial.
    """
    return ok(areas=areas_publicas(cargar_catalogo()))
