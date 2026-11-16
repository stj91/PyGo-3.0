"""Tests del paquete 08: orquestación híbrida, diversidad, explicaciones, registro,
experimento y endpoints. Sin red ni base de datos."""

import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from django.test import Client, SimpleTestCase

from entrenamiento import sinteticos
from features.motor import config, diversidad, experimento, explicaciones, hibrido, registro
from features.motor.eventos.validacion import es_recomendacion_id
from features.motor.perfil.construir import construir_perfil

AHORA = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
USUARIO = "11111111-1111-1111-1111-111111111111"
OTRO = "22222222-2222-2222-2222-222222222222"
BASE = Path(__file__).resolve().parents[3]

CATALOGO = sinteticos.cargar_catalogo_json(BASE / "entrenamiento" / "catalogo_ejemplo.json")
# PY-101=1 (d1), PY-201=2 (d1, requiere 1), PY-301=3 (d3), PY-401=4 (d2), PY-501=5 (d3),
# PY-601=6 (d3), PY-701=7 (d4), PY-801=8 (d4).


# --- Reglas semilla reales, leídas de la migración 0008 ----------------------

_FILA = re.compile(
    r"\('(?P<codigo>\w+)',\s*'(?P<ambito>\w+)',\s*(?P<prioridad>-?\d+),\s*"
    r"'(?P<condicion>\{.*?\})'::jsonb,\s*'(?P<accion>\{.*?\})'::jsonb,",
    re.S,
)


def _reglas_semilla():
    sql = (BASE / "migrations" / "0008_motor_reglas.sql").read_text(encoding="utf-8")
    reglas = [
        {"id": i, "codigo": m["codigo"], "nombre": m["codigo"], "descripcion": "", "ambito": m["ambito"],
         "condicion": json.loads(m["condicion"]), "accion": json.loads(m["accion"]),
         "prioridad": int(m["prioridad"]), "activa": True}
        for i, m in enumerate(_FILA.finditer(sql), start=1)
    ]
    return sorted(reglas, key=lambda r: (-r["prioridad"], r["id"]))


REGLAS_SEMILLA = _reglas_semilla()
#: Sin F01/F02, para que haya candidatos de sobra.
SIN_FILTROS = [r for r in REGLAS_SEMILLA if r["ambito"] != "filtro"]


# --- Perfiles con el constructor real de 04 ----------------------------------


def _inscripcion(curso_id, estado, calificacion=None, fecha=None):
    return {
        "curso_id": curso_id, "estado": estado, "porcentaje_avance_global": 100 if estado == "completado" else 40,
        "calificacion_final": calificacion, "fecha_inscripcion": fecha or AHORA - timedelta(days=30),
        "completado_en": AHORA - timedelta(days=5) if estado == "completado" else None, "origen": "catalogo",
    }


def _perfil(nivel="Principiante", inscripciones=(), areas=(), carrera=None):
    entrada = {
        "usuario": {"id": USUARIO, "nivel_asignado": nivel, "carrera_clave": carrera},
        "inscripciones": list(inscripciones),
        "estados_temas": [],
        "intentos": [],
        "dominio": {},
        "evidencias": {},
        "intereses": [{"concepto_clave": a, "origen": "declarado", "peso": 1.0} for a in areas],
        "ultimo_evento": None,
    }
    return construir_perfil(entrada, CATALOGO, AHORA)


NUEVO = _perfil()
CON_HISTORIA = _perfil(inscripciones=[_inscripcion(1, "completado", 90)])
MODELO = {"nombre": "aprobacion", "version": "v1", "caracteristicas": [], "arbol": {}}


def _contexto(reglas=(), modelo=None, similitudes=None):
    return {"catalogo": CATALOGO, "reglas": list(reglas), "similitudes": similitudes or {},
            "modelo": modelo, "ahora": AHORA}


def _fija(puntos, texto=None, origen=None):
    """Estrategia falsa: `puntos` = {curso_id: puntuación}."""
    def puntuar(perfil, candidatos, contexto):
        ids = {c["id"] for c in candidatos}
        return [
            {"curso_id": c, "puntuacion": p,
             "razones": [{"origen": origen or "x", "texto": texto, "aporte": p}]}
            for c, p in puntos.items() if c in ids
        ]
    return puntuar


def _estrategias(**cambios):
    base = {"reglas": _fija({}, origen="regla:R"), "contenido": _fija({}, origen="contenido"),
            "colaborativo": _fija({}, origen="colaborativo"), "modelo": _fija({}, origen="modelo:m@v")}
    return {**base, **cambios}


def _por_curso(resultado):
    return {i["curso_id"]: i for i in resultado["items"]}


class _SinDiversidad(SimpleTestCase):
    def setUp(self):
        parche = mock.patch.object(config, "LAMBDA_DIVERSIDAD", 0.0)
        parche.start()
        self.addCleanup(parche.stop)


# --- Pipeline puro -------------------------------------------------------------


