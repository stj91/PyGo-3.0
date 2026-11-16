"""Tests del paquete 05: candidatos, filtros duros, evaluador de reglas y puntuación. Sin red."""

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from features.motor import candidatos as cand
from features.motor import catalogo, config
from features.motor.estrategias import reglas as rg

AHORA = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)

# Ids de curso como en la base: PY-101..PY-301 (0002) y PY-401..PY-801 (0003).
PY101, PY201, PY301, PY401, PY501, PY601, PY701, PY801, OCULTO = 1, 2, 3, 4, 5, 6, 7, 8, 9


# --- Catálogo de 01-cimientos.md §2 -----------------------------------------

_CURSOS = [
    (PY101, "PY-101", "Fundamentos de Python", 1, "Principiante"),
    (PY201, "PY-201", "Control de Flujo", 1, "Principiante"),
    (PY301, "PY-301", "Programación Orientada a Objetos", 3, "Intermedio"),
    (PY401, "PY-401", "Funciones y Modularidad", 2, "Principiante"),
    (PY501, "PY-501", "Colecciones Avanzadas y Comprensiones", 3, "Intermedio"),
    (PY601, "PY-601", "Manejo de Errores y Archivos", 3, "Intermedio"),
    (PY701, "PY-701", "Herencia y Polimorfismo", 4, "Avanzado"),
    (PY801, "PY-801", "Librería Estándar y APIs", 4, "Avanzado"),
]

_AREAS = {
    "fundamentos": ("Fundamentos", ["variables_tipos", "colecciones", "condicionales", "bucles", "funciones"]),
    "poo": ("Programación orientada a objetos", ["poo_clases", "herencia_polimorfismo"]),
    "datos": ("Datos", ["diccionarios_conjuntos", "comprensiones", "json_apis"]),
    "automatizacion": ("Automatización", ["excepciones", "archivos", "libreria_estandar", "modulos"]),
}

_ETIQUETAS_CURSO = {
    PY101: {"variables_tipos": 1, "colecciones": 0.6},
    PY201: {"condicionales": 1, "bucles": 1},
    PY401: {"funciones": 1, "modulos": 0.7},
    PY301: {"poo_clases": 1},
    PY501: {"diccionarios_conjuntos": 1, "comprensiones": 1, "colecciones": 0.5},
    PY601: {"excepciones": 1, "archivos": 1},
    PY701: {"herencia_polimorfismo": 1, "poo_clases": 0.6},
    PY801: {"libreria_estandar": 1, "json_apis": 1, "modulos": 0.5},
}

_ETIQUETAS_TEMA = {
    (PY101, 1): {"variables_tipos": 1}, (PY101, 2): {"colecciones": 1},
    (PY201, 1): {"condicionales": 1}, (PY201, 2): {"bucles": 1},
    (PY301, 1): {"poo_clases": 1},
    (PY401, 1): {"funciones": 1}, (PY401, 2): {"modulos": 0.7, "funciones": 0.3},
    (PY501, 1): {"diccionarios_conjuntos": 1}, (PY501, 2): {"comprensiones": 1},
    (PY601, 1): {"excepciones": 1}, (PY601, 2): {"archivos": 1},
    (PY701, 1): {"herencia_polimorfismo": 1}, (PY701, 2): {"herencia_polimorfismo": 0.7, "poo_clases": 0.3},
    (PY801, 1): {"libreria_estandar": 1}, (PY801, 2): {"json_apis": 1},
}

_REQUIERE = {
    PY201: [PY101], PY401: [PY201], PY301: [PY401], PY501: [PY401],
    PY601: [PY401], PY701: [PY301], PY801: [PY501, PY601],
}


def _tema_id(curso_id, orden):
    return curso_id * 10 + orden


def _catalogo():
    conceptos, siguiente_id = [], 1
    for area, (nombre, hijos) in _AREAS.items():
        area_id = siguiente_id
        conceptos.append({"id": area_id, "clave": area, "nombre": nombre, "padre_id": None})
        siguiente_id += 1
        for clave in hijos:
            conceptos.append({"id": siguiente_id, "clave": clave, "nombre": clave, "padre_id": area_id})
            siguiente_id += 1

    cursos = [
        {"id": i, "codigo_curso": c, "titulo": t, "descripcion": "", "dificultad": d,
         "nivel": n, "publicado": True}
        for i, c, t, d, n in _CURSOS
    ] + [{"id": OCULTO, "codigo_curso": "PY-901", "titulo": "Oculto", "descripcion": "",
          "dificultad": 1, "nivel": "Principiante", "publicado": False}]
    temas = [
        {"id": _tema_id(c, o), "curso_id": c, "orden": o, "titulo": f"Módulo {o}"}
        for (c, o) in _ETIQUETAS_TEMA
    ]
    contenido = [
        {"objeto_tipo": "curso", "objeto_id": c, "concepto_clave": k, "peso": p}
        for c, etiquetas in _ETIQUETAS_CURSO.items() for k, p in etiquetas.items()
    ] + [
        {"objeto_tipo": "tema", "objeto_id": _tema_id(c, o), "concepto_clave": k, "peso": p}
        for (c, o), etiquetas in _ETIQUETAS_TEMA.items() for k, p in etiquetas.items()
    ]
    prerrequisitos = [
        {"curso_id": c, "requiere_curso_id": r, "calificacion_minima": 80}
        for c, requeridos in _REQUIERE.items() for r in requeridos
    ]
    return catalogo.ensamblar_catalogo(cursos, temas, conceptos, contenido, prerrequisitos, [], [])


