"""Tests del paquete 07: características, árbol, datos sintéticos, dataset y activación. Sin red.

Las pruebas de `entrenar.py` y `exportar_arbol.py` se saltan sin scikit-learn.

Mientras `perfil.dominio.reproducir_dominio` y `perfil.construir.construir_perfil`
(paquete 04) sean stubs, las pruebas del dataset usan `_Falso04`, una versión
mínima que sigue 04-perfil.md §1–2. En cuanto 04 esté implementado, se usa el
real automáticamente (ver `_con_04`).
"""

import ast
import csv
import io
import importlib.util
import json
import random
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock, skipUnless

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from core.errors import DataAccessError
from entrenamiento import dataset, sinteticos
from features.motor import config
from features.motor.estrategias import modelo
from features.motor.management.commands import activar_modelo
from features.motor.perfil import construir as perfil_construir
from features.motor.perfil import dominio as perfil_dominio

HAY_SKLEARN = importlib.util.find_spec("sklearn") is not None
BASE = Path(settings.BASE_DIR)
INICIO = datetime(2026, 1, 12, tzinfo=timezone.utc)


def _catalogo():
    return sinteticos.cargar_catalogo_json(BASE / "entrenamiento" / "catalogo_ejemplo.json")


# --- Falso 04 (solo mientras 04 sea un stub) ---------------------------------

_RANGO_NIVEL = {"Principiante": 0, "Intermedio": 1, "Avanzado": 2}
_RANGO_ESTADO = {"completado": 3, "actividades_de_refuerzo": 2, "desbloqueado": 1}


class _Falso04:
    """Implementación mínima de 04-perfil.md §1–2, solo para estas pruebas."""

    @staticmethod
    def nuevo_dominio(anterior, puntaje, inicial, peso=1.0):
        base = inicial if anterior is None else anterior
        return round(min(1.0, max(0.0, base + config.ALFA_DOMINIO * peso * (puntaje - base))), 3)

    @staticmethod
    def dominio_inicial(concepto, nivel, catalogo):
        for curso in catalogo["cursos"].values():
            if concepto in curso["conceptos"] and _RANGO_NIVEL[curso["nivel"]] <= _RANGO_NIVEL[nivel]:
                return config.DOMINIO_INICIAL_POR_NIVEL[nivel]
        return config.DOMINIO_SIN_EVIDENCIA

    @classmethod
    def _tema(cls, catalogo, tema_id):
        for curso in catalogo["cursos"].values():
            for tema in curso["temas"]:
                if tema["id"] == tema_id:
                    return tema
        return None

    @classmethod
    def reproducir_dominio(cls, eventos, catalogo, nivel_asignado, hasta=None):
        dominio, evidencias = {}, {}
        for e in sorted(eventos, key=lambda e: e["fecha"]):
            if hasta is not None and e["fecha"] >= hasta:
                continue
            if e["tipo"] == "quiz_intento":
                tema = cls._tema(catalogo, e["objeto_id"])
                for c, peso in (tema or {}).get("conceptos", {}).items():
                    inicial = cls.dominio_inicial(c, nivel_asignado, catalogo)
                    dominio[c] = cls.nuevo_dominio(dominio.get(c), float(e["valor"]), inicial, peso)
                    evidencias[c] = evidencias.get(c, 0) + 1
            elif e["tipo"] == "diagnostico":
                por_concepto = {}
                for ej, ok in (e.get("datos") or {}).get("resultados", {}).items():
                    tema = cls._tema(catalogo, catalogo["ejercicios_diagnostico"].get(int(ej)))
                    for c in (tema or {}).get("conceptos", {}):
                        por_concepto.setdefault(c, []).append(1.0 if ok else 0.0)
                for c, valores in por_concepto.items():
                    p = sum(valores) / len(valores)
                    if c in dominio:
                        inicial = cls.dominio_inicial(c, nivel_asignado, catalogo)
                        dominio[c] = cls.nuevo_dominio(dominio[c], p, inicial)
                    else:
                        dominio[c] = round(config.DOMINIO_DIAGNOSTICO_FALLO + p * (
                            config.DOMINIO_DIAGNOSTICO_ACIERTO - config.DOMINIO_DIAGNOSTICO_FALLO), 3)
                    evidencias[c] = evidencias.get(c, 0) + 1
        return dominio, evidencias

    @classmethod
    def construir_perfil(cls, entrada, catalogo, ahora):
        intereses = {}

        def sumar(clave, peso):
            for c in catalogo["areas"].get(clave, [clave]):
                intereses[c] = min(1.0, max(intereses.get(c, 0.0), float(peso)))

        for i in entrada["intereses"]:
            sumar(i["concepto_clave"], i["peso"])
        for area, peso in catalogo["carrera_areas"].get(entrada["usuario"]["carrera_clave"], {}).items():
            sumar(area, peso)

        evid = entrada["evidencias"]
        con = [entrada["dominio"][c] for c, n in evid.items() if n >= 1]
        inferido = None
        if con:
            media = sum(con) / len(con)
            inferido = ("Avanzado" if media >= 0.75 else "Intermedio" if media >= 0.45 else "Principiante")
        asignado = entrada["usuario"]["nivel_asignado"]
        nivel = inferido if sum(evid.values()) >= config.EVIDENCIAS_MIN_NIVEL_INFERIDO else asignado

        inscripciones = {}
        for i in entrada["inscripciones"]:
            previa = inscripciones.get(i["curso_id"])
            if previa is None or i["porcentaje_avance_global"] > previa["porcentaje_avance_global"]:
                inscripciones[i["curso_id"]] = dict(i)
        completadas = sorted((i for i in inscripciones.values() if i["estado"] == "completado"),
                             key=lambda i: i["completado_en"])

        mejor = {}
        for t in entrada["estados_temas"]:
            if _RANGO_ESTADO.get(t["estado"], 0) >= _RANGO_ESTADO.get(mejor.get(t["tema_id"]), 0):
                mejor[t["tema_id"]] = t["estado"]
        refuerzo = {}
        for tema_id, estado in mejor.items():
            tema = cls._tema(catalogo, tema_id)
            if estado == "actividades_de_refuerzo" and tema:
                refuerzo.setdefault(tema["curso_id"], []).append(tema_id)

        envios = dataset._envios(entrada["intentos"])
        tasa = intentos_prom = None
        if envios:
            aprobados = {t for t, _, m in envios if m >= config.UMBRAL_APROBADO}
            tasa = len(aprobados) / len(envios)
            hasta_aprobar = {}
            for t, _, m in envios:
                if t in hasta_aprobar and hasta_aprobar[t][1]:
                    continue
                n, _ = hasta_aprobar.get(t, (0, False))
                hasta_aprobar[t] = (n + 1, m >= config.UMBRAL_APROBADO)
            intentos_prom = sum(n for n, _ in hasta_aprobar.values()) / len(hasta_aprobar)

        fechas = [f for f in [entrada["ultimo_evento"], *(i["fecha_intento"] for i in entrada["intentos"])] if f]
        return {
            "usuario_id": entrada["usuario"]["id"],
            "nivel": nivel,
            "nivel_asignado": asignado,
            "nivel_inferido": inferido,
            "carrera_clave": entrada["usuario"]["carrera_clave"],
            "intereses": intereses,
            "dominio": dict(entrada["dominio"]),
            "evidencias": dict(evid),
            "inscripciones": inscripciones,
            "cursos_completados": [i["curso_id"] for i in completadas],
            "calificacion_por_curso": {i["curso_id"]: i["calificacion_final"] for i in completadas},
            "modulos_en_refuerzo": refuerzo,
            "tasa_aprobacion_modulos": tasa,
            "intentos_promedio": intentos_prom,
            "dias_inactivo": (ahora - max(fechas)).days if fechas else None,
            "calculado_en": ahora,
        }