class ModoTests(_SinDiversidad):
    def test_modos(self):
        self.assertEqual(hibrido.modo(NUEVO, _contexto(modelo=MODELO)), "nuevo")
        self.assertEqual(hibrido.modo(CON_HISTORIA, _contexto()), "con_historia")
        self.assertEqual(hibrido.modo(CON_HISTORIA, _contexto(modelo=MODELO)), "con_modelo")

    def test_nuevo_usa_reglas_y_contenido_y_no_llama_al_resto(self):
        colaborativo = mock.Mock(return_value=[])
        modelo = mock.Mock(return_value=[])
        r = hibrido.recomendar(NUEVO, _contexto(modelo=MODELO), 8, _estrategias(
            reglas=_fija({1: 1.0}), contenido=_fija({2: 1.0}), colaborativo=colaborativo, modelo=modelo))
        self.assertEqual(r["modo"], "nuevo")
        colaborativo.assert_not_called()
        modelo.assert_not_called()
        items = _por_curso(r)
        self.assertAlmostEqual(items[1]["puntuacion"], 0.6)
        self.assertAlmostEqual(items[2]["puntuacion"], 0.4)

    def test_con_historia_pesa_el_colaborativo(self):
        r = hibrido.recomendar(CON_HISTORIA, _contexto(), 8, _estrategias(
            reglas=_fija({3: 1.0}), contenido=_fija({3: 1.0}), colaborativo=_fija({3: 1.0})))
        self.assertEqual(r["modo"], "con_historia")
        self.assertAlmostEqual(_por_curso(r)[3]["puntuacion"], 1.0)

    def test_con_modelo_usa_las_cuatro(self):
        modelo = mock.Mock(side_effect=_fija({3: 1.0, 4: 1.0}))
        r = hibrido.recomendar(CON_HISTORIA, _contexto(modelo=MODELO), 8, _estrategias(
            reglas=_fija({3: 1.0}), contenido=_fija({3: 1.0}), colaborativo=_fija({3: 1.0}), modelo=modelo))
        self.assertEqual(r["modo"], "con_modelo")
        modelo.assert_called_once()
        items = _por_curso(r)
        self.assertAlmostEqual(items[3]["puntuacion"], 1.0)
        # 4: solo el modelo (0.3); el 0.2 del colaborativo se reparte entre reglas y contenido, que no puntúan.
        self.assertAlmostEqual(items[4]["puntuacion"], 0.3)


class EstrategiaQueFallaTests(_SinDiversidad):
    def test_se_ignora_y_las_demas_siguen(self):
        def rota(*args):
            raise RuntimeError("boom")
        with self.assertLogs("features.motor.hibrido", level="ERROR") as logs:
            r = hibrido.recomendar(NUEVO, _contexto(), 3, _estrategias(reglas=rota, contenido=_fija({1: 1.0})))
        self.assertEqual([i["curso_id"] for i in r["items"]], [1])
        self.assertAlmostEqual(r["items"][0]["puntuacion"], 0.4)
        self.assertTrue(any("reglas" in linea for linea in logs.output))


class NormalizarTests(SimpleTestCase):
    def test_con_puntuaciones_negativas(self):
        n = hibrido.normalizar([
            {"curso_id": 1, "puntuacion": 2.0, "razones": [{"origen": "regla:A", "texto": None, "aporte": 2.0}]},
            {"curso_id": 2, "puntuacion": -4.0, "razones": [{"origen": "regla:B", "texto": None, "aporte": -4.0}]},
        ])
        self.assertAlmostEqual(n[1]["norm"], 0.5)
        self.assertAlmostEqual(n[2]["norm"], -1.0)
        self.assertEqual(n[1]["razones"][0]["aporte"], 2.0)
        self.assertAlmostEqual(n[1]["razones"][0]["aporte_norm"], 0.5)

    def test_todo_cero(self):
        n = hibrido.normalizar([{"curso_id": 1, "puntuacion": 0.0, "razones": [{"origen": "c", "texto": None, "aporte": 0.0}]}])
        self.assertEqual(n[1]["norm"], 0.0)
        self.assertEqual(n[1]["razones"][0]["aporte_norm"], 0.0)
        self.assertEqual(hibrido.normalizar([]), {})

    def test_regla_negativa_hunde_el_curso(self):
        with mock.patch.object(config, "LAMBDA_DIVERSIDAD", 0.0):
            r = hibrido.recomendar(NUEVO, _contexto(), 8, _estrategias(
                reglas=_fija({1: 2.0, 2: -4.0}), contenido=_fija({1: 0.5, 2: 1.0})))
        items = _por_curso(r)
        self.assertAlmostEqual(items[1]["puntuacion"], round(0.6 * 0.5 + 0.4 * 0.5, 4))
        self.assertNotIn(2, items)  # 0.6 × −1 + 0.4 × 1 < 0


