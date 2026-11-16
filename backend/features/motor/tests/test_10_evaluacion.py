"""Tests del paquete 10: evaluación offline. Sin red ni base de datos."""

import copy
import importlib.util
import io
import json
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock, skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from entrenamiento import evaluacion
from features.motor import config
from features.motor.estrategias import reglas as rg

try:
    from entrenamiento import sinteticos
except ImportError:  # pragma: no cover
    sinteticos = None

BASE = Path(__file__).resolve().parents[3]
HAY_SKLEARN = importlib.util.find_spec("sklearn") is not None
INICIO = datetime(2026, 1, 12, tzinfo=timezone.utc)


def _catalogo():
    return sinteticos.cargar_catalogo_json(BASE / "entrenamiento" / "catalogo_ejemplo.json")


def _curso(curso_id, conceptos):
    return {"id": curso_id, "codigo_curso": f"C-{curso_id}", "titulo": f"Curso {curso_id}", "descripcion": "",
            "dificultad": 1, "nivel": "Principiante", "publicado": True, "conceptos": conceptos,
            "areas": [], "prerrequisitos": [], "temas": []}


FIXTURE = {
    "cursos": {
        1: _curso(1, {"x": 1.0}),
        2: _curso(2, {"x": 1.0}),
        3: _curso(3, {"y": 1.0}),
        4: _curso(4, {"z": 1.0}),
    },
    "conceptos": {}, "areas": {}, "carrera_areas": {}, "ejercicios_diagnostico": {},
}


class MetricasTests(SimpleTestCase):
    def test_evaluar_k_ejemplo_a_mano(self):
        reales = {"a": {1, 2}, "b": {5}, "c": set(), "d": {7}}
        recomendados = {"a": [1, 3, 2, 9], "b": [4, 6, 8], "c": [1], "x": [1, 2, 3]}
        m = evaluacion.evaluar_k(recomendados, reales, 3)
        # a: 2 aciertos (1, 2) -> P = 2/3, R = 1, hit; b: nada; d: sin lista -> nada; c y x no cuentan.
        self.assertEqual(m["n_alumnos"], 3)
        self.assertAlmostEqual(m["precision"], (2 / 3) / 3)
        self.assertAlmostEqual(m["recall"], 1 / 3)
        self.assertAlmostEqual(m["hit_rate"], 1 / 3)

    def test_evaluar_k_corta_en_k_y_sin_alumnos(self):
        m = evaluacion.evaluar_k({"a": [9, 8, 1]}, {"a": {1}}, 2)
        self.assertEqual((m["precision"], m["recall"], m["hit_rate"]), (0.0, 0.0, 0.0))
        vacio = evaluacion.evaluar_k({}, {"a": set()}, 3)
        self.assertEqual(vacio, {"precision": 0.0, "recall": 0.0, "hit_rate": 0.0, "n_alumnos": 0})

    def test_cobertura(self):
        self.assertAlmostEqual(evaluacion.cobertura({"a": [1, 2], "b": [2, 99]}, FIXTURE), 0.5)
        self.assertEqual(evaluacion.cobertura({}, FIXTURE), 0.0)

    def test_diversidad(self):
        # [1, 2, 3]: similitudes 1, 0, 0 -> 1 − 1/3; [1, 3]: 1 − 0; [4] no cuenta.
        valor = evaluacion.diversidad({"a": [1, 2, 3], "b": [1, 3], "c": [4]}, FIXTURE)
        self.assertAlmostEqual(valor, ((1 - 1 / 3) + 1.0) / 2)
        self.assertIsNone(evaluacion.diversidad({"a": [1], "b": []}, FIXTURE))

    def test_no_muta_argumentos(self):
        recomendados, reales = {"a": [1, 2]}, {"a": {1}}
        antes = copy.deepcopy((recomendados, reales))
        evaluacion.evaluar_k(recomendados, reales, 3)
        evaluacion.cobertura(recomendados, FIXTURE)
        evaluacion.diversidad(recomendados, FIXTURE)
        self.assertEqual((recomendados, reales), antes)