def _es_stub(funcion, *args):
    try:
        funcion(*args)
    except NotImplementedError:
        return True
    except Exception:
        return False
    return False


@contextmanager
def _con_04():
    """Usa el 04 real si ya está implementado; si sigue siendo stub, `_Falso04`."""
    vacio = {"cursos": {}, "conceptos": {}, "areas": {}, "carrera_areas": {}, "ejercicios_diagnostico": {}}
    entrada = {"usuario": {"id": "x", "nivel_asignado": "Principiante", "carrera_clave": None},
               "inscripciones": [], "estados_temas": [], "intentos": [], "dominio": {},
               "evidencias": {}, "intereses": [], "ultimo_evento": None}
    with ExitStack() as pila:
        if _es_stub(perfil_dominio.reproducir_dominio, [], vacio, "Principiante", None):
            pila.enter_context(mock.patch.object(
                perfil_dominio, "reproducir_dominio", _Falso04.reproducir_dominio))
        if _es_stub(perfil_construir.construir_perfil, entrada, vacio, INICIO):
            pila.enter_context(mock.patch.object(
                perfil_construir, "construir_perfil", _Falso04.construir_perfil))
        yield


# --- Ayudas -----------------------------------------------------------------


def _perfil(**cambios):
    base = {
        "usuario_id": "u1", "nivel": "Intermedio", "nivel_asignado": "Principiante",
        "nivel_inferido": "Intermedio", "carrera_clave": None, "intereses": {}, "dominio": {},
        "evidencias": {}, "inscripciones": {}, "cursos_completados": [], "calificacion_por_curso": {},
        "modulos_en_refuerzo": {}, "tasa_aprobacion_modulos": None, "intentos_promedio": None,
        "dias_inactivo": None, "calculado_en": INICIO,
    }
    return {**base, **cambios}


def _hoja(prob, n=30):
    return {"hoja": True, "prob": prob, "n": n}


ARBOL = {
    "hoja": False, "campo": "dominio_conceptos_curso", "umbral": 0.5,
    "izq": _hoja(0.2),
    "der": {"hoja": False, "campo": "coincide_interes", "umbral": 0.5,
            "izq": _hoja(0.6), "der": _hoja(0.9)},
}


def _contexto(modelo_activo):
    return {"catalogo": _catalogo(), "reglas": [], "similitudes": {}, "modelo": modelo_activo, "ahora": INICIO}


# --- Características ----------------------------------------------------------