class RedistribucionTests(SimpleTestCase):
    PESOS = config.PESOS_ESTRATEGIA["con_modelo"]

    def test_reparte_el_peso_de_datos_que_falta(self):
        normalizadas = {"reglas": {1: {}}, "contenido": {1: {}}, "colaborativo": {}, "modelo": {1: {}}}
        p = hibrido.pesos_para(1, self.PESOS, normalizadas)
        self.assertEqual(p["colaborativo"], 0.0)
        self.assertAlmostEqual(p["reglas"], 0.3 + 0.2 * 0.6)
        self.assertAlmostEqual(p["contenido"], 0.2 + 0.2 * 0.4)
        self.assertAlmostEqual(p["modelo"], 0.3)
        self.assertAlmostEqual(sum(p.values()), 1.0)

    def test_sin_colaborativo_ni_modelo(self):
        p = hibrido.pesos_para(1, self.PESOS, {"reglas": {}, "contenido": {}, "colaborativo": {}, "modelo": {}})
        self.assertAlmostEqual(p["reglas"], 0.6)
        self.assertAlmostEqual(p["contenido"], 0.4)

    def test_en_recomendar(self):
        with mock.patch.object(config, "LAMBDA_DIVERSIDAD", 0.0):
            r = hibrido.recomendar(CON_HISTORIA, _contexto(), 8, _estrategias(
                reglas=_fija({3: 1.0, 4: 1.0}), colaborativo=_fija({3: 1.0})))
        items = _por_curso(r)
        self.assertAlmostEqual(items[3]["puntuacion"], 0.4 + 0.3)
        self.assertAlmostEqual(items[4]["puntuacion"], 0.4 + 0.3 * 0.4 / 0.7, places=4)

    def test_no_muta_los_pesos_de_config(self):
        antes = copy.deepcopy(config.PESOS_ESTRATEGIA)
        hibrido.pesos_para(1, config.PESOS_ESTRATEGIA["con_modelo"], {})
        self.assertEqual(config.PESOS_ESTRATEGIA, antes)


class AjusteYOrdenTests(_SinDiversidad):
    def test_bono_de_ruta(self):
        # Con PY-101 completado, PY-201 es el siguiente en la ruta (F01 de las reglas semilla).
        r = hibrido.recomendar(CON_HISTORIA, _contexto(REGLAS_SEMILLA), 8, _estrategias())
        self.assertEqual([i["curso_id"] for i in r["items"]], [2])
        self.assertAlmostEqual(r["items"][0]["puntuacion"], config.BONO_SIGUIENTE_EN_RUTA)
        self.assertEqual(r["items"][0]["explicacion"], explicaciones.TEXTO_SIGUIENTE)

    def test_totales_no_positivos_fuera(self):
        r = hibrido.recomendar(NUEVO, _contexto(), 8, _estrategias(reglas=_fija({1: -1.0, 2: 0.0, 4: 1.0})))
        self.assertEqual([i["curso_id"] for i in r["items"]], [4])

    def test_desempate_por_dificultad_y_luego_id(self):
        r = hibrido.recomendar(NUEVO, _contexto(), 8, _estrategias(reglas=_fija({5: 1.0, 4: 1.0, 3: 1.0, 2: 1.0})))
        self.assertEqual([i["curso_id"] for i in r["items"]], [2, 4, 3, 5])
        self.assertEqual([i["posicion"] for i in r["items"]], [1, 2, 3, 4])

    def test_limite_y_forma(self):
        r = hibrido.recomendar(NUEVO, _contexto(), 2, _estrategias(
            reglas=_fija({1: 3.0, 2: 2.0, 4: 1.0}, texto="Por la regla.", origen="regla:R01")))
        self.assertEqual(len(r["items"]), 2)
        self.assertEqual(set(r["items"][0]), {"curso_id", "codigo_curso", "titulo", "puntuacion",
                                              "posicion", "explicacion", "origen"})
        self.assertEqual(r["items"][0]["codigo_curso"], "PY-101")
        self.assertEqual(r["items"][0]["origen"], ["regla:R01"])

    def test_sin_candidatos(self):
        todo = _perfil(inscripciones=[_inscripcion(c, "completado", 95) for c in CATALOGO["cursos"]])
        self.assertEqual(hibrido.recomendar(todo, _contexto(), 3, _estrategias(reglas=_fija({1: 1.0})))["items"], [])

    def test_origen_ordenado_por_peso_por_aporte(self):
        def reglas(perfil, candidatos, contexto):
            return [{"curso_id": 1, "puntuacion": 1.0, "razones": [
                {"origen": "regla:R01", "texto": None, "aporte": 0.2},
                {"origen": "regla:R02", "texto": None, "aporte": 0.8},
                {"origen": "regla:R09", "texto": None, "aporte": -0.5},
            ]}]
        r = hibrido.recomendar(NUEVO, _contexto(), 1, _estrategias(
            reglas=reglas, contenido=_fija({1: 1.0}, origen="contenido")))
        self.assertEqual(r["items"][0]["origen"], ["regla:R02", "contenido", "regla:R01"])

    def test_pura(self):
        perfil, contexto = copy.deepcopy(NUEVO), _contexto(REGLAS_SEMILLA)
        antes = copy.deepcopy((perfil, contexto))
        hibrido.recomendar(perfil, contexto, 3)
        self.assertEqual((perfil, contexto), antes)


class ContinuarTests(SimpleTestCase):
    def test_activos_mas_recientes_primero_maximo_tres(self):
        perfil = _perfil(inscripciones=[
            _inscripcion(c, "activo", fecha=AHORA - timedelta(days=c)) for c in (2, 3, 4, 5)
        ] + [_inscripcion(1, "completado", 90), _inscripcion(6, "abandonado")])
        c = hibrido.continuar(perfil, CATALOGO)
        self.assertEqual([x["curso_id"] for x in c], [2, 3, 4])
        self.assertEqual(c[0], {"curso_id": 2, "codigo_curso": "PY-201", "titulo": "Estructuras de Control",
                                "porcentaje_avance_global": 40.0})