CATALOGO = _catalogo()


def _inscripcion(curso_id, estado, calificacion=None, completado_en=None):
    return {
        "curso_id": curso_id, "estado": estado,
        "porcentaje_avance_global": 100.0 if estado == "completado" else 30.0,
        "calificacion_final": calificacion, "fecha_inscripcion": AHORA - timedelta(days=60),
        "completado_en": completado_en, "origen": None,
    }


def _perfil(nivel="Principiante", completados=None, activos=(), abandonados=(),
            dominio=None, intereses=None, refuerzo=None):
    """`Perfil` (00 §4) construido a mano. `completados` = {curso_id: calificación}, en orden."""
    completados = dict(completados or {})
    inscripciones = {}
    for i, (curso_id, nota) in enumerate(completados.items()):
        inscripciones[curso_id] = _inscripcion(
            curso_id, "completado", nota, AHORA - timedelta(days=30 - i))
    for curso_id in activos:
        inscripciones[curso_id] = _inscripcion(curso_id, "activo")
    for curso_id in abandonados:
        inscripciones[curso_id] = _inscripcion(curso_id, "abandonado")
    return {
        "usuario_id": "11111111-1111-1111-1111-111111111111",
        "nivel": nivel, "nivel_asignado": nivel, "nivel_inferido": None,
        "carrera_clave": None,
        "intereses": dict(intereses or {}),
        "dominio": dict(dominio or {}),
        "evidencias": {k: 1 for k in (dominio or {})},
        "inscripciones": inscripciones,
        "cursos_completados": list(completados),
        "calificacion_por_curso": dict(completados),
        "modulos_en_refuerzo": dict(refuerzo or {}),
        "tasa_aprobacion_modulos": None, "intentos_promedio": None, "dias_inactivo": None,
        "calculado_en": AHORA,
    }


# --- Reglas semilla, espejo de migrations/0008_motor_reglas.sql -------------

def _regla(id_, codigo, ambito, prioridad, condicion, accion):
    return {"id": id_, "codigo": codigo, "nombre": codigo, "descripcion": codigo,
            "ambito": ambito, "condicion": condicion, "accion": accion,
            "prioridad": prioridad, "activa": True}


def _nivel(n):
    return {"campo": "nivel", "op": "=", "valor": n}


def _r03(n):
    return {"filtro": {"campo": "curso.nivel", "op": "=", "valor": n}, "puntos": 2,
            "explicacion": "Encaja con tu nivel {nivel}."}


_SEMILLA = [
    _regla(1, "F01", "filtro", 100, {}, {}),
    _regla(2, "F02", "filtro", 90, {}, {}),
    _regla(3, "F03", "filtro", 100, {}, {}),
    _regla(4, "R01", "recomendacion", 50,
           {"ninguna": [{"campo": "cursos_completados", "op": "existe"}]},
           {"filtro": {"campo": "curso.dificultad", "op": "=", "valor": 1}, "puntos": 3,
            "explicacion": "Es un buen punto de partida para empezar con Python."}),
    _regla(5, "R02", "recomendacion", 90, {"campo": "cursos_completados", "op": "existe"},
           {"filtro": {"campo": "curso.es_siguiente_en_ruta", "op": "=", "valor": True}, "puntos": 4,
            "explicacion": "Es el siguiente paso después de {curso.prerrequisito_titulo}."}),
    _regla(6, "R03a", "recomendacion", 60, _nivel("Principiante"), _r03("Principiante")),
    _regla(7, "R03b", "recomendacion", 60, _nivel("Intermedio"), _r03("Intermedio")),
    _regla(8, "R03c", "recomendacion", 60, _nivel("Avanzado"), _r03("Avanzado")),
    _regla(9, "R04", "recomendacion", 70, {"campo": "intereses", "op": "existe"},
           {"filtro": {"campo": "curso.coincide_interes", "op": "=", "valor": True}, "puntos": 2,
            "explicacion": "Coincide con tu interés en {curso.area_nombre}."}),
    _regla(10, "R05", "recomendacion", 80, {"campo": "tiene_refuerzo", "op": "=", "valor": True},
           {"filtro": {"campo": "curso.prerrequisito_en_refuerzo", "op": "=", "valor": True},
            "puntos": -3,
            "explicacion": "Te conviene terminar el repaso de {curso.prerrequisito_refuerzo_titulo} antes."}),
    _regla(11, "R06", "recomendacion", 40, {},
           {"filtro": {"todas": [{"campo": "curso.dificultad", "op": ">=", "valor": 4},
                                 {"campo": "curso.dominio_conceptos_curso", "op": "<", "valor": 0.4}]},
            "puntos": -2, "explicacion": ""}),
]

REGLAS = sorted(_SEMILLA, key=lambda r: (-r["prioridad"], r["id"]))


