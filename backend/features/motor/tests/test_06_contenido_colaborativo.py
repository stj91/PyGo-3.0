"""Tests del paquete 06: estrategias de contenido y colaborativa, y su lote. Sin red."""

import ast
import math
import os
import tempfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from features.motor import catalogo as catalogo_mod
from features.motor import config
from features.motor.estrategias import colaborativo, contenido
from features.motor.management.commands import calcular_similitudes as orden

AHORA = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
USUARIO = "11111111-1111-1111-1111-111111111111"

# --- Catálogo real de 01-cimientos.md §2 ------------------------------------

_AREAS = {
    "fundamentos": ("Fundamentos", [("variables_tipos", "Variables y tipos"), ("colecciones", "Listas y tuplas"),
                                    ("condicionales", "Condicionales"), ("bucles", "Bucles"),
                                    ("funciones", "Funciones")]),
    "poo": ("Programación orientada a objetos", [("poo_clases", "Clases y objetos"),
                                                 ("herencia_polimorfismo", "Herencia y polimorfismo")]),
    "datos": ("Datos", [("diccionarios_conjuntos", "Diccionarios y conjuntos"),
                        ("comprensiones", "Comprensiones"), ("json_apis", "JSON y APIs")]),
    "automatizacion": ("Automatización", [("excepciones", "Excepciones"), ("archivos", "Archivos"),
                                          ("libreria_estandar", "Librería estándar"), ("modulos", "Módulos")]),
}

# id, código, título, dificultad, nivel, etiquetas, requiere, módulos [(orden, {concepto: peso})]
_CURSOS = [
    (1, "PY-101", "Fundamentos de Python", 1, "Principiante",
     {"variables_tipos": 1, "colecciones": 0.6}, [], [{"variables_tipos": 1}, {"colecciones": 1}]),
    (2, "PY-201", "Control de flujo", 1, "Principiante",
     {"condicionales": 1, "bucles": 1}, [1], [{"condicionales": 1}, {"bucles": 1}]),
    (4, "PY-401", "Funciones y Modularidad", 2, "Principiante",
     {"funciones": 1, "modulos": 0.7}, [2], [{"funciones": 1}, {"modulos": 0.7, "funciones": 0.3}]),
    (3, "PY-301", "Programación Orientada a Objetos", 3, "Intermedio",
     {"poo_clases": 1}, [4], [{"poo_clases": 1}]),
    (5, "PY-501", "Colecciones Avanzadas y Comprensiones", 3, "Intermedio",
     {"diccionarios_conjuntos": 1, "comprensiones": 1, "colecciones": 0.5}, [4],
     [{"diccionarios_conjuntos": 1}, {"comprensiones": 1}]),
    (6, "PY-601", "Excepciones y Archivos", 3, "Intermedio",
     {"excepciones": 1, "archivos": 1}, [4], [{"excepciones": 1}, {"archivos": 1}]),
    (7, "PY-701", "POO Avanzada", 4, "Avanzado",
     {"herencia_polimorfismo": 1, "poo_clases": 0.6}, [3],
     [{"herencia_polimorfismo": 1}, {"herencia_polimorfismo": 0.7, "poo_clases": 0.3}]),
    (8, "PY-801", "Librería Estándar y APIs", 4, "Avanzado",
     {"libreria_estandar": 1, "json_apis": 1, "modulos": 0.5}, [5, 6],
     [{"libreria_estandar": 1}, {"json_apis": 1}]),
]