class CaracteristicasTests(SimpleTestCase):
    def setUp(self):
        self.catalogo = _catalogo()
        self.py501 = self.catalogo["cursos"][5]  # requiere PY-401 (id 4)

    def test_todas_las_caracteristicas(self):
        perfil = _perfil(
            dominio={"diccionarios_conjuntos": 0.8, "comprensiones": 0.6, "colecciones": 0.9, "bucles": 0.1},
            evidencias={"diccionarios_conjuntos": 2, "comprensiones": 1, "colecciones": 0, "bucles": 3},
            cursos_completados=[1, 2, 4], calificacion_por_curso={1: 90.0, 2: 70.0, 4: 85.0},
            tasa_aprobacion_modulos=0.75, intentos_promedio=1.5, intereses={"comprensiones": 0.5},
            nivel="Avanzado",
        )
        x = modelo.caracteristicas_para(perfil, self.py501, self.catalogo)
        self.assertEqual(list(x), modelo.CARACTERISTICAS)
        self.assertAlmostEqual(x["dominio_medio"], round((0.8 + 0.6 + 0.1) / 3, 6))
        self.assertAlmostEqual(x["dominio_conceptos_curso"], round((0.8 + 0.6 + 0.5 * 0.9) / 2.5, 6))
        self.assertEqual(x["cursos_previos"], 3.0)
        self.assertEqual(x["calificacion_prerrequisitos"], 85.0)
        self.assertEqual(x["tasa_aprobacion_modulos"], 0.75)
        self.assertEqual(x["intentos_promedio"], 1.5)
        self.assertEqual(x["dificultad_curso"], 3.0)
        self.assertEqual(x["nivel_ordinal"], 2.0)
        self.assertEqual(x["coincide_interes"], 1.0)

    def test_valores_por_defecto_sin_datos(self):
        x = modelo.caracteristicas_para(_perfil(nivel="Principiante"), self.py501, self.catalogo)
        sin = config.DOMINIO_SIN_EVIDENCIA_MODELO
        self.assertEqual(x, {
            "dominio_medio": sin, "dominio_conceptos_curso": sin, "cursos_previos": 0.0,
            "calificacion_prerrequisitos": 0.0, "tasa_aprobacion_modulos": 0.0, "intentos_promedio": 0.0,
            "dificultad_curso": 3.0, "nivel_ordinal": 0.0, "coincide_interes": 0.0,
        })

    def test_concepto_sin_dominio_usa_el_valor_por_defecto(self):
        perfil = _perfil(dominio={"diccionarios_conjuntos": 1.0}, evidencias={"diccionarios_conjuntos": 1},
                         intereses={"comprensiones": 0.49})
        x = modelo.caracteristicas_para(perfil, self.py501, self.catalogo)
        sin = config.DOMINIO_SIN_EVIDENCIA_MODELO
        self.assertAlmostEqual(x["dominio_conceptos_curso"], round((1.0 + sin + 0.5 * sin) / 2.5, 6))
        self.assertEqual(x["coincide_interes"], 0.0)

    def test_prerrequisito_no_completado_no_cuenta(self):
        perfil = _perfil(cursos_completados=[1], calificacion_por_curso={1: 90.0})
        x = modelo.caracteristicas_para(perfil, self.py501, self.catalogo)
        self.assertEqual(x["calificacion_prerrequisitos"], 0.0)

    def test_no_muta_el_perfil(self):
        perfil = _perfil(dominio={"bucles": 0.5}, evidencias={"bucles": 1})
        copia = json.loads(json.dumps(perfil, default=str))
        modelo.caracteristicas_para(perfil, self.py501, self.catalogo)
        self.assertEqual(json.loads(json.dumps(perfil, default=str)), copia)


# --- Árbol --------------------------------------------------------------------


class PredecirTests(SimpleTestCase):
    def test_rama_izquierda(self):
        prob, camino = modelo.predecir(ARBOL, {"dominio_conceptos_curso": 0.5})
        self.assertEqual(prob, 0.2)
        self.assertEqual(camino, [{"campo": "dominio_conceptos_curso", "umbral": 0.5, "izq": True}])

    def test_rama_derecha_y_camino(self):
        prob, camino = modelo.predecir(ARBOL, {"dominio_conceptos_curso": 0.7, "coincide_interes": 1.0})
        self.assertEqual(prob, 0.9)
        self.assertEqual(camino, [
            {"campo": "dominio_conceptos_curso", "umbral": 0.5, "izq": False},
            {"campo": "coincide_interes", "umbral": 0.5, "izq": False},
        ])

    def test_caracteristica_ausente_vale_cero(self):
        prob, camino = modelo.predecir(ARBOL, {"dominio_conceptos_curso": 0.9})
        self.assertEqual(prob, 0.6)
        self.assertTrue(camino[1]["izq"])

    def test_hoja_raiz(self):
        self.assertEqual(modelo.predecir(_hoja(0.4), {}), (0.4, []))


class ValidarArbolTests(SimpleTestCase):
    def test_arbol_valido(self):
        self.assertTrue(modelo.validar_arbol(ARBOL, modelo.CARACTERISTICAS))

    def test_falta_una_clave(self):
        roto = {**ARBOL, "der": {k: v for k, v in ARBOL["der"].items() if k != "umbral"}}
        self.assertFalse(modelo.validar_arbol(roto, modelo.CARACTERISTICAS))
        self.assertFalse(modelo.validar_arbol({"hoja": True, "n": 3}, modelo.CARACTERISTICAS))
        self.assertFalse(modelo.validar_arbol({**ARBOL, "hoja": None}, modelo.CARACTERISTICAS))

    def test_demasiado_profundo(self):
        arbol = _hoja(0.5)
        for _ in range(3):
            arbol = {"hoja": False, "campo": "cursos_previos", "umbral": 1.0, "izq": arbol, "der": _hoja(0.1)}
        self.assertTrue(modelo.validar_arbol(arbol, modelo.CARACTERISTICAS, profundidad_max=3))
        self.assertFalse(modelo.validar_arbol(arbol, modelo.CARACTERISTICAS, profundidad_max=2))

    def test_caracteristica_desconocida(self):
        arbol = {**ARBOL, "campo": "habilidad"}
        self.assertFalse(modelo.validar_arbol(arbol, modelo.CARACTERISTICAS))
        self.assertFalse(modelo.validar_arbol(ARBOL, ["dominio_conceptos_curso"]))

    def test_prob_fuera_de_rango(self):
        self.assertFalse(modelo.validar_arbol({**ARBOL, "izq": _hoja(1.2)}, modelo.CARACTERISTICAS))