class MmrTests(SimpleTestCase):
    ITEMS = [{"curso_id": 1, "puntuacion": 1.0}, {"curso_id": 2, "puntuacion": 0.95},
             {"curso_id": 3, "puntuacion": 0.9}]

    @staticmethod
    def _sim(a, b):
        return 0.99 if {a, b} == {1, 2} else 0.0

    def test_lambda_cero_mantiene_el_orden(self):
        self.assertEqual([i["curso_id"] for i in diversidad.mmr(self.ITEMS, self._sim, 3, 0.0)], [1, 2, 3])

    def test_lambda_alto_baja_el_casi_duplicado(self):
        self.assertEqual([i["curso_id"] for i in diversidad.mmr(self.ITEMS, self._sim, 3, 0.5)], [1, 3, 2])

    def test_corta_en_n_y_empates_en_orden_original(self):
        iguales = [{"curso_id": c, "puntuacion": 1.0} for c in (7, 3, 5)]
        self.assertEqual([i["curso_id"] for i in diversidad.mmr(iguales, lambda a, b: 0.0, 2, 0.2)], [7, 3])
        self.assertEqual(diversidad.mmr([], self._sim, 3, 0.2), [])
        self.assertEqual(diversidad.mmr(self.ITEMS, self._sim, 0, 0.2), [])


class ElegirTests(SimpleTestCase):
    PESOS = {"reglas": 0.6, "contenido": 0.4}

    @staticmethod
    def _r(texto, aporte_norm, aporte=None):
        return {"origen": "x", "texto": texto, "aporte": aporte_norm if aporte is None else aporte,
                "aporte_norm": aporte_norm}

    def test_la_razon_visible_mas_fuerte(self):
        texto = explicaciones.elegir(
            {"reglas": [self._r("Regla débil.", 0.3)], "contenido": [self._r("Contenido fuerte.", 1.0)]},
            self.PESOS, False, NUEVO)
        self.assertEqual(texto, "Contenido fuerte.")  # 0.4 × 1.0 > 0.6 × 0.3

    def test_salta_textos_none_y_negativos(self):
        texto = explicaciones.elegir(
            {"reglas": [self._r(None, 1.0), self._r("Negativa.", -1.0)], "contenido": [self._r("Visible.", 0.1)]},
            self.PESOS, False, NUEVO)
        self.assertEqual(texto, "Visible.")

    def test_respaldos(self):
        solo_none = {"reglas": [self._r(None, 1.0)]}
        self.assertEqual(explicaciones.elegir(solo_none, self.PESOS, True, NUEVO), explicaciones.TEXTO_SIGUIENTE)
        self.assertEqual(explicaciones.elegir({}, self.PESOS, False, NUEVO), "Encaja con tu nivel Principiante.")
        self.assertEqual(explicaciones.elegir({}, {}, False, {}), "Encaja con tu nivel Principiante.")

    def test_nunca_vacio_y_con_punto(self):
        self.assertEqual(explicaciones.elegir({"reglas": [self._r("  ", 1.0)]}, self.PESOS, False, NUEVO),
                         "Encaja con tu nivel Principiante.")
        self.assertEqual(explicaciones.elegir({"reglas": [self._r("Sin punto", 1.0)]}, self.PESOS, False, NUEVO),
                         "Sin punto.")


class SiguienteEstadoTests(SimpleTestCase):
    TABLA = {
        "emitida":    {"mostrada": "mostrada", "clic": "clic", "descartada": "descartada", "inscripcion": "aceptada"},
        "mostrada":   {"mostrada": None, "clic": "clic", "descartada": "descartada", "inscripcion": "aceptada"},
        "clic":       {"mostrada": None, "clic": None, "descartada": "descartada", "inscripcion": "aceptada"},
        "descartada": {"mostrada": None, "clic": None, "descartada": None, "inscripcion": "aceptada"},
        "aceptada":   {"mostrada": None, "clic": None, "descartada": None, "inscripcion": None},
    }

    def test_tabla_completa(self):
        for actual, fila in self.TABLA.items():
            for accion, esperado in fila.items():
                with self.subTest(actual=actual, accion=accion):
                    self.assertEqual(registro.siguiente_estado(actual, accion), esperado)

    def test_desconocidos(self):
        self.assertIsNone(registro.siguiente_estado("rara", "clic"))
        self.assertIsNone(registro.siguiente_estado("emitida", "rara"))