def _contexto(reglas=None):
    return {"catalogo": CATALOGO, "reglas": REGLAS if reglas is None else reglas,
            "similitudes": {}, "modelo": None, "ahora": AHORA}


def _ids(cursos):
    return [c["id"] for c in cursos]


def _por_curso(puntuaciones):
    return {p["curso_id"]: p for p in puntuaciones}


def _origenes(p):
    return [r["origen"] for r in p["razones"]]


# --- Candidatos y filtros ---------------------------------------------------


class CandidatosTests(SimpleTestCase):
    def test_excluye_activos_completados_y_no_publicados(self):
        perfil = _perfil(completados={PY101: 90}, activos=[PY201], abandonados=[PY401])
        ids = _ids(cand.candidatos(perfil, CATALOGO))
        self.assertEqual(ids, [PY301, PY401, PY501, PY601, PY701, PY801])
        self.assertNotIn(OCULTO, ids)

    def test_abandonado_vuelve_a_ser_candidato(self):
        perfil = _perfil(abandonados=[PY101])
        self.assertIn(PY101, _ids(cand.candidatos(perfil, CATALOGO)))

    def test_ignora_cursos_no_publicados_aunque_esten_en_el_catalogo(self):
        cat = copy.deepcopy(CATALOGO)
        cat["cursos"][PY101]["publicado"] = False
        self.assertNotIn(PY101, _ids(cand.candidatos(_perfil(), cat)))


class PrerrequisitoCumplidoTests(SimpleTestCase):
    REQ_401 = {"curso_id": PY401, "calificacion_minima": 80.0}

    def test_completado_con_nota_suficiente(self):
        perfil = _perfil(completados={PY401: 80})
        self.assertTrue(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, False))

    def test_completado_con_nota_bajo_el_minimo_no_cumple(self):
        perfil = _perfil(completados={PY401: 79.5})
        self.assertFalse(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, False))

    def test_completado_sin_calificacion_cumple(self):
        # Completado sin nota (lo marca 0005 al 100 %): no se puede saber la nota real.
        perfil = {**_perfil(completados={PY401: 90}), "calificacion_por_curso": {}}
        self.assertTrue(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, False))

    def test_f02_activa_o_no(self):
        perfil = _perfil(nivel="Intermedio", dominio={"funciones": 0.8, "modulos": 0.7})
        self.assertTrue(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))
        self.assertFalse(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, False))

    def test_f02_nivel_alto_pero_dominio_bajo_no_cumple(self):
        perfil = _perfil(nivel="Avanzado", dominio={"funciones": 0.5, "modulos": 0.5})
        self.assertFalse(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))

    def test_f02_concepto_sin_dato_usa_el_valor_de_partida_del_nivel(self):
        # `modulos` (PY-401, Principiante) sin dato: Intermedio parte de 0.5.
        # (1*0.4 + 0.7*0.5) / 1.7 = 0.441 < 0.6
        perfil = _perfil(nivel="Intermedio", dominio={"funciones": 0.4})
        self.assertFalse(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))
        with mock.patch.dict(config.DOMINIO_INICIAL_POR_NIVEL, {"Intermedio": 0.9}):
            # (0.4 + 0.7*0.9) / 1.7 = 0.606 >= 0.6
            self.assertTrue(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))

    def test_avanzado_sin_practica_cumple_por_su_nivel(self):
        # Sin ninguna evidencia, el nivel del diagnóstico basta: Avanzado parte de 0.7.
        perfil = _perfil(nivel="Avanzado")
        self.assertTrue(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))
        self.assertFalse(cand.prerrequisito_cumplido(_perfil(), self.REQ_401, CATALOGO, True))

    def test_prerrequisitos_pendientes(self):
        py801 = CATALOGO["cursos"][PY801]
        self.assertEqual(sorted(cand.prerrequisitos_pendientes(_perfil(), py801, CATALOGO)), [PY501, PY601])
        self.assertEqual(cand.prerrequisitos_pendientes(_perfil(nivel="Avanzado"), py801, CATALOGO), [])

    def test_f02_nivel_por_debajo_del_curso_requerido_no_cumple(self):
        req_501 = {"curso_id": PY501, "calificacion_minima": 80.0}
        perfil = _perfil(nivel="Principiante",
                         dominio={"diccionarios_conjuntos": 1, "comprensiones": 1, "colecciones": 1})
        self.assertFalse(cand.prerrequisito_cumplido(perfil, req_501, CATALOGO, True))
        perfil = {**perfil, "nivel": "Intermedio"}
        self.assertTrue(cand.prerrequisito_cumplido(perfil, req_501, CATALOGO, True))

    def test_lee_el_umbral_de_config_al_llamar(self):
        perfil = _perfil(nivel="Intermedio", dominio={"funciones": 0.8, "modulos": 0.8})
        with mock.patch.object(config, "F02_DOMINIO_MINIMO", 0.9):
            self.assertFalse(cand.prerrequisito_cumplido(perfil, self.REQ_401, CATALOGO, True))