class ExplicarTests(SimpleTestCase):
    def test_por_debajo_de_medio(self):
        camino = [{"campo": "dominio_conceptos_curso", "umbral": 0.5, "izq": False}]
        self.assertIsNone(modelo.explicar(camino, 0.49))

    def test_cada_plantilla(self):
        esperados = {
            "dominio_conceptos_curso": "Ya tienes buena base en los temas de este curso.",
            "calificacion_prerrequisitos": "Te fue bien en los cursos previos.",
            "tasa_aprobacion_modulos": "Sueles aprobar los módulos a la primera.",
            "coincide_interes": "Coincide con lo que te interesa.",
        }
        for campo, texto in esperados.items():
            with self.subTest(campo=campo):
                camino = [
                    {"campo": "dificultad_curso", "umbral": 2.5, "izq": False},
                    {"campo": "coincide_interes" if campo != "coincide_interes" else "cursos_previos",
                     "umbral": 0.5, "izq": True},
                    {"campo": campo, "umbral": 0.5, "izq": False},
                ]
                self.assertEqual(modelo.explicar(camino, 0.5), texto)

    def test_primer_paso_que_coincide(self):
        camino = [
            {"campo": "tasa_aprobacion_modulos", "umbral": 0.5, "izq": False},
            {"campo": "dominio_conceptos_curso", "umbral": 0.5, "izq": False},
        ]
        self.assertEqual(modelo.explicar(camino, 0.8), "Sueles aprobar los módulos a la primera.")

    def test_sin_coincidencia(self):
        camino = [
            {"campo": "dominio_conceptos_curso", "umbral": 0.5, "izq": True},
            {"campo": "cursos_previos", "umbral": 1.5, "izq": False},
        ]
        self.assertIsNone(modelo.explicar(camino, 0.9))


class PuntuarTests(SimpleTestCase):
    def test_sin_modelo_devuelve_lista_vacia(self):
        cursos = list(_catalogo()["cursos"].values())
        self.assertEqual(modelo.puntuar(_perfil(), cursos, _contexto(None)), [])

    def test_una_puntuacion_por_candidato(self):
        activo = {"nombre": "aprobacion", "version": "20261120-0300",
                  "caracteristicas": modelo.CARACTERISTICAS, "arbol": ARBOL}
        catalogo = _catalogo()
        perfil = _perfil(dominio={"variables_tipos": 0.9, "colecciones": 0.9},
                         evidencias={"variables_tipos": 1, "colecciones": 1})
        resultado = modelo.puntuar(perfil, [catalogo["cursos"][1], catalogo["cursos"][7]], _contexto(activo))
        self.assertEqual([p["curso_id"] for p in resultado], [1, 7])
        self.assertEqual(resultado[0]["puntuacion"], 0.6)
        self.assertEqual(resultado[0]["razones"], [{
            "origen": "modelo:aprobacion@20261120-0300", "aporte": 0.6,
            "texto": "Ya tienes buena base en los temas de este curso.",
        }])
        self.assertEqual(resultado[1]["puntuacion"], 0.2)
        self.assertIsNone(resultado[1]["razones"][0]["texto"])


class CargarActivoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def _fila(self, arbol=ARBOL):
        return {"nombre": "aprobacion", "version": "v1", "caracteristicas": modelo.CARACTERISTICAS,
                "parametros": arbol}

    def test_modelo_valido_y_memoizado(self):
        with mock.patch.object(modelo, "_leer_activo", return_value=self._fila()) as leer:
            primero = modelo.cargar_activo()
            segundo = modelo.cargar_activo()
        self.assertEqual(primero["arbol"], ARBOL)
        self.assertEqual(primero, segundo)
        leer.assert_called_once_with("aprobacion")

    def test_arbol_invalido_da_none_y_error(self):
        with mock.patch.object(modelo, "_leer_activo", return_value=self._fila({"hoja": "x"})):
            with self.assertLogs(modelo.logger, level="ERROR"):
                self.assertIsNone(modelo.cargar_activo())

    def test_sin_modelo_activo(self):
        with mock.patch.object(modelo, "_leer_activo", return_value=None):
            self.assertIsNone(modelo.cargar_activo())

    def test_error_de_lectura_da_none(self):
        with mock.patch.object(modelo, "_leer_activo", side_effect=DataAccessError("x")):
            with self.assertLogs(modelo.logger, level="ERROR"):
                self.assertIsNone(modelo.cargar_activo())