def _catalogo():
    conceptos, contenido_filas, cursos, temas, prerrequisitos = [], [], [], [], []
    siguiente = 1
    for area, (nombre, hijos) in _AREAS.items():
        area_id = siguiente
        conceptos.append({"id": area_id, "clave": area, "nombre": nombre, "padre_id": None})
        siguiente += 1
        for clave, nombre_hijo in hijos:
            conceptos.append({"id": siguiente, "clave": clave, "nombre": nombre_hijo, "padre_id": area_id})
            siguiente += 1
    for curso_id, codigo, titulo, dificultad, nivel, etiquetas, requiere, modulos in _CURSOS:
        cursos.append({"id": curso_id, "codigo_curso": codigo, "titulo": titulo, "descripcion": "",
                       "dificultad": dificultad, "nivel": nivel, "publicado": True})
        contenido_filas += [{"objeto_tipo": "curso", "objeto_id": curso_id, "concepto_clave": c, "peso": p}
                            for c, p in etiquetas.items()]
        prerrequisitos += [{"curso_id": curso_id, "requiere_curso_id": r, "calificacion_minima": 80}
                           for r in requiere]
        for orden_tema, etiquetas_tema in enumerate(modulos, start=1):
            tema_id = curso_id * 10 + orden_tema
            temas.append({"id": tema_id, "curso_id": curso_id, "orden": orden_tema, "titulo": f"T{tema_id}"})
            contenido_filas += [{"objeto_tipo": "tema", "objeto_id": tema_id, "concepto_clave": c, "peso": p}
                                for c, p in etiquetas_tema.items()]
    return catalogo_mod.ensamblar_catalogo(cursos, temas, conceptos, contenido_filas, prerrequisitos, [], [])


CATALOGO = _catalogo()


def _perfil(**cambios):
    perfil = {
        "usuario_id": USUARIO, "nivel": "Principiante", "nivel_asignado": "Principiante",
        "nivel_inferido": None, "carrera_clave": None, "intereses": {}, "dominio": {},
        "evidencias": {}, "inscripciones": {}, "cursos_completados": [],
        "calificacion_por_curso": {}, "modulos_en_refuerzo": {}, "tasa_aprobacion_modulos": None,
        "intentos_promedio": None, "dias_inactivo": None, "calculado_en": AHORA,
    }
    return {**perfil, **cambios}


def _inscripcion(curso_id, estado, calificacion=None):
    return {"curso_id": curso_id, "estado": estado, "porcentaje_avance_global": 100 if estado == "completado" else 40,
            "calificacion_final": calificacion, "fecha_inscripcion": AHORA,
            "completado_en": AHORA if estado == "completado" else None, "origen": None}


def _contexto(similitudes=None):
    return {"catalogo": CATALOGO, "reglas": [], "similitudes": similitudes or {}, "modelo": None, "ahora": AHORA}


def _intereses_area(area, peso=1.0):
    return {clave: peso for clave in CATALOGO["areas"][area]}


# --- Contenido --------------------------------------------------------------


class CosenoTests(SimpleTestCase):
    def test_identicos(self):
        self.assertAlmostEqual(contenido.coseno({"a": 1, "b": 2}, {"a": 1, "b": 2}), 1.0)

    def test_ortogonales(self):
        self.assertEqual(contenido.coseno({"a": 1}, {"b": 1}), 0.0)

    def test_vacios(self):
        self.assertEqual(contenido.coseno({}, {"a": 1}), 0.0)
        self.assertEqual(contenido.coseno({"a": 1}, {}), 0.0)

    def test_ceros(self):
        self.assertEqual(contenido.coseno({"a": 0.0}, {"a": 1.0}), 0.0)

    def test_valor_calculado_a_mano(self):
        self.assertAlmostEqual(contenido.coseno({"a": 1, "b": 1}, {"a": 1}), 1 / math.sqrt(2))


class VectorAlumnoTests(SimpleTestCase):
    def test_intereses_mas_cursos_completados_con_tope(self):
        perfil = _perfil(intereses={"colecciones": 0.8, "comprensiones": 0.5}, cursos_completados=[1])
        vector = contenido.vector_alumno(perfil, CATALOGO)
        # PY-101: variables_tipos 1, colecciones max(0.6, 0.5×1)=0.6
        self.assertAlmostEqual(vector["variables_tipos"], 0.5)
        self.assertAlmostEqual(vector["colecciones"], 1.0)  # 0.8 + 0.3 = 1.1 -> tope 1.0
        self.assertAlmostEqual(vector["comprensiones"], 0.5)
        self.assertEqual(set(vector), {"variables_tipos", "colecciones", "comprensiones"})

    def test_no_muta_el_perfil(self):
        intereses = {"colecciones": 0.8}
        perfil = _perfil(intereses=intereses, cursos_completados=[1])
        contenido.vector_alumno(perfil, CATALOGO)
        self.assertEqual(intereses, {"colecciones": 0.8})


