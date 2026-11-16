"""Modelo de lectura del catálogo: cursos, módulos, conceptos y sus relaciones.

Tres partes:
- lectura (`_leer_*`): una consulta por tabla, a través de `core.supabase`;
- ensamblado (`ensamblar_catalogo`): función pura, también la usan 07 y 10 para
  montar el catálogo desde CSV o fixtures;
- `cargar_catalogo()`: lee y ensambla, memoizado en el proceso.

Nunca se consulta `opciones_ejercicios`: el catálogo no necesita respuestas.
"""

from typing import Any, Dict, Iterable, List, Optional, Sequence

from django.core.cache import cache

from core import supabase
from core.supabase import eq

from . import config
from .tipos import Catalogo, Concepto, Curso, TemaCatalogo

_CACHE_CLAVE = "pygo:motor:catalogo"

#: Factor de las etiquetas de módulo al combinarlas con las del curso.
_FACTOR_MODULO = 0.5


# --- Lectura (efectos) ------------------------------------------------------


def _leer_cursos() -> List[Dict[str, Any]]:
    return supabase.select(
        "cursos",
        columns="id,codigo_curso,titulo,descripcion,dificultad,nivel,publicado",
        filters=(eq("publicado", "true"),),
        order="id.asc",
        operation="motor:catalogo:cursos",
    )


def _leer_temas() -> List[Dict[str, Any]]:
    return supabase.select(
        "temas",
        columns="id,curso_id,orden,titulo",
        order="curso_id.asc,orden.asc",
        operation="motor:catalogo:temas",
    )


def _leer_conceptos() -> List[Dict[str, Any]]:
    return supabase.select(
        "conceptos",
        columns="id,clave,nombre,padre_id",
        operation="motor:catalogo:conceptos",
    )


def _leer_contenido() -> List[Dict[str, Any]]:
    filas = supabase.select(
        "contenido_concepto",
        columns="objeto_tipo,objeto_id,peso,conceptos(clave)",
        operation="motor:catalogo:contenido",
    )
    return [
        {
            "objeto_tipo": f.get("objeto_tipo"),
            "objeto_id": f.get("objeto_id"),
            "concepto_clave": _clave_embebida(f.get("conceptos")),
            "peso": f.get("peso"),
        }
        for f in filas
    ]


def _leer_prerrequisitos() -> List[Dict[str, Any]]:
    return supabase.select(
        "curso_prerrequisitos",
        columns="curso_id,requiere_curso_id,calificacion_minima",
        operation="motor:catalogo:prerrequisitos",
    )


def _leer_carrera_areas() -> List[Dict[str, Any]]:
    filas = supabase.select(
        "carrera_areas",
        columns="peso,carreras(clave),conceptos(clave)",
        operation="motor:catalogo:carrera_areas",
    )
    return [
        {
            "carrera_clave": _clave_embebida(f.get("carreras")),
            "area_clave": _clave_embebida(f.get("conceptos")),
            "peso": f.get("peso"),
        }
        for f in filas
    ]


def _leer_ejercicios_diagnostico() -> List[Dict[str, Any]]:
    return supabase.select(
        "ejercicios",
        columns="id,tema_id",
        filters=(eq("tipo", "evaluacion_tecnica"),),
        operation="motor:catalogo:ejercicios_diagnostico",
    )


def _clave_embebida(recurso: Any) -> Optional[str]:
    """`clave` de un recurso embebido de PostgREST (objeto, o lista de uno)."""
    if isinstance(recurso, list):
        recurso = recurso[0] if recurso else None
    return recurso.get("clave") if isinstance(recurso, dict) else None


# --- Ensamblado (puro) ------------------------------------------------------


def _max_merge(*vectores: Dict[str, float]) -> Dict[str, float]:
    resultado: Dict[str, float] = {}
    for vector in vectores:
        for clave, peso in vector.items():
            if clave not in resultado or peso > resultado[clave]:
                resultado[clave] = peso
    return resultado


def _etiquetas(
    contenido: Iterable[Dict[str, Any]], objeto_tipo: str, conocidos: Dict[str, Concepto]
) -> Dict[int, Dict[str, float]]:
    """objeto_id -> {clave de concepto: peso}, ignorando conceptos desconocidos."""
    por_objeto: Dict[int, Dict[str, float]] = {}
    for fila in contenido:
        clave = fila.get("concepto_clave")
        if fila.get("objeto_tipo") != objeto_tipo or clave not in conocidos:
            continue
        objeto_id = int(fila["objeto_id"])
        por_objeto[objeto_id] = _max_merge(
            por_objeto.get(objeto_id, {}), {clave: float(fila.get("peso", 1.0))}
        )
    return por_objeto


def _conceptos(filas: Iterable[Dict[str, Any]]) -> Dict[str, Concepto]:
    filas = list(filas)
    clave_por_id = {f["id"]: f["clave"] for f in filas}
    return {
        f["clave"]: {
            "id": int(f["id"]),
            "clave": f["clave"],
            "nombre": f["nombre"],
            "area": clave_por_id.get(f.get("padre_id")) if f.get("padre_id") is not None else None,
        }
        for f in filas
    }


def _areas_de(claves: Iterable[str], conceptos: Dict[str, Concepto]) -> List[str]:
    areas = set()
    for clave in claves:
        concepto = conceptos.get(clave)
        if concepto is None:
            continue
        areas.add(concepto["area"] if concepto["area"] is not None else clave)
    return sorted(areas)