class FiltrarTests(SimpleTestCase):
    def _filtrar(self, perfil, reglas):
        return _ids(cand.filtrar(perfil, cand.candidatos(perfil, CATALOGO), CATALOGO, reglas))

    def test_con_f01_solo_quedan_los_cursos_con_prerrequisitos_cumplidos(self):
        perfil = _perfil(completados={PY101: 90, PY201: 85})
        self.assertEqual(self._filtrar(perfil, REGLAS), [PY401])

    def test_f01_inactiva_no_comprueba_prerrequisitos(self):
        perfil = _perfil()
        sin_f01 = [r for r in REGLAS if r["codigo"] != "F01"]
        f01_apagada = [{**r, "activa": False} if r["codigo"] == "F01" else r for r in REGLAS]
        todos = [PY101, PY201, PY301, PY401, PY501, PY601, PY701, PY801]
        self.assertEqual(self._filtrar(perfil, sin_f01), todos)
        self.assertEqual(self._filtrar(perfil, f01_apagada), todos)

    def test_f02_inactiva_solo_cuenta_la_completitud(self):
        perfil = _perfil(nivel="Intermedio", completados={PY101: 90},
                         dominio={"condicionales": 0.9, "bucles": 0.9})
        self.assertEqual(self._filtrar(perfil, REGLAS), [PY201, PY401])
        sin_f02 = [r for r in REGLAS if r["codigo"] != "F02"]
        self.assertEqual(self._filtrar(perfil, sin_f02), [PY201])

    def test_alumno_nuevo_solo_ve_py101(self):
        self.assertEqual(self._filtrar(_perfil(), REGLAS), [PY101])

    def test_no_modifica_la_entrada(self):
        perfil = _perfil(completados={PY101: 90})
        cursos = cand.candidatos(perfil, CATALOGO)
        antes = copy.deepcopy((perfil, cursos, CATALOGO, REGLAS))
        cand.filtrar(perfil, cursos, CATALOGO, REGLAS)
        self.assertEqual((perfil, cursos, CATALOGO, REGLAS), antes)


class SiguienteEnRutaTests(SimpleTestCase):
    def test_py801_con_un_prerrequisito_de_dos_no_es_siguiente(self):
        perfil = _perfil(completados={PY101: 90, PY201: 90, PY401: 90, PY501: 90})
        self.assertEqual(cand.siguiente_en_ruta(perfil, CATALOGO), [PY301, PY601])

    def test_py801_con_los_dos_prerrequisitos_es_siguiente(self):
        perfil = _perfil(completados={PY101: 90, PY201: 90, PY401: 90, PY501: 90, PY601: 85})
        self.assertEqual(cand.siguiente_en_ruta(perfil, CATALOGO), [PY301, PY801])

    def test_cursos_sin_prerrequisitos_y_f02_no_cuentan(self):
        perfil = _perfil(nivel="Avanzado", dominio={k: 1.0 for k in CATALOGO["conceptos"]})
        self.assertEqual(cand.siguiente_en_ruta(perfil, CATALOGO), [])

    def test_nota_insuficiente_no_es_siguiente(self):
        perfil = _perfil(completados={PY101: 70})
        self.assertEqual(cand.siguiente_en_ruta(perfil, CATALOGO), [])


# --- Hechos -----------------------------------------------------------------


class HechosTests(SimpleTestCase):
    def test_hechos_alumno(self):
        perfil = _perfil(nivel="Intermedio", completados={PY101: 90},
                         intereses={"json_apis": 1.0, "bucles": 0.5, "archivos": 0.3},
                         refuerzo={PY201: [21], PY401: []})
        h = rg.hechos_alumno(perfil)
        self.assertEqual(h["intereses"], ["bucles", "json_apis"])
        self.assertEqual(h["nivel"], "Intermedio")
        self.assertEqual(h["cursos_completados"], [PY101])
        self.assertTrue(h["tiene_refuerzo"])
        self.assertFalse(rg.hechos_alumno(_perfil(refuerzo={PY201: []}))["tiene_refuerzo"])

    def test_area_de_mayor_interes_y_su_nombre(self):
        perfil = _perfil(intereses={"json_apis": 0.6, "libreria_estandar": 0.6})
        h = rg.hechos_curso(perfil, CATALOGO["cursos"][PY801], CATALOGO, [])
        # empate entre automatizacion y datos -> alfabético
        self.assertEqual(h["area"], "automatizacion")
        self.assertEqual(h["area_nombre"], "Automatización")
        self.assertTrue(h["coincide_interes"])
        perfil = _perfil(intereses={"json_apis": 0.9, "libreria_estandar": 0.6})
        h = rg.hechos_curso(perfil, CATALOGO["cursos"][PY801], CATALOGO, [])
        self.assertEqual((h["area"], h["area_nombre"]), ("datos", "Datos"))

    def test_sin_intereses_no_hay_area(self):
        h = rg.hechos_curso(_perfil(), CATALOGO["cursos"][PY801], CATALOGO, [])
        self.assertIsNone(h["area"])
        self.assertIsNone(h["area_nombre"])
        self.assertFalse(h["coincide_interes"])

    def test_prerrequisito_titulo_el_completado_mas_reciente(self):
        curso = CATALOGO["cursos"][PY801]
        perfil = _perfil(completados={PY601: 90, PY501: 90})  # PY-501 es el más reciente
        h = rg.hechos_curso(perfil, curso, CATALOGO, [PY801])
        self.assertEqual(h["prerrequisito_titulo"], CATALOGO["cursos"][PY501]["titulo"])
        self.assertTrue(h["es_siguiente_en_ruta"])
        h = rg.hechos_curso(_perfil(), curso, CATALOGO, [])
        self.assertEqual(h["prerrequisito_titulo"], CATALOGO["cursos"][PY501]["titulo"])
        self.assertIsNone(rg.hechos_curso(_perfil(), CATALOGO["cursos"][PY101], CATALOGO, [])
                          ["prerrequisito_titulo"])

    def test_prerrequisito_en_refuerzo(self):
        perfil = _perfil(refuerzo={PY401: [41]})
        h = rg.hechos_curso(perfil, CATALOGO["cursos"][PY501], CATALOGO, [])
        self.assertTrue(h["prerrequisito_en_refuerzo"])
        self.assertEqual(h["prerrequisito_refuerzo_titulo"], "Funciones y Modularidad")
        h = rg.hechos_curso(perfil, CATALOGO["cursos"][PY201], CATALOGO, [])
        self.assertFalse(h["prerrequisito_en_refuerzo"])
        self.assertIsNone(h["prerrequisito_refuerzo_titulo"])

    def test_dominio_conceptos_curso(self):
        perfil = _perfil(dominio={"poo_clases": 1.0})
        h = rg.hechos_curso(perfil, CATALOGO["cursos"][PY301], CATALOGO, [])
        self.assertAlmostEqual(h["dominio_conceptos_curso"], 1.0)