class PuntuarContenidoTests(SimpleTestCase):
    def _candidatos(self, *ids):
        return [CATALOGO["cursos"][i] for i in ids]

    def test_alumno_de_datos_prefiere_py501_a_py301(self):
        perfil = _perfil(intereses=_intereses_area("datos"))
        puntos = {p["curso_id"]: p["puntuacion"] for p in
                  contenido.puntuar(perfil, self._candidatos(3, 5), _contexto())}
        self.assertIn(5, puntos)
        self.assertGreater(puntos[5], puntos.get(3, 0.0))

    def test_explicacion_nombra_el_concepto_correcto(self):
        perfil = _perfil(intereses={"comprensiones": 1.0, "diccionarios_conjuntos": 0.4})
        [p] = contenido.puntuar(perfil, self._candidatos(5), _contexto())
        [razon] = p["razones"]
        self.assertEqual(razon["origen"], "contenido")
        self.assertEqual(razon["texto"], "Coincide con tu interés en Comprensiones.")
        self.assertAlmostEqual(razon["aporte"], p["puntuacion"])

    def test_puntuacion_baja_sin_texto(self):
        perfil = _perfil(intereses={"colecciones": 0.1, "poo_clases": 1.0})
        [p] = contenido.puntuar(perfil, self._candidatos(5), _contexto())
        self.assertLess(p["puntuacion"], 0.2)
        self.assertGreater(p["puntuacion"], 0.0)
        self.assertIsNone(p["razones"][0]["texto"])

    def test_sin_intereses_ni_historia(self):
        self.assertEqual(contenido.puntuar(_perfil(), self._candidatos(1, 3, 5), _contexto()), [])

    def test_omite_candidatos_con_cero(self):
        perfil = _perfil(intereses=_intereses_area("datos"))
        ids = [p["curso_id"] for p in contenido.puntuar(perfil, self._candidatos(2, 3, 5, 8), _contexto())]
        self.assertEqual(ids, [5, 8])

    def test_similitud_entre_cursos(self):
        cursos = CATALOGO["cursos"]
        self.assertAlmostEqual(contenido.similitud_entre_cursos(cursos[5], cursos[5]), 1.0)
        self.assertEqual(contenido.similitud_entre_cursos(cursos[2], cursos[3]), 0.0)
        self.assertGreater(contenido.similitud_entre_cursos(cursos[3], cursos[7]), 0.0)


# --- Colaborativo -----------------------------------------------------------


class InteraccionesTests(SimpleTestCase):
    def test_valores_y_bono_por_calificacion(self):
        filas = [
            {"usuario_id": "u1", "curso_id": 1, "estado": "completado", "calificacion_final": 85},
            {"usuario_id": "u1", "curso_id": 2, "estado": "completado", "calificacion_final": "95.00"},
            {"usuario_id": "u1", "curso_id": 3, "estado": "activo", "calificacion_final": None},
            {"usuario_id": "u1", "curso_id": 4, "estado": "abandonado", "calificacion_final": 99},
            {"usuario_id": "u1", "curso_id": 5, "estado": "desconocido", "calificacion_final": None},
        ]
        valores = {i["curso_id"]: i["valor"] for i in colaborativo.interacciones(filas)}
        self.assertEqual(valores, {1: 1.0, 2: 1.0, 3: 0.6, 4: 0.2})

    def test_bono_con_tope(self):
        with mock.patch.object(config, "VALOR_INTERACCION", {"completado": 0.9}):
            [i] = colaborativo.interacciones(
                [{"usuario_id": "u1", "curso_id": 1, "estado": "completado", "calificacion_final": 90}])
        self.assertEqual(i["valor"], 1.0)
        with mock.patch.object(config, "VALOR_INTERACCION", {"completado": 0.7}):
            [i] = colaborativo.interacciones(
                [{"usuario_id": "u1", "curso_id": 1, "estado": "completado", "calificacion_final": 90}])
        self.assertAlmostEqual(i["valor"], 0.9)

    def test_duplicados_se_quedan_con_el_maximo(self):
        filas = [
            {"usuario_id": "u1", "curso_id": 1, "estado": "abandonado", "calificacion_final": None},
            {"usuario_id": "u1", "curso_id": "1", "estado": "activo", "calificacion_final": ""},
            {"usuario_id": "u1", "curso_id": 1, "estado": "abandonado", "calificacion_final": None},
        ]
        self.assertEqual(colaborativo.interacciones(filas),
                         [{"usuario_id": "u1", "curso_id": 1, "valor": 0.6}])