class CorteTemporalTests(SimpleTestCase):
    def _insc(self, usuario, curso, dias, estado="activo", completado_dias=None):
        return {"usuario_id": usuario, "curso_id": curso, "estado": estado, "calificacion_final": 90.0,
                "fecha_inscripcion": INICIO + timedelta(days=dias),
                "completado_en": INICIO + timedelta(days=completado_dias) if completado_dias is not None else None}

    def test_percentil_70_y_verdad(self):
        filas = [self._insc("u", c, d) for c, d in zip(range(1, 11), range(10))]
        t = evaluacion.corte_temporal(filas)
        self.assertEqual(t, INICIO + timedelta(days=6))
        self.assertEqual(evaluacion.verdad_desde(filas, t), {"u": {7, 8, 9, 10}})
        with self.assertRaises(ValueError):
            evaluacion.corte_temporal([])

    def test_estado_en_oculta_desenlaces_futuros(self):
        t = INICIO + timedelta(days=10)
        terminada = self._insc("u", 1, 0, "completado", 5)
        futura = self._insc("u", 2, 0, "completado", 10)
        abandonada = self._insc("u", 3, 0, "abandonado")
        self.assertEqual(evaluacion.estado_en(terminada, t)["estado"], "completado")
        self.assertEqual(evaluacion.estado_en(futura, t)["estado"], "activo")
        self.assertIsNone(evaluacion.estado_en(futura, t)["calificacion_final"])
        self.assertEqual(evaluacion.estado_en(abandonada, t)["estado"], "activo")

    def test_desenlaces_conocidos(self):
        t = INICIO + timedelta(days=10)
        inscripciones = [
            self._insc("u", 1, 0, "completado", 5),
            self._insc("u", 2, 0, "completado", 12),
            self._insc("u", 3, 0, "abandonado"),
            self._insc("u", 4, 0, "abandonado"),
            self._insc("u", 5, 0, "activo"),
        ]
        eventos = [
            {"usuario_id": "u", "curso_id": 3, "fecha": INICIO + timedelta(days=4)},
            {"usuario_id": "u", "curso_id": 4, "fecha": INICIO + timedelta(days=11)},
        ]
        self.assertEqual(evaluacion.desenlaces_conocidos(inscripciones, eventos, t), {("u", 1), ("u", 3)})


