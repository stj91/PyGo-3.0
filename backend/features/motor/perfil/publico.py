"""Vista pública del perfil (`PerfilPublico`): lo que el alumno puede ver de sí mismo. **Pura.**"""

from typing import Any, Dict, Iterable, List

from ..tipos import Catalogo, Perfil
from ._comun import a_iso


def perfil_publico(perfil: Perfil, intereses_declarados: Iterable[str], catalogo: Catalogo) -> Dict[str, Any]:
    """`PerfilPublico` sin campos internos.

    `dominio` lista solo conceptos con evidencia, ordenados por área y nombre.
    `cursos_completados` mantiene el orden del perfil y omite los cursos que ya
    no están publicados.
    """
    conceptos = catalogo.get("conceptos", {})
    cursos = catalogo.get("cursos", {})

    dominio: List[Dict[str, Any]] = []
    for clave, evidencias in perfil.get("evidencias", {}).items():
        if evidencias < 1 or clave not in perfil.get("dominio", {}):
            continue
        concepto = conceptos.get(clave)
        area = (concepto["area"] or clave) if concepto else None
        dominio.append({
            "clave": clave,
            "nombre": concepto["nombre"] if concepto else clave,
            "area": area,
            "dominio": perfil["dominio"][clave],
            "evidencias": evidencias,
        })
    dominio.sort(key=lambda d: (d["area"] or "", d["nombre"], d["clave"]))

    return {
        "nivel": perfil["nivel"],
        "nivel_asignado": perfil["nivel_asignado"],
        "nivel_inferido": perfil["nivel_inferido"],
        "intereses_declarados": sorted(set(intereses_declarados)),
        "dominio": dominio,
        "cursos_completados": [
            {
                "curso_id": curso_id,
                "codigo_curso": cursos[curso_id]["codigo_curso"],
                "titulo": cursos[curso_id]["titulo"],
            }
            for curso_id in perfil.get("cursos_completados", [])
            if curso_id in cursos
        ],
        "calculado_en": a_iso(perfil["calculado_en"]),
    }


def areas_declaradas(filas: Iterable[Dict[str, Any]], catalogo: Catalogo) -> List[str]:
    """Claves de área de las filas `origen='declarado'` vigentes (peso > 0)."""
    areas = catalogo.get("areas", {})
    return sorted({
        f["concepto_clave"]
        for f in filas
        if f.get("origen") == "declarado"
        and f.get("concepto_clave") in areas
        and float(f.get("peso") or 0) > 0
    })