class SinLibreriasDeMLTests(SimpleTestCase):
    def test_estrategias_no_importan_librerias_de_ml(self):
        prohibidas = {"pandas", "numpy", "sklearn", "joblib", "pickle"}
        carpeta = BASE / "features" / "motor" / "estrategias"
        for ruta in carpeta.glob("*.py"):
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                nombres = []
                if isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                    nombres = [nodo.module]
                for nombre in nombres:
                    with self.subTest(fichero=ruta.name, modulo=nombre):
                        self.assertNotIn(nombre.split(".")[0], prohibidas)


# --- Catálogo de ejemplo y datos sintéticos -----------------------------------


class CatalogoEjemploTests(SimpleTestCase):
    def test_coincide_con_01_cimientos(self):
        catalogo = _catalogo()
        self.assertEqual(len(catalogo["cursos"]), 8)
        self.assertEqual(sorted(catalogo["areas"]), ["automatizacion", "datos", "fundamentos", "poo"])
        self.assertEqual(sum(len(v) for v in catalogo["areas"].values()), 14)
        self.assertEqual(sum(len(c["prerrequisitos"]) for c in catalogo["cursos"].values()), 8)
        self.assertEqual(len(catalogo["carrera_areas"]), 21)
        self.assertEqual(catalogo["ejercicios_diagnostico"], {9001: 1, 9002: 6, 9003: 2, 9004: 4, 9005: 2})
        por_codigo = {c["codigo_curso"]: c for c in catalogo["cursos"].values()}
        self.assertEqual([p["curso_id"] for p in por_codigo["PY-801"]["prerrequisitos"]],
                         [por_codigo["PY-501"]["id"], por_codigo["PY-601"]["id"]])
        self.assertEqual(por_codigo["PY-401"]["temas"][1]["conceptos"], {"modulos": 0.7, "funciones": 0.3})
        for curso in catalogo["cursos"].values():
            self.assertTrue(all(t["conceptos"] for t in curso["temas"]), curso["codigo_curso"])


class GenerarTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalogo = _catalogo()
        cls.datos = sinteticos.generar(cls.catalogo, 2000, 42, INICIO)

    def test_misma_semilla_misma_salida(self):
        self.assertEqual(sinteticos.generar(self.catalogo, 50, 7, INICIO),
                         sinteticos.generar(self.catalogo, 50, 7, INICIO))
        self.assertNotEqual(sinteticos.generar(self.catalogo, 50, 7, INICIO),
                            sinteticos.generar(self.catalogo, 50, 8, INICIO))

    def test_no_usa_el_random_global(self):
        random.seed(1)
        a = sinteticos.generar(self.catalogo, 5, 3, INICIO)
        random.seed(2)
        self.assertEqual(a, sinteticos.generar(self.catalogo, 5, 3, INICIO))

    def test_alumnos(self):
        alumnos = self.datos["alumnos"]
        self.assertEqual(len(alumnos), 2000)
        self.assertEqual(alumnos[0]["usuario_id"], "sint-000001")
        for a in alumnos:
            self.assertIn(a["nivel_asignado"], ("Principiante", "Intermedio", "Avanzado"))
            self.assertTrue(1 <= len(a["intereses"]) <= 2)
            self.assertTrue(0.3 <= a["habilidad"] <= 1.0)
        self.assertTrue(any(a["carrera_clave"] in sinteticos.CARRERAS_SIN_AREAS for a in alumnos))

    def test_estados_validos(self):
        for i in self.datos["inscripciones"]:
            self.assertIn(i["estado"], ("activo", "completado", "abandonado"))
            self.assertEqual(i["origen"], "catalogo")

    def test_completados_tienen_calificacion(self):
        completados = [i for i in self.datos["inscripciones"] if i["estado"] == "completado"]
        self.assertTrue(completados)
        for i in completados:
            self.assertIsNotNone(i["calificacion_final"])
            self.assertGreaterEqual(i["completado_en"], i["fecha_inscripcion"])
            self.assertEqual(i["porcentaje_avance_global"], 100.0)
        for i in self.datos["inscripciones"]:
            if i["estado"] != "completado":
                self.assertIsNone(i["calificacion_final"])

    def test_eventos_ordenados_por_alumno(self):
        por_alumno = {}
        for e in self.datos["eventos"]:
            por_alumno.setdefault(e["usuario_id"], []).append(e["fecha"])
        for fechas in por_alumno.values():
            self.assertEqual(fechas, sorted(fechas))
        tipos = {e["tipo"] for e in self.datos["eventos"]}
        self.assertTrue({"diagnostico", "curso_vista", "quiz_intento", "curso_completado"} <= tipos)

    def test_saltar_prerrequisitos_suspende_mas(self):
        completados = {}
        con, sin = [], []
        por_alumno = {}
        for i in self.datos["inscripciones"]:
            por_alumno.setdefault(i["usuario_id"], []).append(i)
        for inscripciones in por_alumno.values():
            completados = set()
            for i in sorted(inscripciones, key=lambda i: i["fecha_inscripcion"]):
                requeridos = [p["curso_id"] for p in self.catalogo["cursos"][i["curso_id"]]["prerrequisitos"]]
                aprobo = i["estado"] == "completado"
                (sin if any(r not in completados for r in requeridos) else con).append(aprobo)
                if aprobo:
                    completados.add(i["curso_id"])
        self.assertGreater(len(sin), 50)
        tasa_con, tasa_sin = sum(con) / len(con), sum(sin) / len(sin)
        self.assertGreater(tasa_con - tasa_sin, 0.1, (tasa_con, tasa_sin))

    def test_csv_ida_y_vuelta(self):
        datos = sinteticos.generar(self.catalogo, 20, 1, INICIO)
        with tempfile.TemporaryDirectory() as tmp:
            sinteticos.escribir(datos, self.catalogo, Path(tmp))
            leidos, catalogo = sinteticos.leer(Path(tmp))
            with open(Path(tmp) / "eventos.csv", encoding="utf-8") as f:
                cabecera = next(csv.reader(f))
        self.assertEqual(catalogo, self.catalogo)
        self.assertEqual(cabecera, sinteticos.COLUMNAS["eventos"])
        self.assertEqual(len(leidos["intentos"]), len(datos["intentos"]))
        evento = leidos["eventos"][0]
        self.assertEqual(json.loads(evento["datos"]), datos["eventos"][0]["datos"])
        self.assertEqual(sinteticos.fecha(evento["fecha"]), datos["eventos"][0]["fecha"])

    def test_fecha_admite_z_y_decimales_raros(self):
        self.assertEqual(sinteticos.fecha("2026-01-12T00:00:00.12345Z"),
                         datetime(2026, 1, 12, 0, 0, 0, 123450, tzinfo=timezone.utc))
        self.assertIsNone(sinteticos.fecha(""))