class GrupoTests(SimpleTestCase):
    def test_determinista_y_ambos_grupos(self):
        self.assertEqual(experimento.grupo(USUARIO), experimento.grupo(USUARIO))
        grupos = [experimento.grupo(f"00000000-0000-0000-0000-{i:012d}") for i in range(1000)]
        self.assertEqual(set(grupos), {"motor", "control"})
        self.assertGreater(grupos.count("motor"), 400)
        self.assertGreater(grupos.count("control"), 400)

    def test_regla_del_hash(self):
        import hashlib
        primer = hashlib.sha256(f"{config.EXPERIMENTO}:{USUARIO}".encode()).digest()[0]
        self.assertEqual(experimento.grupo(USUARIO), "control" if primer % 2 == 0 else "motor")
        self.assertIn(experimento.grupo(USUARIO, "otro-exp"), {"motor", "control"})

    def test_experimento_apagado_todos_reciben_el_motor(self):
        with mock.patch.object(config, "EXPERIMENTO_ACTIVO", False):
            grupos = {experimento.grupo_asignado(f"00000000-0000-0000-0000-{i:012d}") for i in range(200)}
        self.assertEqual(grupos, {"motor"})

    def test_experimento_encendido_usa_el_grupo_del_hash(self):
        with mock.patch.object(config, "EXPERIMENTO_ACTIVO", True):
            self.assertEqual(experimento.grupo_asignado(USUARIO), experimento.grupo(USUARIO))


class ControlTests(SimpleTestCase):
    def test_orden_del_temario(self):
        r = experimento.recomendar_control(NUEVO, _contexto(), 4)
        self.assertEqual(r["modo"], "control")
        self.assertEqual([i["curso_id"] for i in r["items"]], [1, 2, 4, 3])
        self.assertEqual({i["explicacion"] for i in r["items"]}, {experimento.TEXTO_CONTROL})
        self.assertEqual(r["items"][0]["origen"], ["control:temario"])
        self.assertEqual([i["posicion"] for i in r["items"]], [1, 2, 3, 4])

    def test_mismos_filtros(self):
        r = experimento.recomendar_control(NUEVO, _contexto(REGLAS_SEMILLA), 8)
        self.assertEqual([i["curso_id"] for i in r["items"]], [1])


# --- Registro ----------------------------------------------------------------


class RegistroTests(SimpleTestCase):
    def test_nuevo_id(self):
        rid = registro.nuevo_id()
        self.assertTrue(re.match(r"^r-[0-9a-f-]{36}\Z", rid))
        self.assertTrue(es_recomendacion_id(rid))
        self.assertNotEqual(rid, registro.nuevo_id())

    def test_snapshot_sin_datos_personales_y_serializable(self):
        perfil = {**CON_HISTORIA, "nombre": "Ana", "email": "ana@example.com",
                  "modulos_en_refuerzo": {3: [5]}}
        foto = registro.snapshot(perfil)
        self.assertEqual(set(foto), {"nivel", "nivel_asignado", "intereses", "dominio", "evidencias",
                                     "cursos_completados", "calificacion_por_curso", "modulos_en_refuerzo",
                                     "dias_inactivo", "calculado_en"})
        self.assertEqual(foto["calificacion_por_curso"], {"1": 90.0})
        self.assertEqual(foto["modulos_en_refuerzo"], {"3": [5]})
        self.assertEqual(foto["calculado_en"], AHORA.isoformat())
        json.dumps(foto)

    def test_registrar_una_sola_insercion(self):
        items = [{"recomendacion_id": f"r-{i:036d}", "curso_id": i, "puntuacion": 0.5, "posicion": i,
                  "explicacion": "E.", "origen": ["contenido"]} for i in (1, 2)]
        with mock.patch("core.supabase.insert") as insert:
            registro.registrar(USUARIO, items, "hibrido-v1", "motor", NUEVO)
        insert.assert_called_once()
        tabla, filas = insert.call_args.args
        self.assertEqual(tabla, "recomendaciones")
        self.assertEqual([f["id"] for f in filas], [items[0]["recomendacion_id"], items[1]["recomendacion_id"]])
        self.assertEqual(filas[0]["estado"], "emitida")
        self.assertEqual(filas[0]["usuario_id"], USUARIO)
        self.assertEqual((filas[0]["motor"], filas[0]["grupo"]), ("hibrido-v1", "motor"))
        self.assertIn("perfil_snapshot", filas[0])

    def test_registrar_sin_items_no_inserta(self):
        with mock.patch("core.supabase.insert") as insert:
            registro.registrar(USUARIO, [], "hibrido-v1", "motor", NUEVO)
        insert.assert_not_called()

    def test_marcar_aceptada(self):
        rid = registro.nuevo_id()
        for estado, actualiza in [("clic", True), ("descartada", True), ("aceptada", False)]:
            with self.subTest(estado=estado), \
                    mock.patch("core.supabase.select_one", return_value={"id": rid, "estado": estado}) as leer, \
                    mock.patch("core.supabase.update") as update:
                registro.marcar_aceptada(rid, USUARIO)
                self.assertIn(("usuario_id", f"eq.{USUARIO}"), leer.call_args.kwargs["filters"])
                self.assertEqual(update.called, actualiza)
                if actualiza:
                    self.assertEqual(update.call_args.args[1], {"estado": "aceptada"})
                    self.assertIn(("usuario_id", f"eq.{USUARIO}"), update.call_args.kwargs["filters"])

    def test_marcar_aceptada_id_ajeno_o_desconocido(self):
        with mock.patch("core.supabase.select_one", return_value=None), \
                mock.patch("core.supabase.update") as update:
            registro.marcar_aceptada(registro.nuevo_id(), USUARIO)
        update.assert_not_called()

    def test_ultima_tanda(self):
        filas = [
            {"id": "a", "posicion": 2, "creada_en": "2026-11-20T11:50:00+00:00"},
            {"id": "b", "posicion": 1, "creada_en": "2026-11-20T11:50:00+00:00"},
            {"id": "c", "posicion": 1, "creada_en": "2026-11-20T11:40:00+00:00"},
        ]
        self.assertEqual([f["id"] for f in registro.ultima_tanda(filas)], ["b", "a"])
        self.assertEqual(registro.ultima_tanda([]), [])