# --- Evaluador --------------------------------------------------------------


class ObtenerTests(SimpleTestCase):
    def test_ruta_con_puntos_y_pasos_que_faltan(self):
        hechos = {"curso": {"nivel": "Intermedio", "x": None}, "nivel": "Avanzado"}
        self.assertEqual(rg.obtener(hechos, "curso.nivel"), "Intermedio")
        self.assertEqual(rg.obtener(hechos, "nivel"), "Avanzado")
        self.assertIsNone(rg.obtener(hechos, "curso.falta"))
        self.assertIsNone(rg.obtener(hechos, "nivel.mas"))
        self.assertIsNone(rg.obtener(hechos, "curso.x.y"))
        self.assertIsNone(rg.obtener(hechos, ""))


class CumpleTests(SimpleTestCase):
    HECHOS = {"n": 3, "f": 0.5, "s": "Intermedio", "b": True, "lista": ["a", "b"], "vacia": [],
              "nada": None, "curso": {"dificultad": 4}}

    def _hoja(self, campo, op, valor=None, con_valor=True):
        hoja = {"campo": campo, "op": op}
        if con_valor:
            hoja["valor"] = valor
        return rg.cumple(hoja, self.HECHOS)

    def test_condicion_vacia_siempre_se_cumple(self):
        self.assertTrue(rg.cumple({}, {}))

    def test_cada_operador(self):
        self.assertTrue(self._hoja("n", "=", 3))
        self.assertTrue(self._hoja("n", "=", 3.0))
        self.assertFalse(self._hoja("n", "=", 4))
        self.assertTrue(self._hoja("n", "!=", 4))
        self.assertFalse(self._hoja("n", "!=", 3))
        self.assertTrue(self._hoja("n", "<", 4))
        self.assertFalse(self._hoja("n", "<", 3))
        self.assertTrue(self._hoja("n", "<=", 3))
        self.assertTrue(self._hoja("f", ">", 0.4))
        self.assertFalse(self._hoja("f", ">", 0.5))
        self.assertTrue(self._hoja("curso.dificultad", ">=", 4))
        self.assertTrue(self._hoja("s", "<", "Z"))
        self.assertTrue(self._hoja("s", "en", ["Principiante", "Intermedio"]))
        self.assertFalse(self._hoja("s", "en", ["Avanzado"]))
        self.assertTrue(self._hoja("lista", "contiene", "a"))
        self.assertFalse(self._hoja("lista", "contiene", "z"))
        self.assertTrue(self._hoja("s", "contiene", "medio"))
        self.assertTrue(self._hoja("lista", "existe", con_valor=False))
        self.assertFalse(self._hoja("vacia", "existe", con_valor=False))
        self.assertFalse(self._hoja("nada", "existe", con_valor=False))
        self.assertFalse(self._hoja("falta", "existe", con_valor=False))
        self.assertTrue(self._hoja("n", "existe", con_valor=False))
        self.assertTrue(self._hoja("b", "=", True))
        self.assertTrue(self._hoja("vacia", "=", []))

    def test_campo_que_falta_es_falso_salvo_existe(self):
        for op, valor in (("=", None), ("!=", 1), ("<", 1), ("en", [None]), ("contiene", "a")):
            self.assertFalse(self._hoja("falta", op, valor), op)
            self.assertFalse(self._hoja("nada", op, valor), op)

    def test_tipos_incompatibles_son_falsos_sin_excepcion(self):
        self.assertFalse(self._hoja("s", "<", 3))
        self.assertFalse(self._hoja("n", ">=", "3"))
        self.assertFalse(self._hoja("n", "=", "3"))
        self.assertFalse(self._hoja("n", "!=", "3"))
        self.assertFalse(self._hoja("b", "=", 1))
        self.assertFalse(self._hoja("n", "=", True))
        self.assertFalse(self._hoja("lista", "<", 1))
        self.assertFalse(self._hoja("n", "contiene", 3))
        self.assertFalse(self._hoja("n", "en", [True, "3"]))

    def test_grupos_anidados(self):
        si = {"campo": "n", "op": "=", "valor": 3}
        no = {"campo": "n", "op": "=", "valor": 9}
        self.assertTrue(rg.cumple({"todas": [si, si]}, self.HECHOS))
        self.assertFalse(rg.cumple({"todas": [si, no]}, self.HECHOS))
        self.assertTrue(rg.cumple({"alguna": [no, si]}, self.HECHOS))
        self.assertFalse(rg.cumple({"alguna": [no]}, self.HECHOS))
        self.assertTrue(rg.cumple({"ninguna": [no]}, self.HECHOS))
        self.assertFalse(rg.cumple({"ninguna": [no, si]}, self.HECHOS))
        anidada = {"todas": [si, {"alguna": [no, {"ninguna": [no]}]}]}
        self.assertTrue(rg.cumple(anidada, self.HECHOS))
        self.assertTrue(rg.cumple({"todas": []}, self.HECHOS))
        self.assertFalse(rg.cumple({"alguna": []}, self.HECHOS))

    def test_operador_desconocido_es_falso(self):
        self.assertFalse(self._hoja("n", "==", 3))
        self.assertFalse(self._hoja("n", "__import__('os')", 3))
        # una hoja rota invalida toda la condición, también dentro de `ninguna`
        self.assertFalse(rg.cumple({"ninguna": [{"campo": "n", "op": "??", "valor": 1}]}, self.HECHOS))

    def test_condiciones_mal_formadas_son_falsas(self):
        for mala in (None, [], "n = 3", {"todas": {"campo": "n"}}, {"todas": [1]},
                     {"todas": [], "alguna": []}, {"campo": "n", "op": "=", "valor": 3, "x": 1},
                     {"op": "existe"}, {"campo": "n", "op": "="}, {"campo": "n", "op": "en", "valor": 3}):
            self.assertFalse(rg.cumple(mala, self.HECHOS), mala)

    def test_limite_de_profundidad(self):
        def anidar(n):
            nodo = {"campo": "n", "op": "=", "valor": 3}
            for _ in range(n):
                nodo = {"todas": [nodo]}
            return nodo

        self.assertEqual(rg.PROFUNDIDAD_MAXIMA, 5)
        self.assertTrue(rg.cumple(anidar(5), self.HECHOS))
        self.assertFalse(rg.cumple(anidar(6), self.HECHOS))
        self.assertTrue(any("anidados" in p for p in rg.validar_regla(
            {"codigo": "X", "ambito": "filtro", "condicion": anidar(6), "accion": {}})))