def _i(usuario, curso, valor):
    return {"usuario_id": usuario, "curso_id": curso, "valor": valor}


class CalcularSimilitudesTests(SimpleTestCase):
    INTERACCIONES = [
        _i("u1", 1, 1.0), _i("u1", 2, 0.6),
        _i("u2", 1, 1.0), _i("u2", 3, 0.2),
        _i("u3", 2, 1.0), _i("u3", 3, 1.0),
    ]

    def test_ejemplo_calculado_a_mano(self):
        s = colaborativo.calcular_similitudes(self.INTERACCIONES)
        n1, n2, n3 = math.sqrt(1 + 1), math.sqrt(0.36 + 1), math.sqrt(0.04 + 1)
        self.assertAlmostEqual(s[1][2]["similitud"], 0.6 / (n1 * n2))  # ≈ 0.3638
        self.assertAlmostEqual(s[1][3]["similitud"], 0.2 / (n1 * n3))  # ≈ 0.1387
        self.assertAlmostEqual(s[2][3]["similitud"], 1.0 / (n2 * n3))  # ≈ 0.8408
        self.assertAlmostEqual(s[2][3]["similitud"], 0.8408, places=4)

    def test_simetrica_sin_autopares(self):
        s = colaborativo.calcular_similitudes(self.INTERACCIONES)
        for a, vecinos in s.items():
            self.assertNotIn(a, vecinos)
            for b, par in vecinos.items():
                self.assertEqual(s[b][a], par)

    def test_soporte(self):
        s = colaborativo.calcular_similitudes(
            self.INTERACCIONES + [_i("u4", 1, 1.0), _i("u4", 2, 1.0), _i("u5", 4, 1.0)])
        self.assertEqual(s[1][2]["soporte"], 2)
        self.assertEqual(s[2][3]["soporte"], 1)
        self.assertNotIn(4, s)  # sin co-ocurrencias: soporte 0, se omite

    def test_vacio(self):
        self.assertEqual(colaborativo.calcular_similitudes([]), {})


def _sim(similitud, soporte):
    return {"similitud": similitud, "soporte": soporte}


def _simetrica(pares):
    resultado = {}
    for (a, b), par in pares.items():
        resultado.setdefault(a, {})[b] = par
        resultado.setdefault(b, {})[a] = par
    return resultado


class PuntuarColaborativoTests(SimpleTestCase):
    def test_soporte_bajo_el_minimo_se_ignora(self):
        perfil = _perfil(inscripciones={1: _inscripcion(1, "completado", 85), 2: _inscripcion(2, "activo")})
        similitudes = _simetrica({(4, 1): _sim(0.5, 6), (4, 2): _sim(0.9, config.SOPORTE_MINIMO - 1)})
        [p] = colaborativo.puntuar(perfil, [CATALOGO["cursos"][4]], _contexto(similitudes))
        self.assertAlmostEqual(p["puntuacion"], 1.0)  # sólo cuenta (4,1): 0.5×1.0 / 0.5

    def test_candidato_sin_pares_validos_se_omite(self):
        perfil = _perfil(inscripciones={1: _inscripcion(1, "completado", 85)})
        similitudes = _simetrica({(4, 1): _sim(0.5, 2)})
        self.assertEqual(colaborativo.puntuar(perfil, [CATALOGO["cursos"][4]], _contexto(similitudes)), [])

    def test_sin_historia(self):
        similitudes = _simetrica({(4, 1): _sim(0.5, 9)})
        self.assertEqual(colaborativo.puntuar(_perfil(), [CATALOGO["cursos"][4]], _contexto(similitudes)), [])

    def test_explicacion_usa_un_curso_completado(self):
        perfil = _perfil(inscripciones={1: _inscripcion(1, "completado", 85), 2: _inscripcion(2, "activo")})
        similitudes = _simetrica({(4, 1): _sim(0.2, 6), (4, 2): _sim(0.9, 6)})
        [p] = colaborativo.puntuar(perfil, [CATALOGO["cursos"][4]], _contexto(similitudes))
        self.assertAlmostEqual(p["puntuacion"], (0.2 * 1.0 + 0.9 * 0.6) / 1.1)
        [razon] = p["razones"]
        self.assertEqual(razon["origen"], "colaborativo")
        self.assertEqual(razon["texto"],
                         "Alumnos que completaron Fundamentos de Python tomaron este curso después.")
        self.assertAlmostEqual(razon["aporte"], p["puntuacion"])

    def test_sin_curso_completado_no_hay_texto(self):
        perfil = _perfil(inscripciones={2: _inscripcion(2, "activo")})
        similitudes = _simetrica({(4, 2): _sim(0.9, 6)})
        [p] = colaborativo.puntuar(perfil, [CATALOGO["cursos"][4]], _contexto(similitudes))
        self.assertIsNone(p["razones"][0]["texto"])