# --- Orquestación con todo simulado -------------------------------------------


def _fila(curso_id, posicion, creada="2026-11-20T11:50:00+00:00", grupo="motor"):
    return {"id": f"r-{curso_id:036d}", "usuario_id": USUARIO, "curso_id": curso_id, "puntuacion": 0.5,
            "posicion": posicion, "motor": "hibrido-v1", "grupo": grupo, "origen": ["contenido"],
            "explicacion": "Guardada.", "estado": "emitida", "creada_en": creada}


class RecomendarCursosTests(SimpleTestCase):
    def setUp(self):
        self.perfil = _perfil(areas=["datos"])
        parches = {
            "ahora": mock.patch.object(hibrido, "_ahora", return_value=AHORA),
            "grupo": mock.patch.object(experimento, "grupo_asignado", return_value="motor"),
            "perfil": mock.patch.object(hibrido, "obtener_perfil", side_effect=lambda u: self.perfil),
            "catalogo": mock.patch.object(hibrido, "cargar_catalogo", return_value=CATALOGO),
            "reglas": mock.patch.object(hibrido.reglas, "cargar_reglas", return_value=SIN_FILTROS),
            "similitudes": mock.patch.object(hibrido.colaborativo, "cargar_similitudes", return_value={}),
            "modelo": mock.patch.object(hibrido.modelo, "cargar_activo", return_value=None),
            "recientes": mock.patch.object(registro, "recientes", return_value=[]),
            "eventos": mock.patch.object(registro, "hay_eventos_desde", return_value=False),
            "registrar": mock.patch.object(registro, "registrar"),
        }
        self.m = {nombre: p.start() for nombre, p in parches.items()}
        for p in parches.values():
            self.addCleanup(p.stop)

    def test_calcula_registra_y_responde(self):
        r = hibrido.recomendar_cursos(USUARIO, 3)
        self.assertEqual(set(r), {"success", "usuario_id", "generado_en", "motor", "grupo",
                                  "recomendaciones", "continuar"})
        self.assertEqual((r["success"], r["motor"], r["grupo"]), (True, "hibrido-v1", "motor"))
        self.assertEqual(r["generado_en"], "2026-11-20T12:00:00Z")
        self.assertEqual(len(r["recomendaciones"]), 3)
        self.assertTrue(all(es_recomendacion_id(i["recomendacion_id"]) for i in r["recomendaciones"]))
        self.m["registrar"].assert_called_once()
        args = self.m["registrar"].call_args.args
        self.assertEqual((args[0], args[2], args[3]), (USUARIO, "hibrido-v1", "motor"))
        self.assertEqual(args[1], r["recomendaciones"])
        desde = self.m["recientes"].call_args.args[1]
        self.assertEqual(desde, AHORA - timedelta(minutes=config.MINUTOS_ESTABILIDAD))

    def test_grupo_control(self):
        self.m["grupo"].return_value = "control"
        r = hibrido.recomendar_cursos(USUARIO, 2)
        self.assertEqual((r["motor"], r["grupo"]), ("control-temario", "control"))
        self.assertEqual([i["curso_id"] for i in r["recomendaciones"]], [1, 2])
        self.assertEqual(self.m["registrar"].call_args.args[2:4], ("control-temario", "control"))

    def test_acota_el_limite(self):
        self.m["grupo"].return_value = "control"  # el temario tiene los 8 cursos
        self.assertEqual(len(hibrido.recomendar_cursos(USUARIO, 50)["recomendaciones"]), config.LIMITE_MAXIMO)
        self.assertEqual(len(hibrido.recomendar_cursos(USUARIO, 0)["recomendaciones"]), 1)
        self.assertEqual(len(hibrido.recomendar_cursos(USUARIO, None)["recomendaciones"]),
                         config.LIMITE_POR_DEFECTO)

    def test_ventana_de_estabilidad_reutiliza_sin_registrar(self):
        self.perfil = _perfil(areas=["datos"], inscripciones=[_inscripcion(4, "activo")])
        self.m["recientes"].return_value = [_fila(5, 1), _fila(4, 2), _fila(6, 3),
                                            _fila(8, 1, creada="2026-11-20T11:40:00+00:00")]
        r = hibrido.recomendar_cursos(USUARIO, 3)
        self.m["registrar"].assert_not_called()
        self.assertEqual([i["curso_id"] for i in r["recomendaciones"]], [5, 6])  # 4 ya está inscrito
        self.assertEqual(r["recomendaciones"][0]["recomendacion_id"], _fila(5, 1)["id"])
        self.assertEqual(r["recomendaciones"][0]["explicacion"], "Guardada.")
        self.assertEqual(r["generado_en"], "2026-11-20T11:50:00Z")
        self.assertEqual([c["curso_id"] for c in r["continuar"]], [4])
        self.assertEqual(self.m["eventos"].call_args.args[2], "2026-11-20T11:50:00+00:00")
        self.assertEqual(set(self.m["eventos"].call_args.args[1]), set(hibrido.EVENTOS_RELEVANTES))

    def test_evento_posterior_obliga_a_recalcular(self):
        self.m["recientes"].return_value = [_fila(5, 1), _fila(4, 2), _fila(6, 3)]
        self.m["eventos"].return_value = True
        r = hibrido.recomendar_cursos(USUARIO, 3)
        self.m["registrar"].assert_called_once()
        self.assertNotEqual(r["recomendaciones"][0]["recomendacion_id"], _fila(5, 1)["id"])

    def test_tanda_mas_corta_que_el_limite_recalcula(self):
        self.m["recientes"].return_value = [_fila(5, 1), _fila(4, 2), _fila(6, 3)]
        r = hibrido.recomendar_cursos(USUARIO, 8)
        self.m["registrar"].assert_called_once()
        self.assertGreater(len(r["recomendaciones"]), 3)
        self.assertNotIn(_fila(5, 1)["id"], [i["recomendacion_id"] for i in r["recomendaciones"]])

    def test_tanda_corta_igual_a_la_nueva_no_se_registra_otra_vez(self):
        nueva = hibrido.recomendar(self.perfil, _contexto(SIN_FILTROS), 8)["items"]
        self.m["recientes"].return_value = [_fila(i["curso_id"], i["posicion"]) for i in nueva[:5]]
        with mock.patch.object(hibrido, "recomendar", return_value={"modo": "nuevo", "items": nueva[:5],
                                                                      "continuar": []}):
            r = hibrido.recomendar_cursos(USUARIO, 8)
        self.m["registrar"].assert_not_called()
        self.assertEqual(r["recomendaciones"][0]["recomendacion_id"], _fila(nueva[0]["curso_id"], 1)["id"])

    def test_tanda_de_otro_grupo_no_vale(self):
        self.m["recientes"].return_value = [_fila(5, 1, grupo="control"), _fila(4, 2, grupo="control"),
                                            _fila(6, 3, grupo="control")]
        hibrido.recomendar_cursos(USUARIO, 3)
        self.m["registrar"].assert_called_once()

    def test_fallo_al_leer_la_ventana_recalcula(self):
        self.m["recientes"].side_effect = RuntimeError("sin tabla")
        with self.assertLogs("features.motor.hibrido", level="ERROR"):
            r = hibrido.recomendar_cursos(USUARIO, 3)
        self.assertEqual(len(r["recomendaciones"]), 3)

    def test_fallo_al_registrar_devuelve_igualmente(self):
        self.m["registrar"].side_effect = RuntimeError("caído")
        with self.assertLogs("features.motor.hibrido", level="ERROR"):
            r = hibrido.recomendar_cursos(USUARIO, 3)
        self.assertEqual(len(r["recomendaciones"]), 3)
        self.assertTrue(all(i["explicacion"] for i in r["recomendaciones"]))