class ResolverTextoTests(SimpleTestCase):
    HECHOS = {"nivel": "Intermedio", "curso": {"prerrequisito_titulo": None, "titulo": "POO"}}

    def test_sustituye_marcadores(self):
        self.assertEqual(rg.resolver_texto("Encaja con tu nivel {nivel}.", self.HECHOS),
                         "Encaja con tu nivel Intermedio.")
        self.assertEqual(rg.resolver_texto("{curso.titulo} y {nivel}", self.HECHOS), "POO y Intermedio")
        self.assertEqual(rg.resolver_texto("Sin marcadores.", self.HECHOS), "Sin marcadores.")

    def test_marcador_sin_valor_anula_el_texto(self):
        self.assertIsNone(rg.resolver_texto("Después de {curso.prerrequisito_titulo}.", self.HECHOS))
        self.assertIsNone(rg.resolver_texto("Después de {curso.falta}.", self.HECHOS))

    def test_vacio_o_none_es_none(self):
        self.assertIsNone(rg.resolver_texto("", self.HECHOS))
        self.assertIsNone(rg.resolver_texto("   ", self.HECHOS))
        self.assertIsNone(rg.resolver_texto(None, self.HECHOS))

    def test_no_evalua_expresiones(self):
        texto = "{nivel.__class__} {1+1}"
        self.assertIsNone(rg.resolver_texto(texto, self.HECHOS))
        self.assertEqual(rg.resolver_texto("{1+1}", self.HECHOS), "{1+1}")