class CargarSimilitudesTests(SimpleTestCase):
    def test_lee_paginado_e_ignora_pares_invalidados(self):
        filas = [
            {"curso_a": 1, "curso_b": 2, "similitud": "0.3638", "soporte": 6},
            {"curso_a": 2, "curso_b": 1, "similitud": "0.3638", "soporte": 6},
            {"curso_a": 1, "curso_b": 3, "similitud": 0, "soporte": 0},
        ]
        with mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 0), \
                mock.patch.object(colaborativo.supabase, "select", return_value=filas) as select:
            resultado = colaborativo.cargar_similitudes()
        self.assertEqual(resultado, {1: {2: _sim(0.3638, 6)}, 2: {1: _sim(0.3638, 6)}})
        self.assertEqual(select.call_args.args[0], "similitud_cursos")

    def test_leer_paginado(self):
        datos = list(range(2500))
        llamadas = []

        def pagina(desde, tamano):
            llamadas.append(desde)
            return datos[desde:desde + tamano]

        self.assertEqual(colaborativo.leer_paginado(pagina), datos)
        self.assertEqual(llamadas, [0, 1000, 2000])


# --- Orden calcular_similitudes ---------------------------------------------

_CSV = """usuario_id,curso_id,estado,porcentaje_avance_global,calificacion_final,fecha_inscripcion,completado_en,origen
sint-000001,1,completado,100,92.5,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000001,2,activo,40,,2026-02-02T00:00:00+00:00,,catalogo
sint-000002,1,completado,100,81,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000002,2,completado,100,85,2026-02-02T00:00:00+00:00,2026-03-01T00:00:00+00:00,catalogo
sint-000003,1,completado,100,90,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000003,2,abandonado,10,,2026-02-02T00:00:00+00:00,,catalogo
sint-000004,1,completado,100,88,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000004,2,activo,20,,2026-02-02T00:00:00+00:00,,catalogo
sint-000005,1,completado,100,80,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000005,2,activo,30,,2026-02-02T00:00:00+00:00,,catalogo
sint-000005,2,activo,30,,2026-02-02T00:00:00+00:00,,catalogo
sint-000006,2,completado,100,70,2026-01-01T00:00:00+00:00,2026-02-01T00:00:00+00:00,catalogo
sint-000006,3,activo,50,,2026-02-02T00:00:00+00:00,,catalogo
"""