def ensamblar_catalogo(
    cursos: Sequence[Dict[str, Any]],
    temas: Sequence[Dict[str, Any]],
    conceptos: Sequence[Dict[str, Any]],
    contenido: Sequence[Dict[str, Any]],
    prerrequisitos: Sequence[Dict[str, Any]],
    carrera_areas: Sequence[Dict[str, Any]],
    ejercicios_diagnostico: Sequence[Dict[str, Any]],
) -> Catalogo:
    """Construye el `Catalogo` a partir de filas planas. **Pura.**

    Formas de entrada (columnas de cada tabla, con las claves embebidas ya
    aplanadas):
    - cursos: `{id, codigo_curso, titulo, descripcion, dificultad, nivel, publicado}`
    - temas: `{id, curso_id, orden, titulo}`
    - conceptos: `{id, clave, nombre, padre_id}`
    - contenido: `{objeto_tipo: 'curso'|'tema', objeto_id, concepto_clave, peso}`
    - prerrequisitos: `{curso_id, requiere_curso_id, calificacion_minima}`
    - carrera_areas: `{carrera_clave, area_clave, peso}`
    - ejercicios_diagnostico: `{id, tema_id}`

    Reglas: los cursos no publicados se excluyen; `Curso.conceptos` combina por
    máximo las etiquetas del curso y 0.5 × las de cada módulo; `Curso.areas`
    son las áreas de esos conceptos, ordenadas; los temas van por `orden`.
    """
    por_clave = _conceptos(conceptos)
    etiquetas_curso = _etiquetas(contenido, "curso", por_clave)
    etiquetas_tema = _etiquetas(contenido, "tema", por_clave)

    publicados = [c for c in cursos if c.get("publicado", True)]
    ids_publicados = {int(c["id"]) for c in publicados}

    temas_por_curso: Dict[int, List[TemaCatalogo]] = {}
    for t in sorted(temas, key=lambda t: (int(t["curso_id"]), int(t["orden"]), int(t["id"]))):
        curso_id = int(t["curso_id"])
        if curso_id not in ids_publicados:
            continue
        tema: TemaCatalogo = {
            "id": int(t["id"]),
            "curso_id": curso_id,
            "orden": int(t["orden"]),
            "titulo": t.get("titulo") or "",
            "conceptos": dict(etiquetas_tema.get(int(t["id"]), {})),
        }
        temas_por_curso[curso_id] = [*temas_por_curso.get(curso_id, []), tema]

    prerrequisitos_por_curso: Dict[int, List[Dict[str, Any]]] = {}
    for p in sorted(prerrequisitos, key=lambda p: (int(p["curso_id"]), int(p["requiere_curso_id"]))):
        curso_id = int(p["curso_id"])
        prerrequisitos_por_curso[curso_id] = [
            *prerrequisitos_por_curso.get(curso_id, []),
            {
                "curso_id": int(p["requiere_curso_id"]),
                "calificacion_minima": float(
                    p["calificacion_minima"] if p.get("calificacion_minima") is not None else 80
                ),
            },
        ]

    def curso(c: Dict[str, Any]) -> Curso:
        curso_id = int(c["id"])
        temas_curso = temas_por_curso.get(curso_id, [])
        vector = _max_merge(
            etiquetas_curso.get(curso_id, {}),
            *(
                {clave: peso * _FACTOR_MODULO for clave, peso in t["conceptos"].items()}
                for t in temas_curso
            ),
        )
        return {
            "id": curso_id,
            "codigo_curso": c["codigo_curso"],
            "titulo": c.get("titulo") or "",
            "descripcion": c.get("descripcion") or "",
            "dificultad": int(c.get("dificultad") or 1),
            "nivel": c.get("nivel") or "Principiante",
            "publicado": True,
            "conceptos": vector,
            "areas": _areas_de(vector, por_clave),
            "prerrequisitos": prerrequisitos_por_curso.get(curso_id, []),
            "temas": temas_curso,
        }

    areas = {
        clave: sorted(k for k, c in por_clave.items() if c["area"] == clave)
        for clave, concepto in por_clave.items()
        if concepto["area"] is None
    }

    carreras: Dict[str, Dict[str, float]] = {}
    for fila in carrera_areas:
        carrera, area = fila.get("carrera_clave"), fila.get("area_clave")
        if not carrera or area not in areas:
            continue
        carreras[carrera] = {**carreras.get(carrera, {}), area: float(fila["peso"])}

    return {
        "cursos": {int(c["id"]): curso(c) for c in publicados},
        "conceptos": por_clave,
        "areas": areas,
        "carrera_areas": carreras,
        "ejercicios_diagnostico": {
            int(e["id"]): int(e["tema_id"]) for e in ejercicios_diagnostico
        },
    }


# --- Carga memoizada --------------------------------------------------------


def cargar_catalogo() -> Catalogo:
    """Catálogo publicado, memoizado en el proceso `CATALOGO_CACHE_SEGUNDOS`.

    Usa la caché de Django (en memoria del proceso, como `core/auth.py`). Cada
    lectura de la caché devuelve una copia, así que quien la modifique no
    contamina a los demás. `0` desactiva la memoización.
    """
    segundos = config.CATALOGO_CACHE_SEGUNDOS
    if segundos > 0:
        guardado = cache.get(_CACHE_CLAVE)
        if guardado is not None:
            return guardado

    catalogo = ensamblar_catalogo(
        _leer_cursos(),
        _leer_temas(),
        _leer_conceptos(),
        _leer_contenido(),
        _leer_prerrequisitos(),
        _leer_carrera_areas(),
        _leer_ejercicios_diagnostico(),
    )

    if segundos > 0:
        cache.set(_CACHE_CLAVE, catalogo, segundos)
    return catalogo


def invalidar_catalogo() -> None:
    """Olvida el catálogo memoizado; la próxima carga vuelve a leer la base."""
    cache.delete(_CACHE_CLAVE)