class ValidarReglaTests(SimpleTestCase):
    BUENA = REGLAS[0]

    def _problemas(self, **cambios):
        return rg.validar_regla({**dict(_SEMILLA[4]), **cambios})

    def test_reglas_semilla_validas(self):
        for regla in _SEMILLA:
            self.assertEqual(rg.validar_regla(regla), [], regla["codigo"])

    def test_cada_tipo_de_problema(self):
        hoja = {"campo": "curso.dificultad", "op": "=", "valor": 1}
        casos = {
            "codigo": self._problemas(codigo=""),
            "ámbito": self._problemas(ambito="otro"),
            "prioridad": self._problemas(prioridad="alta"),
            "activa": self._problemas(activa="sí"),
            "condición debe ser un objeto": self._problemas(condicion="siempre"),
            "operador desconocido": self._problemas(condicion={"campo": "n", "op": "~"}),
            "necesita `valor`": self._problemas(condicion={"campo": "n", "op": "<"}),
            "falta `campo`": self._problemas(condicion={"op": "existe"}),
            "claves desconocidas": self._problemas(condicion={"campo": "n", "op": "existe", "x": 1}),
            "una sola clave": self._problemas(condicion={"todas": [], "ninguna": []}),
            "debe ser una lista": self._problemas(condicion={"alguna": hoja}),
            "`en` necesita una lista": self._problemas(condicion={"campo": "n", "op": "en", "valor": 1}),
            "número o un texto": self._problemas(condicion={"campo": "n", "op": "<", "valor": [1]}),
            "`accion` debe ser un objeto": self._problemas(accion=[]),
            "falta `filtro`": self._problemas(accion={"puntos": 1}),
            "`puntos` debe ser un número": self._problemas(accion={"filtro": hoja, "puntos": "3"}),
            "`explicacion` debe ser texto": self._problemas(
                accion={"filtro": hoja, "puntos": 1, "explicacion": 3}),
            "llaves": self._problemas(accion={"filtro": hoja, "puntos": 1, "explicacion": "{a b}"}),
        }
        for esperado, problemas in casos.items():
            self.assertTrue(any(esperado in p for p in problemas), (esperado, problemas))
        self.assertEqual(rg.validar_regla("R01"), ["la regla debe ser un objeto"])
        self.assertTrue(any("`puntos`" in p for p in self._problemas(
            accion={"filtro": hoja, "puntos": True})))


# --- Puntuación -------------------------------------------------------------


class PuntuarTests(SimpleTestCase):
    def _puntuar(self, perfil, filtrar=False, reglas=None):
        cursos = cand.candidatos(perfil, CATALOGO)
        if filtrar:
            cursos = cand.filtrar(perfil, cursos, CATALOGO, REGLAS)
        return _por_curso(rg.puntuar(perfil, cursos, _contexto(reglas)))

    def test_alumno_nuevo_r01_y_r03_para_py101(self):
        p = self._puntuar(_perfil(), filtrar=True)
        self.assertEqual(list(p), [PY101])
        self.assertEqual(p[PY101]["puntuacion"], 5.0)
        self.assertEqual(p[PY101]["razones"], [
            {"origen": "regla:R03a", "texto": "Encaja con tu nivel Principiante.", "aporte": 2.0},
            {"origen": "regla:R01", "texto": "Es un buen punto de partida para empezar con Python.",
             "aporte": 3.0},
        ])

    def test_tras_completar_py401_r02_para_301_501_601(self):
        perfil = _perfil(completados={PY101: 90, PY201: 88, PY401: 92})
        p = self._puntuar(perfil)
        titulo_401 = CATALOGO["cursos"][PY401]["titulo"]
        for curso_id in (PY301, PY501, PY601):
            self.assertEqual(p[curso_id]["razones"], [{
                "origen": "regla:R02",
                "texto": f"Es el siguiente paso después de {titulo_401}.",
                "aporte": 4.0,
            }])
            self.assertEqual(p[curso_id]["puntuacion"], 4.0)
        for curso_id in (PY701, PY801):
            self.assertNotIn("regla:R02", _origenes(p[curso_id]))
            self.assertNotIn("regla:R01", _origenes(p[curso_id]))
        filtrados = self._puntuar(perfil, filtrar=True)
        self.assertEqual(list(filtrados), [PY301, PY501, PY601])

    def test_repaso_pendiente_r05_negativa(self):
        perfil = _perfil(completados={PY101: 90, PY201: 90}, activos=[PY401], refuerzo={PY401: [42]})
        p = self._puntuar(perfil)
        for curso_id in (PY301, PY501, PY601):
            self.assertIn({"origen": "regla:R05",
                           "texto": "Te conviene terminar el repaso de Funciones y Modularidad antes.",
                           "aporte": -3.0}, p[curso_id]["razones"])
            self.assertLess(p[curso_id]["puntuacion"], 0)
        self.assertNotIn("regla:R05", _origenes(p[PY801]))

    def test_avanzado_con_dominio_bajo_r06(self):
        # Practicó herencia y le fue mal (0.1); el resto de conceptos parte de 0.7
        # por ser Avanzado. PY-701 queda por debajo de 0.4 y PY-801 no.
        perfil = _perfil(nivel="Avanzado", dominio={"herencia_polimorfismo": 0.1})
        p = self._puntuar(perfil)
        self.assertEqual(_origenes(p[PY701]), ["regla:R03c", "regla:R06"])
        self.assertEqual(p[PY701]["puntuacion"], 0.0)
        self.assertIsNone(p[PY701]["razones"][1]["texto"])
        self.assertEqual(p[PY701]["razones"][1]["aporte"], -2.0)
        self.assertEqual(_origenes(p[PY801]), ["regla:R03c"])
        dominio_alto = _perfil(nivel="Avanzado",
                               dominio={"herencia_polimorfismo": 0.9, "poo_clases": 0.9})
        self.assertNotIn("regla:R06", _origenes(self._puntuar(dominio_alto)[PY701]))

    def test_intereses_r04(self):
        perfil = _perfil(intereses={"json_apis": 1.0, "diccionarios_conjuntos": 1.0})
        p = self._puntuar(perfil)
        self.assertIn({"origen": "regla:R04", "texto": "Coincide con tu interés en Datos.",
                       "aporte": 2.0}, p[PY801]["razones"])
        self.assertNotIn(PY301, p)  # Intermedio, sin interés ni otras reglas

    def test_omite_candidatos_sin_reglas_y_respeta_el_orden(self):
        perfil = _perfil()
        cursos = list(reversed(cand.candidatos(perfil, CATALOGO)))
        ids = [x["curso_id"] for x in rg.puntuar(perfil, cursos, _contexto())]
        self.assertEqual(ids, [PY801, PY701, PY401, PY201, PY101])

    def test_ignora_otros_ambitos_inactivas_e_invalidas(self):
        r01 = next(r for r in REGLAS if r["codigo"] == "R01")
        reglas = [
            {**r01, "codigo": "A01", "ambito": "adaptacion"},
            {**r01, "codigo": "R99", "activa": False},
            {**r01, "codigo": "R98", "accion": {**r01["accion"], "puntos": "mucho"}},
        ]
        self.assertEqual(rg.puntuar(_perfil(), cand.candidatos(_perfil(), CATALOGO), _contexto(reglas)), [])
        self.assertEqual(rg.puntuar(_perfil(), [], _contexto()), [])

    def test_no_modifica_la_entrada(self):
        perfil = _perfil(nivel="Intermedio", completados={PY101: 90, PY201: 90},
                         intereses={"bucles": 1.0}, refuerzo={PY201: [21]})
        cursos = cand.candidatos(perfil, CATALOGO)
        contexto = _contexto()
        antes = copy.deepcopy((perfil, cursos, contexto))
        rg.puntuar(perfil, cursos, contexto)
        self.assertEqual((perfil, cursos, contexto), antes)