# --- Vistas ------------------------------------------------------------------


def _verificar_falso(token):
    return {"id": USUARIO}


class _VistasBase(SimpleTestCase):
    def setUp(self):
        parche = mock.patch("core.auth._verify_token", side_effect=_verificar_falso)
        parche.start()
        self.addCleanup(parche.stop)

    def _get(self, ruta, token="t"):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return Client().get(ruta, **extra)

    def _post(self, cuerpo, token="t"):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return Client().post("/api/retroalimentacion", data=json.dumps(cuerpo),
                             content_type="application/json", **extra)


class VistaRecomendacionesTests(_VistasBase):
    def test_sin_usuario_id_400(self):
        self.assertEqual(self._get("/api/recomendaciones/cursos").status_code, 400)

    def test_otro_usuario_403(self):
        with mock.patch.object(hibrido, "recomendar_cursos") as rc:
            self.assertEqual(self._get(f"/api/recomendaciones/cursos?usuario_id={OTRO}").status_code, 403)
        rc.assert_not_called()

    def test_sin_token_401(self):
        self.assertEqual(self._get(f"/api/recomendaciones/cursos?usuario_id={USUARIO}", token=None).status_code, 401)

    def test_limite_no_entero_400(self):
        for limite in ("abc", "2.5", "1e3"):
            with self.subTest(limite=limite):
                r = self._get(f"/api/recomendaciones/cursos?usuario_id={USUARIO}&limite={limite}")
                self.assertEqual(r.status_code, 400)

    def test_exito(self):
        respuesta = {"success": True, "recomendaciones": []}
        with mock.patch.object(hibrido, "recomendar_cursos", return_value=respuesta) as rc:
            r = self._get(f"/api/recomendaciones/cursos?usuario_id={USUARIO}&limite=5")
            sin_limite = self._get(f"/api/recomendaciones/cursos?usuario_id={USUARIO}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), respuesta)
        self.assertEqual(rc.call_args_list[0].args, (USUARIO, 5))
        self.assertEqual(rc.call_args_list[1].args, (USUARIO, None))
        self.assertEqual(sin_limite.status_code, 200)


class VistaRetroalimentacionTests(_VistasBase):
    RID = "r-5c1e0000-0000-4000-8000-000000000001"

    def setUp(self):
        super().setUp()
        parches = {
            "de_usuario": mock.patch.object(registro, "de_usuario",
                                            return_value={"id": self.RID, "posicion": 2, "estado": "emitida"}),
            "cambiar": mock.patch.object(registro, "cambiar_estado"),
            "evento": mock.patch("features.motor.eventos.service.registrar_servidor"),
        }
        self.m = {n: p.start() for n, p in parches.items()}
        for p in parches.values():
            self.addCleanup(p.stop)

    def test_sin_token_401(self):
        self.assertEqual(self._post({"recomendacion_id": self.RID, "accion": "clic"}, token=None).status_code, 401)

    def test_de_otro_usuario_o_inexistente_404(self):
        self.m["de_usuario"].return_value = None
        r = self._post({"recomendacion_id": self.RID, "accion": "clic"})
        self.assertEqual(r.status_code, 404)
        self.m["de_usuario"].assert_called_once_with(self.RID, USUARIO)
        self.m["cambiar"].assert_not_called()
        self.m["evento"].assert_not_called()

    def test_cuerpo_invalido_400(self):
        for cuerpo in [
            {"recomendacion_id": self.RID, "accion": "aceptada"},
            {"recomendacion_id": self.RID},
            {"recomendacion_id": "r-corto", "accion": "clic"},
            {"recomendacion_id": self.RID, "accion": "descartada", "motivo": "porque"},
            {"recomendacion_id": self.RID, "accion": "clic", "motivo": "otro"},
        ]:
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(self._post(cuerpo).status_code, 400)
        self.m["evento"].assert_not_called()

    def test_exito_204_y_un_evento(self):
        r = self._post({"recomendacion_id": self.RID, "accion": "descartada", "motivo": "no_es_mi_nivel"})
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.content, b"")
        self.m["cambiar"].assert_called_once_with(self.RID, USUARIO, "descartada", "no_es_mi_nivel")
        self.m["evento"].assert_called_once_with(
            USUARIO, "recomendacion_descartada",
            datos={"recomendacion_id": self.RID, "posicion": 2, "motivo": "no_es_mi_nivel"})

    def test_sin_cambio_de_estado_registra_igualmente(self):
        self.m["de_usuario"].return_value = {"id": self.RID, "posicion": 1, "estado": "aceptada"}
        r = self._post({"recomendacion_id": self.RID, "accion": "mostrada"})
        self.assertEqual(r.status_code, 204)
        self.m["cambiar"].assert_not_called()
        self.m["evento"].assert_called_once_with(
            USUARIO, "recomendacion_mostrada", datos={"recomendacion_id": self.RID, "posicion": 1})

    def test_el_evento_pasa_la_validacion_de_03(self):
        from features.motor.eventos.validacion import validar_evento
        self.m["evento"].side_effect = lambda u, tipo, **campos: validar_evento(
            {**campos, "usuario_id": u, "tipo": tipo}, u, "servidor")
        self.assertEqual(self._post({"recomendacion_id": self.RID, "accion": "clic"}).status_code, 204)