class GenerarSinteticosOrdenTests(SimpleTestCase):
    def test_rechaza_salida_fuera_de_entrenamiento_datos(self):
        for salida in ("/tmp/fuera", "entrenamiento/modelos/x", "entrenamiento/datos/../../fuera"):
            with self.subTest(salida=salida):
                with self.assertRaisesMessage(CommandError, "Solo se puede escribir dentro de"):
                    call_command("generar_sinteticos", "--alumnos", "1", "--salida", salida)


# --- Dataset (depende de 04: real o `_Falso04`) --------------------------------


class ConstruirDatasetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalogo = _catalogo()
        cls.datos = sinteticos.generar(cls.catalogo, 60, 5, INICIO)

    def _construir(self, datos):
        with _con_04():
            return dataset.construir(datos["alumnos"], datos["inscripciones"], datos["intentos"],
                                     datos["eventos"], self.catalogo)

    def test_una_fila_por_inscripcion_con_desenlace_y_etiqueta(self):
        filas = self._construir(self.datos)
        con_desenlace = [i for i in self.datos["inscripciones"] if i["estado"] in ("completado", "abandonado")]
        self.assertEqual(len(filas), len(con_desenlace))
        self.assertEqual(list(filas[0]), dataset.COLUMNAS_DATASET)
        esperado = {
            (i["usuario_id"], i["curso_id"]): int(
                i["estado"] == "completado" and i["calificacion_final"] >= config.UMBRAL_ETIQUETA_APROBO)
            for i in con_desenlace
        }
        self.assertEqual({(f["usuario_id"], f["curso_id"]): f["aprobo"] for f in filas}, esperado)
        self.assertEqual(filas, sorted(filas, key=lambda f: f["fecha_inscripcion"]))

    def test_etiqueta_por_debajo_del_umbral_es_cero(self):
        self.assertEqual(dataset._etiqueta({"estado": "completado", "calificacion_final": 79.9}), 0)
        self.assertEqual(dataset._etiqueta({"estado": "completado", "calificacion_final": 80.0}), 1)
        self.assertEqual(dataset._etiqueta({"estado": "abandonado", "calificacion_final": 95.0}), 0)

    def test_acepta_filas_de_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            sinteticos.escribir(self.datos, self.catalogo, Path(tmp))
            leidos, catalogo = sinteticos.leer(Path(tmp))
        with _con_04():
            desde_csv = dataset.construir(leidos["alumnos"], leidos["inscripciones"], leidos["intentos"],
                                          leidos["eventos"], catalogo)
        self.assertEqual(desde_csv, self._construir(self.datos))

    def test_sin_fuga_anadir_datos_posteriores_no_cambia_la_fila(self):
        filas = self._construir(self.datos)
        objetivo = next(f for f in filas if f["cursos_previos"] >= 1)
        uid, t = objetivo["usuario_id"], sinteticos.fecha(objetivo["fecha_inscripcion"])
        despues = t  # lo que ocurre justo en t ya es futuro
        extra = {
            "eventos": [
                {"usuario_id": uid, "tipo": "quiz_intento", "objeto_tipo": "tema", "objeto_id": tema["id"],
                 "curso_id": curso["id"], "valor": 1.0, "datos": {}, "fecha": despues + timedelta(hours=k)}
                for k, curso in enumerate(self.catalogo["cursos"].values()) for tema in curso["temas"]
            ] + [{"usuario_id": uid, "tipo": "diagnostico", "objeto_tipo": None, "objeto_id": None,
                  "curso_id": None, "valor": 1.0, "fecha": despues,
                  "datos": {"resultados": {"9001": True, "9002": True}, "nivel": "Avanzado"}}],
            "intentos": [
                {"usuario_id": uid, "ejercicio_id": 1, "tema_id": tema_id, "tipo": "ejercicio_practico",
                 "calificacion_obtenida": 100.0, "fecha_intento": despues}
                for tema_id in range(1, 16)
            ],
            "inscripciones": [
                {"usuario_id": uid, "curso_id": c, "estado": "completado", "porcentaje_avance_global": 100.0,
                 "calificacion_final": 100.0, "fecha_inscripcion": despues + timedelta(seconds=1),
                 "completado_en": despues + timedelta(seconds=2),
                 "origen": "catalogo"}
                for c in self.catalogo["cursos"]
            ],
        }
        aumentados = {**self.datos, **{k: self.datos[k] + v for k, v in extra.items()}}
        nuevas = self._construir(aumentados)
        misma = next(f for f in nuevas if f["usuario_id"] == uid and f["curso_id"] == objetivo["curso_id"]
                     and f["fecha_inscripcion"] == objetivo["fecha_inscripcion"])
        self.assertEqual(misma, objetivo)

    def test_04_solo_recibe_datos_anteriores_a_t(self):
        vistos = []
        with _con_04():
            real_dominio = perfil_dominio.reproducir_dominio
            real_perfil = perfil_construir.construir_perfil

            def espia_dominio(eventos, catalogo, nivel, hasta=None):
                vistos.append(("eventos", hasta, [e["fecha"] for e in eventos]))
                return real_dominio(eventos, catalogo, nivel, hasta=hasta)

            def espia_perfil(entrada, catalogo, ahora):
                fechas = [i["fecha_intento"] for i in entrada["intentos"]]
                fechas += [i["fecha_inscripcion"] for i in entrada["inscripciones"]]
                fechas += [i["completado_en"] for i in entrada["inscripciones"] if i["completado_en"]]
                fechas += [entrada["ultimo_evento"]] if entrada["ultimo_evento"] else []
                vistos.append(("perfil", ahora, fechas))
                return real_perfil(entrada, catalogo, ahora)

            with mock.patch.object(perfil_dominio, "reproducir_dominio", espia_dominio), \
                    mock.patch.object(perfil_construir, "construir_perfil", espia_perfil):
                dataset.construir(self.datos["alumnos"], self.datos["inscripciones"],
                                  self.datos["intentos"], self.datos["eventos"], self.catalogo)
        self.assertTrue(vistos)
        for _, t, fechas in vistos:
            self.assertIsNotNone(t)
            self.assertTrue(all(f < t for f in fechas))

    def test_completado_despues_de_t_cuenta_como_activo(self):
        t = INICIO + timedelta(days=10)
        inscripciones = [{"curso_id": 1, "estado": "completado", "porcentaje_avance_global": 100.0,
                          "calificacion_final": 90.0, "fecha_inscripcion": INICIO,
                          "completado_en": t + timedelta(days=1), "origen": "catalogo"}]
        resultado = dataset._inscripciones_en(inscripciones, t, {1}, self.catalogo)
        self.assertEqual(resultado[0]["estado"], "activo")
        self.assertIsNone(resultado[0]["calificacion_final"])
        self.assertEqual(resultado[0]["porcentaje_avance_global"], 50.0)