# --- Migración 0008 y carga -------------------------------------------------

_MIGRACION = Path(__file__).resolve().parents[3] / "migrations" / "0008_motor_reglas.sql"
_FILA = re.compile(
    r"\('(?P<codigo>\w+)',\s*'(?P<ambito>\w+)',\s*(?P<prioridad>-?\d+),\s*"
    r"'(?P<condicion>\{.*?\})'::jsonb,\s*'(?P<accion>\{.*?\})'::jsonb,",
    re.S,
)


class MigracionTests(SimpleTestCase):
    def test_la_migracion_coincide_con_las_reglas_de_los_tests(self):
        sql = _MIGRACION.read_text(encoding="utf-8")
        filas = {
            m["codigo"]: (m["ambito"], int(m["prioridad"]), json.loads(m["condicion"]), json.loads(m["accion"]))
            for m in _FILA.finditer(sql)
        }
        esperado = {r["codigo"]: (r["ambito"], r["prioridad"], r["condicion"], r["accion"]) for r in _SEMILLA}
        self.assertEqual(filas, esperado)
        self.assertIn("ON CONFLICT (codigo) DO UPDATE", sql)
        self.assertNotIn("activa      = EXCLUDED", sql)


class CargarReglasTests(SimpleTestCase):
    def setUp(self):
        rg.invalidar_reglas()
        self.addCleanup(rg.invalidar_reglas)

    def _filas(self):
        filas = [{**r, "prioridad": r["prioridad"]} for r in _SEMILLA]
        rota = {**_SEMILLA[4], "id": 50, "codigo": "R77", "condicion": {"campo": "n", "op": "~"}}
        return list(reversed(filas)) + [rota]

    def test_ordena_descarta_invalidas_y_memoiza(self):
        with mock.patch.object(rg, "_leer_reglas", return_value=self._filas()) as leer, \
                mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 300), \
                self.assertLogs("features.motor.estrategias.reglas", level="ERROR") as logs:
            primera = rg.cargar_reglas()
            segunda = rg.cargar_reglas()
        self.assertEqual(leer.call_count, 1)
        self.assertEqual([r["codigo"] for r in primera], [r["codigo"] for r in REGLAS])
        self.assertEqual(primera, segunda)
        self.assertTrue(any("R77" in linea and "operador desconocido" in linea for linea in logs.output))

    def test_sin_cache_lee_siempre(self):
        with mock.patch.object(rg, "_leer_reglas", return_value=[]) as leer, \
                mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 0):
            rg.cargar_reglas()
            rg.cargar_reglas()
        self.assertEqual(leer.call_count, 2)

    def test_lee_solo_activas_ordenadas(self):
        with mock.patch.object(rg.supabase, "select", return_value=[]) as select, \
                mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 0):
            rg.cargar_reglas()
        _, kwargs = select.call_args
        self.assertEqual(select.call_args.args[0], "reglas")
        self.assertEqual(kwargs["order"], "prioridad.desc,id.asc")
        self.assertEqual(list(kwargs["filters"]), [("activa", "eq.true")])

    def test_descarta_inactivas_aunque_lleguen(self):
        filas = [{**_SEMILLA[4], "activa": False}]
        with mock.patch.object(rg, "_leer_reglas", return_value=filas), \
                mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 0):
            self.assertEqual(rg.cargar_reglas(), [])