class OrdenCalcularSimilitudesTests(SimpleTestCase):
    def setUp(self):
        self.directorio = tempfile.mkdtemp()
        Path(self.directorio, "inscripciones.csv").write_text(_CSV, encoding="utf-8")

    def tearDown(self):
        os.remove(os.path.join(self.directorio, "inscripciones.csv"))
        os.rmdir(self.directorio)

    def _ejecutar(self, *args):
        salida = StringIO()
        call_command("calcular_similitudes", *args, stdout=salida)
        return salida.getvalue()

    def test_desde_csv_simula_e_imprime_los_totales(self):
        with mock.patch.object(orden, "supabase") as supabase:
            salida = self._ejecutar("--desde-csv", self.directorio, "--simular")
            salida_implicita = self._ejecutar("--desde-csv", self.directorio)
        self.assertEqual(supabase.mock_calls, [])
        for texto in (salida, salida_implicita):
            self.assertIn("Cursos: 3. Pares: 2. Pares con soporte >= 5: 1.", texto)
            self.assertIn("simulación", texto)

    def test_desde_csv_con_escribir_es_un_error(self):
        with mock.patch.object(orden, "supabase") as supabase:
            with self.assertRaisesMessage(CommandError, "--escribir"):
                self._ejecutar("--desde-csv", self.directorio, "--escribir")
        self.assertEqual(supabase.mock_calls, [])

    def test_csv_inexistente(self):
        with self.assertRaisesMessage(CommandError, "inscripciones.csv"):
            self._ejecutar("--desde-csv", os.path.join(self.directorio, "no-existe"))

    def _filas_bd(self):
        return [
            {"usuario_id": f"u{n}", "curso_id": c, "estado": "completado", "calificacion_final": 85}
            for n in range(5) for c in (1, 2)
        ] + [{"usuario_id": "u9", "curso_id": 3, "estado": "activo", "calificacion_final": None},
             {"usuario_id": "u9", "curso_id": 2, "estado": "activo", "calificacion_final": None}]

    def test_simular_contra_bd_solo_lee(self):
        with mock.patch.object(orden, "supabase") as supabase:
            supabase.select.return_value = self._filas_bd()
            salida = self._ejecutar("--simular")
        self.assertIn("Cursos: 3. Pares: 2. Pares con soporte >= 5: 1.", salida)
        supabase.upsert.assert_not_called()
        supabase.update.assert_not_called()
        self.assertEqual(supabase.select.call_args.args[0], "usuario_cursos")

    def test_escritura_upsert_ambas_direcciones_y_luego_invalida_obsoletas(self):
        with mock.patch.object(orden, "supabase") as supabase:
            supabase.select.return_value = self._filas_bd()
            salida = self._ejecutar()
        self.assertIn("escrito en similitud_cursos", salida)
        filas = [c.args[1] for c in supabase.upsert.call_args_list]
        self.assertEqual({(f["curso_a"], f["curso_b"]) for f in filas}, {(1, 2), (2, 1), (2, 3), (3, 2)})
        for llamada in supabase.upsert.call_args_list:
            self.assertEqual(llamada.args[0], "similitud_cursos")
            self.assertEqual(llamada.kwargs["on_conflict"], "curso_a,curso_b")
        inicio = {f["calculado_en"] for f in filas}
        self.assertEqual(len(inicio), 1)
        self.assertEqual([n for n, *_ in supabase.mock_calls if n != "select"][-1], "update")
        filtros = dict(supabase.update.call_args.kwargs["filters"])
        self.assertEqual(filtros["calculado_en"], f"lt.{inicio.pop()}")

    def test_filas_a_escribir_redondea(self):
        filas = orden.filas_a_escribir({1: {2: _sim(0.123456, 5)}}, "t")
        self.assertEqual(filas, [{"curso_a": 1, "curso_b": 2, "similitud": 0.1235, "soporte": 5,
                                  "calculado_en": "t"}])


class SinDependenciasPesadasTests(SimpleTestCase):
    def test_estrategias_no_importan_numpy_ni_pandas(self):
        carpeta = Path(contenido.__file__).parent
        for archivo in (carpeta / "contenido.py", carpeta / "colaborativo.py"):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            modulos = {alias.name.split(".")[0] for nodo in ast.walk(arbol)
                       if isinstance(nodo, ast.Import) for alias in nodo.names}
            modulos |= {(nodo.module or "").split(".")[0] for nodo in ast.walk(arbol)
                        if isinstance(nodo, ast.ImportFrom)}
            with self.subTest(archivo=archivo.name):
                self.assertFalse(modulos & {"numpy", "pandas", "sklearn"})