# --- Activación -----------------------------------------------------------------


class DecidirActivacionTests(SimpleTestCase):
    def _m(self, **cambios):
        return {"f1": 0.7, "f1_baseline_mayoritaria": 0.5, "f1_baseline_regla": 0.6,
                "dataset_sha256": "a", "origen": "real", **cambios}

    def test_supera_lineas_base_sin_activa(self):
        self.assertEqual(activar_modelo.decidir_activacion(self._m(), None, False), ([], []))

    def test_no_supera_una_linea_base_ni_forzando(self):
        errores, _ = activar_modelo.decidir_activacion(self._m(f1_baseline_regla=0.7), None, True)
        self.assertEqual(len(errores), 1)

    def test_peor_que_la_activa_con_el_mismo_dataset(self):
        errores, _ = activar_modelo.decidir_activacion(self._m(), self._m(f1=0.8), True)
        self.assertEqual(len(errores), 1)
        self.assertEqual(activar_modelo.decidir_activacion(self._m(), self._m(f1=0.7), False), ([], []))

    def test_otro_dataset_exige_forzar(self):
        activa = self._m(dataset_sha256="b", f1=0.9)
        self.assertTrue(activar_modelo.decidir_activacion(self._m(), activa, False)[0])
        errores, avisos = activar_modelo.decidir_activacion(self._m(), activa, True)
        self.assertEqual(errores, [])
        self.assertTrue(avisos)

    def test_sintetico_avisa_y_exige_forzar(self):
        errores, avisos = activar_modelo.decidir_activacion(self._m(origen="sintetico"), None, False)
        self.assertTrue(errores and avisos)
        errores, avisos = activar_modelo.decidir_activacion(self._m(origen="sintetico"), None, True)
        self.assertEqual(errores, [])
        self.assertIn("SINTÉTICOS", avisos[0])