# --- De punta a punta con las estrategias reales (05/06/07) -------------------


class EstrategiasRealesTests(SimpleTestCase):
    def test_alumno_nuevo_de_datos_empieza_por_py101(self):
        perfil = _perfil(areas=["datos"])
        r = hibrido.recomendar(perfil, _contexto(REGLAS_SEMILLA), 3)
        self.assertEqual(r["modo"], "nuevo")
        self.assertTrue(r["items"])
        primero = r["items"][0]
        self.assertEqual(primero["codigo_curso"], "PY-101")
        self.assertEqual(primero["posicion"], 1)
        self.assertTrue(primero["explicacion"].endswith("."))
        self.assertTrue(primero["origen"])
        self.assertTrue(all(o.startswith(("regla:", "contenido", "colaborativo", "modelo:"))
                            for o in primero["origen"]))
        self.assertGreater(primero["puntuacion"], 0)

    def test_con_historia_modelo_y_similitudes_reales(self):
        perfil = _perfil(areas=["datos"], inscripciones=[_inscripcion(1, "completado", 92),
                                                          _inscripcion(2, "completado", 88)])
        arbol = {"hoja": False, "campo": "dominio_conceptos_curso", "umbral": 0.5,
                 "izq": {"hoja": True, "prob": 0.4, "n": 30}, "der": {"hoja": True, "prob": 0.9, "n": 30}}
        modelo = {"nombre": "aprobacion", "version": "20261120-0300",
                  "caracteristicas": ["dominio_conceptos_curso"], "arbol": arbol}
        similitudes = {4: {1: {"similitud": 0.9, "soporte": 12}, 2: {"similitud": 0.8, "soporte": 12}},
                       1: {4: {"similitud": 0.9, "soporte": 12}}, 2: {4: {"similitud": 0.8, "soporte": 12}}}
        with mock.patch.object(hibrido.logger, "exception") as fallo:
            r = hibrido.recomendar(perfil, _contexto(REGLAS_SEMILLA, modelo, similitudes), 3)
        fallo.assert_not_called()
        self.assertEqual(r["modo"], "con_modelo")
        self.assertEqual(r["items"][0]["codigo_curso"], "PY-401")
        self.assertTrue(r["items"][0]["explicacion"])