@skipUnless(sinteticos is not None, "requiere el generador de 07")
class SinFugasTests(SimpleTestCase):
    """Nada en `T` o después llega a un perfil, a las similitudes o a la popularidad."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalogo = _catalogo()
        cls.datos = sinteticos.generar(cls.catalogo, 200, 7, INICIO)

    def _todo(self, datos, t=None):
        alumnos, inscripciones, intentos, eventos = evaluacion._normalizados(datos)
        t = t or evaluacion.corte_temporal(inscripciones)
        reales = evaluacion.verdad_desde(inscripciones, t)
        perfiles = evaluacion.perfiles_en(alumnos, inscripciones, intentos, eventos, self.catalogo, t, set(reales))
        contexto = {"catalogo": self.catalogo, "reglas": evaluacion.cargar_reglas_semilla(),
                    "similitudes": evaluacion.similitudes_en(inscripciones, t), "modelo": None, "ahora": t}
        popularidad = evaluacion.popularidad_en(inscripciones, t)
        listas = evaluacion.recomendaciones(perfiles, contexto, popularidad, 3)
        return t, reales, perfiles, contexto["similitudes"], popularidad, listas

    def test_datos_posteriores_a_t_no_cambian_nada(self):
        t, reales, perfiles, similitudes, popularidad, listas = self._todo(self.datos)
        uid = sorted(reales)[0]
        curso = next(c for c in sorted(self.catalogo["cursos"]) if c not in reales[uid])
        tema = self.catalogo["cursos"][curso]["temas"][0]["id"]

        extra = copy.deepcopy(self.datos)
        for fecha in (t, t + timedelta(hours=1)):
            extra["eventos"] += [
                {"usuario_id": uid, "tipo": "quiz_intento", "objeto_tipo": "tema", "objeto_id": tema,
                 "curso_id": curso, "valor": 0.0, "datos": {}, "fecha": fecha},
                {"usuario_id": uid, "tipo": "curso_completado", "objeto_tipo": "curso", "objeto_id": curso,
                 "curso_id": curso, "valor": 100.0, "datos": {}, "fecha": fecha},
            ]
            extra["intentos"].append({"usuario_id": uid, "ejercicio_id": sinteticos.ejercicio_sintetico(tema, 1),
                                      "tema_id": tema, "tipo": sinteticos.TIPO_PRACTICA,
                                      "calificacion_obtenida": 0.0, "fecha_intento": fecha})
        # Otro alumno se inscribe y completa justo en T: cambia la verdad, no lo que sabe el motor.
        otro = sorted(reales)[1]
        extra["inscripciones"].append({
            "usuario_id": otro, "curso_id": curso, "estado": "completado", "porcentaje_avance_global": 100.0,
            "calificacion_final": 100.0, "fecha_inscripcion": t + timedelta(days=1),
            "completado_en": t + timedelta(days=2), "origen": "catalogo",
        })

        # T se fija: una inscripción nueva movería el percentil.
        _, reales2, perfiles2, similitudes2, popularidad2, listas2 = self._todo(extra, t)
        self.assertIn(curso, reales2[otro])
        self.assertEqual(perfiles2, perfiles)
        self.assertEqual(similitudes2, similitudes)
        self.assertEqual(popularidad2, popularidad)
        self.assertEqual(listas2, listas)

    def test_perfiles_solo_con_inscripciones_previas(self):
        t, reales, perfiles, *_ = self._todo(self.datos)
        _, inscripciones, _, _ = evaluacion._normalizados(self.datos)
        for uid, perfil in perfiles.items():
            for curso_id, inscripcion in perfil["inscripciones"].items():
                self.assertLess(inscripcion["fecha_inscripcion"], t)
                if inscripcion["estado"] == "completado":
                    self.assertLess(inscripcion["completado_en"], t)
            self.assertFalse(set(perfil["inscripciones"]) & reales[uid])

    def test_pesos_temporales_se_restauran(self):
        original = config.PESOS_ESTRATEGIA
        with self.assertRaises(RuntimeError):
            with evaluacion.pesos_temporales({"nuevo": dict(evaluacion.PESOS_B)}):
                self.assertEqual(config.PESOS_ESTRATEGIA["nuevo"], evaluacion.PESOS_B)
                self.assertEqual(config.PESOS_ESTRATEGIA["con_historia"], original["con_historia"])
                raise RuntimeError
        self.assertIs(config.PESOS_ESTRATEGIA, original)


# --- reglas_semilla.json frente a migrations 0008 + 0009 ---------------------

_FILA = re.compile(
    r"\('(?P<codigo>\w+)',\s*'(?P<ambito>\w+)',\s*(?P<prioridad>-?\d+),\s*"
    r"'(?P<condicion>\{.*?\})'::jsonb,\s*'(?P<accion>\{.*?\})'::jsonb,",
    re.S,
)
_CONDICION_R01 = re.compile(r"SET condicion = '(\{.*?\})'::jsonb.*?WHERE codigo = 'R01'", re.S)


def _reglas_de_las_migraciones():
    """Estado de las reglas tras aplicar 0008 y luego 0009 (que apaga F01,
    limita R01 a Principiante y añade R07)."""
    reglas = {}
    for nombre in ("0008_motor_reglas.sql", "0009_motor_prerrequisitos_suaves.sql"):
        sql = (BASE / "migrations" / nombre).read_text(encoding="utf-8")
        for m in _FILA.finditer(sql):
            accion = json.loads(m["accion"])
            reglas[m["codigo"]] = {"prioridad": int(m["prioridad"]), "puntos": accion.get("puntos"),
                                   "ambito": m["ambito"], "condicion": json.loads(m["condicion"]),
                                   "accion": accion, "activa": True}
        if nombre.startswith("0009"):
            reglas["F01"]["activa"] = False
            reglas["R01"]["condicion"] = json.loads(_CONDICION_R01.search(sql).group(1))
    return reglas


class ReglasSemillaTests(SimpleTestCase):
    def test_coincide_con_las_migraciones(self):
        en_sql = _reglas_de_las_migraciones()
        semilla = json.loads(evaluacion.RUTA_REGLAS_SEMILLA.read_text(encoding="utf-8"))
        en_json = {
            r["codigo"]: {"prioridad": r["prioridad"], "puntos": r["accion"].get("puntos"),
                          "ambito": r["ambito"], "condicion": r["condicion"], "accion": r["accion"],
                          "activa": r["activa"]}
            for r in semilla
        }
        self.assertEqual(len(en_sql), 12)
        self.assertEqual(en_json, en_sql)

    def test_todas_validas_y_ordenadas(self):
        reglas = evaluacion.cargar_reglas_semilla()
        # 12 reglas, de las que se cargan las 11 activas: F01 está apagada desde 0009.
        self.assertEqual(len(reglas), 11)
        self.assertNotIn("F01", {r["codigo"] for r in reglas})
        for regla in reglas:
            self.assertEqual(rg.validar_regla(regla), [], regla["codigo"])
        self.assertEqual(reglas, sorted(reglas, key=lambda r: (-r["prioridad"], r["id"])))


# --- Ejecución completa -------------------------------------------------------


@skipUnless(sinteticos is not None, "requiere el generador de 07")
class EjecutarTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name) / "sinteticos"
        catalogo = _catalogo()
        sinteticos.escribir(sinteticos.generar(catalogo, 200, 42, INICIO), catalogo, cls.dir)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    def test_sin_modelo_rangos_sanos(self):
        with mock.patch("core.supabase._request", side_effect=AssertionError("no debe tocar la base")):
            r = evaluacion.ejecutar(self.dir, k=3, con_modelo=False)
        esperadas = [n for n in evaluacion.CONFIGURACIONES if n not in evaluacion.CONFIGURACIONES_CON_MODELO]
        self.assertEqual(list(r["configuraciones"]), esperadas)
        self.assertEqual((r["origen"], r["k"], r["semilla"], r["con_modelo"]), ("sintetico", 3, 42, False))
        self.assertIsNone(r["modelo"])
        self.assertEqual(r["n_alumnos_total"], 200)
        self.assertGreater(r["n_alumnos_evaluados"], 0)
        self.assertLessEqual(r["n_alumnos_sin_candidatos"], r["n_alumnos_evaluados"])
        self.assertRegex(r["dataset_sha256"], r"^[0-9a-f]{64}$")
        for nombre, m in r["configuraciones"].items():
            with self.subTest(configuracion=nombre):
                self.assertEqual(m["n_alumnos"], r["n_alumnos_evaluados"])
                for clave in ("precision", "recall", "hit_rate", "cobertura", "diversidad"):
                    self.assertGreaterEqual(m[clave], 0.0)
                    self.assertLessEqual(m[clave], 1.0)
        tabla = evaluacion.tabla_markdown(r)
        self.assertIn("SINTÉTICOS", tabla)
        self.assertEqual(tabla.count("\n| "), len(esperadas) + 1)

    @skipUnless(HAY_SKLEARN, "requiere scikit-learn (requirements-ml.txt)")
    def test_con_modelo_entrena_en_carpeta_temporal(self):
        from entrenamiento import entrenar

        directorio = entrenar.DIRECTORIO_MODELOS
        antes = set(directorio.glob("*")) if directorio.exists() else set()
        r = evaluacion.ejecutar(self.dir, k=3, con_modelo=True)
        self.assertEqual(list(r["configuraciones"]), evaluacion.CONFIGURACIONES)
        self.assertEqual(r["modelo"]["metricas"]["origen"], "sintetico")
        self.assertEqual(entrenar.DIRECTORIO_MODELOS, directorio)
        self.assertEqual(set(directorio.glob("*")) if directorio.exists() else set(), antes)

    def test_orden_escribe_json_y_tabla(self):
        with tempfile.TemporaryDirectory() as salida, \
                mock.patch("features.motor.management.commands.evaluar_motor.directorio_salida",
                           return_value=Path(salida)), \
                mock.patch("core.supabase._request", side_effect=AssertionError("no debe tocar la base")):
            out = io.StringIO()
            call_command("evaluar_motor", datos=str(self.dir), k=3, sin_modelo=True, stdout=out)
            call_command("evaluar_motor", datos=str(self.dir), k=3, sin_modelo=True, stdout=io.StringIO())
            archivos = sorted(Path(salida).glob("evaluacion-*.json"))
            self.assertEqual(len(archivos), 2)
            guardado = json.loads(archivos[0].read_text(encoding="utf-8"))
        self.assertEqual(guardado["origen"], "sintetico")
        self.assertIn("| hibrido |", out.getvalue())

    def test_orden_rechaza_directorio_inexistente(self):
        with self.assertRaisesMessage(CommandError, "No existe el directorio"):
            call_command("evaluar_motor", datos=str(self.dir / "nada"), sin_modelo=True, stdout=io.StringIO())