class ActivarModeloOrdenTests(SimpleTestCase):
    METRICAS = {"f1": 0.7, "f1_baseline_mayoritaria": 0.5, "f1_baseline_regla": 0.6,
                "dataset_sha256": "a", "origen": "real"}

    def _select_one(self, candidata, activa):
        def select_one(tabla, columns, filters, operation):
            return activa if ("activo", "eq.true") in filters else candidata
        return select_one

    def test_cambia_de_version(self):
        candidata = {"id": 2, "version": "v2", "activo": False, "metricas": self.METRICAS}
        activa = {"id": 1, "version": "v1", "activo": True, "metricas": {**self.METRICAS, "f1": 0.65}}
        with mock.patch("core.supabase.select_one", self._select_one(candidata, activa)), \
                mock.patch("core.supabase.update") as update:
            call_command("activar_modelo", "aprobacion", "v2", stdout=io.StringIO())
        self.assertEqual([c.args[1] for c in update.call_args_list], [{"activo": False}, {"activo": True}])
        self.assertEqual([c.kwargs["filters"] for c in update.call_args_list], [(("id", "eq.1"),), (("id", "eq.2"),)])

    def test_si_falla_la_activacion_reactiva_la_anterior(self):
        candidata = {"id": 2, "version": "v2", "activo": False, "metricas": self.METRICAS}
        activa = {"id": 1, "version": "v1", "activo": True, "metricas": self.METRICAS}
        llamadas = []

        def update(tabla, valores, filters, operation):
            llamadas.append((valores, filters))
            if filters == (("id", "eq.2"),):
                raise DataAccessError("único")

        with mock.patch("core.supabase.select_one", self._select_one(candidata, activa)), \
                mock.patch("core.supabase.update", update):
            with self.assertRaisesMessage(CommandError, "se mantiene la versión anterior"):
                call_command("activar_modelo", "aprobacion", "v2")
        self.assertEqual(llamadas[-1], ({"activo": True}, (("id", "eq.1"),)))

    def test_rechaza_sin_cumplir_las_comprobaciones(self):
        candidata = {"id": 2, "version": "v2", "activo": False,
                     "metricas": {**self.METRICAS, "origen": "sintetico"}}
        with mock.patch("core.supabase.select_one", self._select_one(candidata, None)), \
                mock.patch("core.supabase.update") as update:
            with self.assertRaisesMessage(CommandError, "--forzar"):
                call_command("activar_modelo", "aprobacion", "v2", stdout=io.StringIO())
        update.assert_not_called()


# --- Entrenamiento y exportación (solo con scikit-learn) ---------------------------


@skipUnless(HAY_SKLEARN, "requiere scikit-learn (requirements-ml.txt)")
class ExportarArbolTests(SimpleTestCase):
    def test_ida_y_vuelta_con_predecir(self):
        from sklearn.tree import DecisionTreeClassifier

        from entrenamiento.exportar_arbol import arbol_a_json

        rng = random.Random(0)
        filas = [{c: round(rng.uniform(0, 5), 3) for c in modelo.CARACTERISTICAS} for _ in range(400)]
        y = [int(f["dominio_conceptos_curso"] + rng.gauss(0, 1) > 2.5 + f["dificultad_curso"] / 5) for f in filas]
        x = [[f[c] for c in modelo.CARACTERISTICAS] for f in filas]
        arbol_sk = DecisionTreeClassifier(max_depth=4, min_samples_leaf=20, class_weight="balanced",
                                          random_state=1).fit(x[:300], y[:300])
        arbol = arbol_a_json(arbol_sk, modelo.CARACTERISTICAS)
        self.assertTrue(modelo.validar_arbol(arbol, modelo.CARACTERISTICAS))
        esperadas = arbol_sk.predict_proba(x[300:350])[:, 1]
        for fila, esperada in zip(filas[300:350], esperadas):
            self.assertAlmostEqual(modelo.predecir(arbol, fila)[0], float(esperada), places=9)
        self.assertEqual(json.loads(json.dumps(arbol)), arbol)


@skipUnless(HAY_SKLEARN, "requiere scikit-learn (requirements-ml.txt)")
class EntrenarTests(SimpleTestCase):
    def test_escribe_los_cuatro_ficheros_y_las_metricas(self):
        from entrenamiento import entrenar

        catalogo = _catalogo()
        datos = sinteticos.generar(catalogo, 300, 11, INICIO)
        with _con_04():
            filas = dataset.construir(datos["alumnos"], datos["inscripciones"], datos["intentos"],
                                      datos["eventos"], catalogo)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "dataset.csv"
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                escritor = csv.DictWriter(f, fieldnames=dataset.COLUMNAS_DATASET)
                escritor.writeheader()
                escritor.writerows(filas)
            salida = Path(tmp) / "modelos"
            with mock.patch.object(entrenar, "DIRECTORIO_MODELOS", salida):
                resultado = entrenar.entrenar(ruta, "sintetico", semilla=3)
            v = resultado["version"]
            nombres = sorted(p.name for p in salida.iterdir())
            self.assertEqual(nombres, sorted(f"aprobacion-{v}{s}" for s in
                                             (".json", ".metricas.json", ".txt", ".joblib")))
            metricas = json.loads((salida / f"aprobacion-{v}.metricas.json").read_text(encoding="utf-8"))
            arbol = json.loads((salida / f"aprobacion-{v}.json").read_text(encoding="utf-8"))
        for clave in ("accuracy", "precision", "recall", "f1", "matriz_confusion", "f1_cv_media",
                      "f1_baseline_mayoritaria", "f1_baseline_regla", "n_train", "n_test",
                      "tasa_positivos", "origen", "semilla", "dataset_sha256"):
            self.assertIn(clave, metricas)
        self.assertEqual(metricas["origen"], "sintetico")
        self.assertEqual(metricas["semilla"], 3)
        self.assertEqual(metricas["n_train"] + metricas["n_test"], len(filas))
        self.assertEqual(len(metricas["dataset_sha256"]), 64)
        self.assertTrue(modelo.validar_arbol(arbol, modelo.CARACTERISTICAS, profundidad_max=4))
