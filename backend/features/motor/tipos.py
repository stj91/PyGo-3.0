"""Formas de datos compartidas por todo el motor (00-arquitectura.md §4).

Son `TypedDict`: documentación y comprobación de tipos. En ejecución los
valores son diccionarios normales. Todos los ids son `int` salvo `usuario_id`
(`str`, un UUID). Las fechas son `datetime` con zona horaria en Python y
cadenas ISO-8601 UTC en JSON.
"""

from datetime import datetime
from typing import Dict, List, Literal, Optional, TypedDict

Nivel = Literal["Principiante", "Intermedio", "Avanzado"]
EstadoInscripcion = Literal["activo", "completado", "abandonado"]
EstadoTema = Literal["Bloqueado", "desbloqueado", "actividades_de_refuerzo", "completado"]


class Concepto(TypedDict):
    id: int
    clave: str              # 'bucles'
    nombre: str
    area: Optional[str]     # clave del área padre; None para las propias áreas


class Prerrequisito(TypedDict):
    curso_id: int           # el curso requerido
    calificacion_minima: float


class TemaCatalogo(TypedDict):
    id: int
    curso_id: int
    orden: int
    titulo: str
    conceptos: Dict[str, float]          # clave de concepto -> peso


class Curso(TypedDict):
    id: int
    codigo_curso: str
    titulo: str
    descripcion: str
    dificultad: int                      # 1..5
    nivel: Nivel
    publicado: bool
    conceptos: Dict[str, float]          # etiquetas del curso + 0.5 × las de sus módulos, por máximo
    areas: List[str]                     # claves de área que cubren sus conceptos
    prerrequisitos: List[Prerrequisito]
    temas: List[TemaCatalogo]            # ordenados por `orden`


class Catalogo(TypedDict):
    cursos: Dict[int, Curso]             # solo publicados
    conceptos: Dict[str, Concepto]       # por clave, áreas incluidas
    areas: Dict[str, List[str]]          # clave de área -> claves de concepto
    carrera_areas: Dict[str, Dict[str, float]]   # clave de carrera -> {clave de área: peso}
    ejercicios_diagnostico: Dict[int, int]       # id de ejercicio de diagnóstico -> id de tema


class Inscripcion(TypedDict):
    curso_id: int
    estado: EstadoInscripcion
    porcentaje_avance_global: float
    calificacion_final: Optional[float]
    fecha_inscripcion: datetime
    completado_en: Optional[datetime]
    origen: Optional[str]


class Perfil(TypedDict):
    usuario_id: str
    nivel: Nivel                         # nivel efectivo (ver 04)
    nivel_asignado: Nivel
    nivel_inferido: Optional[Nivel]
    carrera_clave: Optional[str]
    intereses: Dict[str, float]          # clave de concepto -> peso 0..1 (áreas ya expandidas)
    dominio: Dict[str, float]            # clave de concepto -> 0..1
    evidencias: Dict[str, int]           # clave de concepto -> número
    inscripciones: Dict[int, Inscripcion]   # por curso_id
    cursos_completados: List[int]
    calificacion_por_curso: Dict[int, float]
    modulos_en_refuerzo: Dict[int, List[int]]   # curso_id -> ids de tema
    tasa_aprobacion_modulos: Optional[float]
    intentos_promedio: Optional[float]
    dias_inactivo: Optional[int]
    calculado_en: datetime


class Razon(TypedDict):
    origen: str             # 'regla:R02' | 'contenido' | 'colaborativo' | 'modelo:aprobacion@20261120-0300'
    texto: Optional[str]    # frase en español para el usuario, o None si no debe mostrarse
    aporte: float           # contribución de esta razón, en la escala de la estrategia


class Puntuacion(TypedDict):
    curso_id: int
    puntuacion: float       # en la escala propia de la estrategia; solo 'reglas' puede ser negativa
    razones: List[Razon]


class Regla(TypedDict):
    id: int
    codigo: str
    nombre: str
    descripcion: str
    ambito: Literal["filtro", "recomendacion", "adaptacion", "inferencia"]
    condicion: dict
    accion: dict
    prioridad: int
    activa: bool


class Similitud(TypedDict):
    similitud: float
    soporte: int


class ModeloActivo(TypedDict):
    nombre: str
    version: str
    caracteristicas: List[str]
    arbol: dict             # árbol exportado (07)


class Contexto(TypedDict):
    catalogo: Catalogo
    reglas: List[Regla]
    similitudes: Dict[int, Dict[int, Similitud]]   # curso_a -> curso_b -> Similitud
    modelo: Optional[ModeloActivo]
    ahora: datetime


class Evento(TypedDict, total=False):
    usuario_id: str
    tipo: str
    objeto_tipo: Optional[str]
    objeto_id: Optional[int]
    curso_id: Optional[int]
    valor: Optional[float]
    datos: dict
    sesion_id: Optional[str]
    fecha: datetime          # siempre la pone el servidor
