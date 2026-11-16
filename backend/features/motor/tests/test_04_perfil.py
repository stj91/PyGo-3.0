"""Tests del paquete 04: dominio, constructor del perfil, servicio, batch y vistas. Sin red."""

import copy
import json
import logging
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import Client, SimpleTestCase

from core.errors import NotFoundError
from features.motor import catalogo as catalogo_mod
from features.motor import config
from features.motor.perfil import repository, service
from features.motor.perfil.construir import construir_perfil
from features.motor.perfil.dominio import (
    aplicar_diagnostico,
    aplicar_tema,
    dominio_inicial,
    nuevo_dominio,
    reproducir_dominio,
)
from features.motor.perfil.publico import perfil_publico
from features.motor.perfil.recalculo import (
    cursos_abandonados,
    intereses_inferidos,
    ultima_actividad_por_curso,
)

USUARIO = "11111111-1111-1111-1111-111111111111"
OTRO = "22222222-2222-2222-2222-222222222222"
AHORA = datetime(2026, 11, 20, 16, 20, tzinfo=timezone.utc)


def _catalogo():
    """Dos cursos: 1 (Principiante; temas 10 y 11) y 2 (Intermedio; tema 20)."""
    return catalogo_mod.ensamblar_catalogo(
        cursos=[
            {"id": 1, "codigo_curso": "PY-101", "titulo": "Fundamentos", "descripcion": "",
             "dificultad": 1, "nivel": "Principiante", "publicado": True},
            {"id": 2, "codigo_curso": "PY-201", "titulo": "Control", "descripcion": "",
             "dificultad": 2, "nivel": "Intermedio", "publicado": True},
        ],
        temas=[
            {"id": 10, "curso_id": 1, "orden": 1, "titulo": "Variables"},
            {"id": 11, "curso_id": 1, "orden": 2, "titulo": "Colecciones"},
            {"id": 20, "curso_id": 2, "orden": 1, "titulo": "If"},
        ],
        conceptos=[
            {"id": 1, "clave": "fundamentos", "nombre": "Fundamentos", "padre_id": None},
            {"id": 2, "clave": "datos", "nombre": "Datos", "padre_id": None},
            {"id": 3, "clave": "variables", "nombre": "Variables", "padre_id": 1},
            {"id": 4, "clave": "colecciones", "nombre": "Colecciones", "padre_id": 1},
            {"id": 5, "clave": "condicionales", "nombre": "Condicionales", "padre_id": 1},
            {"id": 6, "clave": "pandas", "nombre": "Pandas", "padre_id": 2},
        ],
        contenido=[
            {"objeto_tipo": "curso", "objeto_id": 1, "concepto_clave": "variables", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 10, "concepto_clave": "variables", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 11, "concepto_clave": "colecciones", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 11, "concepto_clave": "variables", "peso": 0.5},
            {"objeto_tipo": "curso", "objeto_id": 2, "concepto_clave": "condicionales", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 20, "concepto_clave": "condicionales", "peso": 1.0},
        ],
        prerrequisitos=[],
        carrera_areas=[{"carrera_clave": "LMAT", "area_clave": "datos", "peso": 0.6},
                       {"carrera_clave": "LMAT", "area_clave": "fundamentos", "peso": 0.3}],
        ejercicios_diagnostico=[{"id": 101, "tema_id": 10}, {"id": 102, "tema_id": 10},
                                {"id": 103, "tema_id": 20}],
    )


def _entrada(**cambios):
    base = {
        "usuario": {"id": USUARIO, "nivel_asignado": "Intermedio", "carrera_clave": None},
        "inscripciones": [],
        "estados_temas": [],
        "intentos": [],
        "dominio": {},
        "evidencias": {},
        "intereses": [],
        "ultimo_evento": None,
    }
    return {**base, **cambios}


# --- Dominio ----------------------------------------------------------------


class NuevoDominioTests(SimpleTestCase):
    def test_primer_valor_usa_inicial(self):
        self.assertEqual(nuevo_dominio(None, 1.0, 0.5), 0.65)

    def test_usa_el_anterior(self):
        self.assertEqual(nuevo_dominio(0.2, 1.0, 0.9), 0.44)

    def test_peso_cero_no_cambia(self):
        self.assertEqual(nuevo_dominio(0.42, 1.0, 0.2, peso=0.0), 0.42)

    def test_acota(self):
        self.assertEqual(nuevo_dominio(0.9, 5.0, 0.2), 1.0)
        self.assertEqual(nuevo_dominio(0.1, -5.0, 0.2), 0.0)

    def test_redondea_a_tres_decimales(self):
        self.assertEqual(nuevo_dominio(1 / 3, 0.0, 0.2), 0.233)


class DominioInicialTests(SimpleTestCase):
    def test_concepto_en_curso_de_nivel_igual_o_inferior(self):
        cat = _catalogo()
        self.assertEqual(dominio_inicial("variables", "Intermedio", cat), 0.5)
        self.assertEqual(dominio_inicial("condicionales", "Intermedio", cat), 0.5)

    def test_concepto_solo_en_cursos_superiores(self):
        self.assertEqual(dominio_inicial("condicionales", "Principiante", _catalogo()),
                         config.DOMINIO_SIN_EVIDENCIA)

    def test_concepto_sin_cursos(self):
        self.assertEqual(dominio_inicial("pandas", "Avanzado", _catalogo()), config.DOMINIO_SIN_EVIDENCIA)


class AplicarTemaTests(SimpleTestCase):
    def test_usa_el_peso_de_cada_concepto_y_suma_evidencia(self):
        cat = _catalogo()
        dominio, evidencias = aplicar_tema({"variables": 0.5}, {"variables": 2}, 11, 1.0, "Intermedio", cat)
        self.assertEqual(dominio, {"variables": nuevo_dominio(0.5, 1.0, 0.5, 0.5),
                                   "colecciones": nuevo_dominio(None, 1.0, 0.5, 1.0)})
        self.assertEqual(evidencias, {"variables": 3, "colecciones": 1})

    def test_tema_desconocido_no_cambia_nada(self):
        self.assertEqual(aplicar_tema({"a": 0.3}, {"a": 1}, 999, 1.0, "Intermedio", _catalogo()),
                         ({"a": 0.3}, {"a": 1}))


class AplicarDiagnosticoTests(SimpleTestCase):
    def test_una_pregunta_acertada(self):
        dominio, evidencias = aplicar_diagnostico({}, {}, {103: True}, "Intermedio", _catalogo())
        self.assertEqual(dominio, {"condicionales": 0.7})
        self.assertEqual(evidencias, {"condicionales": 1})

    def test_dos_preguntas_del_mismo_modulo_una_acertada(self):
        dominio, evidencias = aplicar_diagnostico({}, {}, {101: True, 102: False}, "Intermedio", _catalogo())
        self.assertEqual(dominio, {"variables": 0.45})
        self.assertEqual(evidencias, {"variables": 1})

    def test_concepto_con_valor_previo(self):
        dominio, evidencias = aplicar_diagnostico(
            {"variables": 0.8}, {"variables": 3}, {101: False}, "Intermedio", _catalogo())
        self.assertEqual(dominio, {"variables": nuevo_dominio(0.8, 0.0, 0.5)})
        self.assertEqual(evidencias, {"variables": 4})

    def test_ejercicio_desconocido_y_claves_texto(self):
        dominio, _ = aplicar_diagnostico({}, {}, {"103": False, 999: True}, "Intermedio", _catalogo())
        self.assertEqual(dominio, {"condicionales": 0.2})


class ReproducirDominioTests(SimpleTestCase):
    T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)

    def _eventos(self):
        return [
            {"tipo": "diagnostico", "fecha": self.T0, "datos": {"resultados": {"101": True, "103": False}}},
            {"tipo": "quiz_intento", "fecha": self.T0 + timedelta(days=1), "objeto_id": 10, "valor": 0.9},
            {"tipo": "sesion_inicio", "fecha": self.T0 + timedelta(days=1)},
            {"tipo": "quiz_intento", "fecha": self.T0 + timedelta(days=2), "objeto_id": 11, "valor": 0.4},
        ]

    def test_igual_a_aplicar_uno_a_uno(self):
        cat = _catalogo()
        d, e = aplicar_diagnostico({}, {}, {101: True, 103: False}, "Intermedio", cat)
        d, e = aplicar_tema(d, e, 10, 0.9, "Intermedio", cat)
        d, e = aplicar_tema(d, e, 11, 0.4, "Intermedio", cat)
        self.assertEqual(reproducir_dominio(self._eventos(), cat, "Intermedio", None), (d, e))

    def test_hasta_corta_los_posteriores(self):
        cat = _catalogo()
        d, e = aplicar_diagnostico({}, {}, {101: True, 103: False}, "Intermedio", cat)
        d, e = aplicar_tema(d, e, 10, 0.9, "Intermedio", cat)
        hasta = self.T0 + timedelta(days=2)  # el evento con fecha == hasta queda fuera
        self.assertEqual(reproducir_dominio(self._eventos(), cat, "Intermedio", hasta), (d, e))

    def test_ordena_la_entrada(self):
        cat = _catalogo()
        eventos = self._eventos()
        desordenados = [eventos[3], eventos[1], eventos[0], eventos[2]]
        self.assertEqual(reproducir_dominio(desordenados, cat, "Intermedio", None),
                         reproducir_dominio(eventos, cat, "Intermedio", None))

    def test_fechas_iso_en_texto(self):
        cat = _catalogo()
        eventos = [{**e, "fecha": e["fecha"].isoformat().replace("+00:00", "Z")} for e in self._eventos()]
        self.assertEqual(reproducir_dominio(eventos, cat, "Intermedio", None),
                         reproducir_dominio(self._eventos(), cat, "Intermedio", None))

    def test_no_muta_los_eventos(self):
        eventos = self._eventos()
        antes = copy.deepcopy(eventos)
        reproducir_dominio(eventos, _catalogo(), "Intermedio", None)
        self.assertEqual(eventos, antes)


# --- Constructor ------------------------------------------------------------


def _intento(tema_id, nota, minutos, tipo="ejercicio_practico"):
    return {"ejercicio_id": 1, "tema_id": tema_id, "tipo": tipo, "calificacion_obtenida": nota,
            "fecha_intento": AHORA - timedelta(days=3) + timedelta(minutes=minutos)}


class ConstruirPerfilTests(SimpleTestCase):
    def test_intereses_por_area_y_carrera_combinados_por_maximo(self):
        entrada = _entrada(
            usuario={"id": USUARIO, "nivel_asignado": "Principiante", "carrera_clave": "LMAT"},
            intereses=[
                {"concepto_clave": "fundamentos", "origen": "declarado", "peso": 1.0},
                {"concepto_clave": "pandas", "origen": "inferido", "peso": 0.2},
                {"concepto_clave": "variables", "origen": "inferido", "peso": 0.0},  # retirado
                {"concepto_clave": "desconocido", "origen": "declarado", "peso": 1.0},
            ],
        )
        perfil = construir_perfil(entrada, _catalogo(), AHORA)
        self.assertEqual(perfil["intereses"], {
            "variables": 1.0, "colecciones": 1.0, "condicionales": 1.0, "pandas": 0.6,
        })

    def test_nivel_efectivo_cambia_con_cinco_evidencias(self):
        cat = _catalogo()
        cuatro = construir_perfil(_entrada(dominio={"variables": 0.9}, evidencias={"variables": 4}), cat, AHORA)
        self.assertEqual(cuatro["nivel_inferido"], "Avanzado")
        self.assertEqual(cuatro["nivel"], "Intermedio")
        cinco = construir_perfil(
            _entrada(dominio={"variables": 0.9, "colecciones": 0.1}, evidencias={"variables": 4, "colecciones": 1}),
            cat, AHORA)
        self.assertEqual(cinco["nivel_inferido"], "Intermedio")  # media 0.5
        self.assertEqual(cinco["nivel"], "Intermedio")
        bajo = construir_perfil(
            _entrada(dominio={"variables": 0.3}, evidencias={"variables": 5}), cat, AHORA)
        self.assertEqual(bajo["nivel"], "Principiante")

    def test_sin_evidencias_no_hay_nivel_inferido(self):
        perfil = construir_perfil(_entrada(), _catalogo(), AHORA)
        self.assertIsNone(perfil["nivel_inferido"])
        self.assertEqual(perfil["nivel"], "Intermedio")
        self.assertIsNone(perfil["tasa_aprobacion_modulos"])
        self.assertIsNone(perfil["intentos_promedio"])
        self.assertIsNone(perfil["dias_inactivo"])
        self.assertEqual(perfil["calculado_en"], AHORA)

    def test_inscripciones_duplicadas_y_completados(self):
        entrada = _entrada(inscripciones=[
            {"curso_id": 1, "estado": "activo", "porcentaje_avance_global": 20, "calificacion_final": None,
             "fecha_inscripcion": "2026-10-01T00:00:00+00:00", "completado_en": None, "origen": None},
            {"curso_id": 1, "estado": "completado", "porcentaje_avance_global": "100.00",
             "calificacion_final": "91.50", "fecha_inscripcion": "2026-10-01T00:00:00Z",
             "completado_en": "2026-11-10T10:00:00.12345Z", "origen": None},
            {"curso_id": 2, "estado": "completado", "porcentaje_avance_global": 100, "calificacion_final": 85,
             "fecha_inscripcion": "2026-10-01T00:00:00Z", "completado_en": "2026-11-01T10:00:00Z",
             "origen": "recomendacion"},
        ])
        perfil = construir_perfil(entrada, _catalogo(), AHORA)
        self.assertEqual(perfil["inscripciones"][1]["estado"], "completado")
        self.assertEqual(perfil["inscripciones"][1]["porcentaje_avance_global"], 100.0)
        self.assertEqual(perfil["cursos_completados"], [2, 1])
        self.assertEqual(perfil["calificacion_por_curso"], {2: 85.0, 1: 91.5})

    def test_modulos_en_refuerzo_con_estados_duplicados(self):
        entrada = _entrada(estados_temas=[
            {"tema_id": 10, "estado": "actividades_de_refuerzo"},
            {"tema_id": 10, "estado": "completado"},
            {"tema_id": 11, "estado": "desbloqueado"},
            {"tema_id": 11, "estado": "actividades_de_refuerzo"},
            {"tema_id": 20, "estado": "actividades_de_refuerzo"},
            {"tema_id": 999, "estado": "actividades_de_refuerzo"},
        ])
        self.assertEqual(construir_perfil(entrada, _catalogo(), AHORA)["modulos_en_refuerzo"],
                         {1: [11], 2: [20]})

    def test_tasa_e_intentos_con_ventana_de_diez_minutos(self):
        entrada = _entrada(intentos=[
            # tema 10: envío 1 (min 0 y 5, media 50) suspende; envío 2 (min 30) aprueba.
            _intento(10, 40, 0), _intento(10, 60, 5), _intento(10, 100, 30),
            # tema 11: un único envío suspendido.
            _intento(11, 50, 0),
            # el diagnóstico no cuenta.
            _intento(20, 100, 0, tipo="evaluacion_tecnica"),
        ])
        perfil = construir_perfil(entrada, _catalogo(), AHORA)
        self.assertEqual(perfil["tasa_aprobacion_modulos"], round(1 / 3, 3))
        self.assertEqual(perfil["intentos_promedio"], 1.5)

    def test_dias_inactivo_usa_lo_mas_reciente(self):
        cat = _catalogo()
        entrada = _entrada(ultimo_evento=AHORA - timedelta(days=10, hours=5),
                           intentos=[_intento(10, 90, 0)])
        self.assertEqual(construir_perfil(entrada, cat, AHORA)["dias_inactivo"], 3)
        solo_evento = _entrada(ultimo_evento="2026-11-10T16:20:00Z")
        self.assertEqual(construir_perfil(solo_evento, cat, AHORA)["dias_inactivo"], 10)

    def test_no_muta_la_entrada(self):
        entrada = _entrada(
            dominio={"variables": 0.5}, evidencias={"variables": 2},
            inscripciones=[{"curso_id": 1, "estado": "activo", "porcentaje_avance_global": 10,
                            "calificacion_final": None, "fecha_inscripcion": AHORA, "completado_en": None,
                            "origen": None}],
            estados_temas=[{"tema_id": 10, "estado": "actividades_de_refuerzo"}],
            intentos=[_intento(10, 90, 0)],
            intereses=[{"concepto_clave": "datos", "origen": "declarado", "peso": 1}],
        )
        cat = _catalogo()
        antes, cat_antes = copy.deepcopy(entrada), copy.deepcopy(cat)
        perfil = construir_perfil(entrada, cat, AHORA)
        perfil["dominio"]["variables"] = 0.0
        self.assertEqual(entrada, antes)
        self.assertEqual(cat, cat_antes)


# --- Batch: funciones puras -------------------------------------------------


class RecalculoTests(SimpleTestCase):
    def test_intereses_inferidos(self):
        cat = _catalogo()
        perfil = {"cursos_completados": [1]}
        self.assertEqual(intereses_inferidos(perfil, [2, 1, 999], cat), {
            "variables": 0.5,          # completado (0.5 × 1.0) gana a visto (0.2 × 1.0)
            "colecciones": 0.25,       # 0.5 × 0.5 (etiqueta de módulo)
            "condicionales": 0.2,      # visto
        })

    def test_abandono(self):
        inscripciones = {
            1: {"estado": "activo", "fecha_inscripcion": AHORA - timedelta(days=60)},
            2: {"estado": "activo", "fecha_inscripcion": AHORA - timedelta(days=60)},
            3: {"estado": "activo", "fecha_inscripcion": AHORA - timedelta(days=5)},
            4: {"estado": "completado", "fecha_inscripcion": AHORA - timedelta(days=90)},
            5: {"estado": "activo", "fecha_inscripcion": AHORA - timedelta(days=90)},
        }
        actividad = {1: AHORA - timedelta(days=31), 2: AHORA - timedelta(days=2)}
        self.assertEqual(cursos_abandonados(inscripciones, actividad, AHORA), [1, 5])

    def test_ultima_actividad_por_curso(self):
        intentos = [{"tema_id": 11, "fecha_intento": AHORA - timedelta(days=5)},
                    {"tema_id": 10, "fecha_intento": AHORA - timedelta(days=9)}]
        eventos = [{"curso_id": 1, "fecha": "2026-11-10T00:00:00Z"}, {"curso_id": 2, "fecha": None}]
        self.assertEqual(ultima_actividad_por_curso(intentos, eventos, _catalogo()),
                         {1: AHORA - timedelta(days=5)})

    def test_perfil_publico_sin_campos_internos(self):
        cat = _catalogo()
        perfil = construir_perfil(_entrada(
            dominio={"variables": 0.82, "pandas": 0.3, "colecciones": 0.6},
            evidencias={"variables": 4, "colecciones": 1},
            inscripciones=[{"curso_id": 2, "estado": "completado", "porcentaje_avance_global": 100,
                            "calificacion_final": 90, "fecha_inscripcion": AHORA, "completado_en": AHORA,
                            "origen": None},
                           {"curso_id": 77, "estado": "completado", "porcentaje_avance_global": 100,
                            "calificacion_final": 90, "fecha_inscripcion": AHORA, "completado_en": AHORA,
                            "origen": None}],
        ), cat, AHORA)
        publico = perfil_publico(perfil, ["datos", "datos"], cat)
        self.assertEqual(set(publico), {"nivel", "nivel_asignado", "nivel_inferido", "intereses_declarados",
                                        "dominio", "cursos_completados", "calculado_en"})
        self.assertEqual(publico["intereses_declarados"], ["datos"])
        self.assertEqual([d["clave"] for d in publico["dominio"]], ["colecciones", "variables"])
        self.assertEqual(publico["dominio"][1], {"clave": "variables", "nombre": "Variables",
                                                 "area": "fundamentos", "dominio": 0.82, "evidencias": 4})
        self.assertEqual(publico["cursos_completados"],
                         [{"curso_id": 2, "codigo_curso": "PY-201", "titulo": "Control"}])
        self.assertEqual(publico["calculado_en"], "2026-11-20T16:20:00Z")
        json.dumps(publico)


# --- Servicio con repositorio simulado --------------------------------------


class _RepoFalso:
    """Sustituye a `repository` registrando las escrituras."""

    def __init__(self, usuario=True, dominio=(), intereses=(), inscripciones=(), intentos=(),
                 vistas=(), ultimo_evento=None):
        self.usuario = {"id": USUARIO, "nivel_asignado": "Intermedio", "carrera_clave": None} if usuario else None
        self.dominio, self.intereses = list(dominio), list(intereses)
        self.inscripciones, self.intentos, self.vistas = list(inscripciones), list(intentos), list(vistas)
        self.ultimo_evento = ultimo_evento
        self.escrituras = []

    def parches(self):
        def leer_dominio(usuario_id, concepto_ids=None):
            return [f for f in self.dominio if concepto_ids is None or f["concepto_id"] in concepto_ids]

        def leer_intereses(usuario_id, origen=None):
            return [f for f in self.intereses if origen is None or f["origen"] == origen]

        def anotar(nombre):
            return lambda *args: self.escrituras.append((nombre, *args))

        funciones = {
            "leer_usuario": lambda u: self.usuario,
            "leer_inscripciones": lambda u: self.inscripciones,
            "leer_estados_temas": lambda u: [],
            "leer_intentos": lambda u: self.intentos,
            "leer_dominio": leer_dominio,
            "leer_intereses": leer_intereses,
            "leer_ultimo_evento": lambda u, curso_id=None: self.ultimo_evento,
            "leer_vistas": lambda u, desde: self.vistas,
            "guardar_dominio": anotar("guardar_dominio"),
            "guardar_interes": anotar("guardar_interes"),
            "retirar_intereses": anotar("retirar_intereses"),
            "marcar_abandonado": anotar("marcar_abandonado"),
            "guardar_snapshot": anotar("guardar_snapshot"),
        }
        return [mock.patch.object(repository, n, f) for n, f in funciones.items()] + [
            mock.patch("features.motor.perfil.service.cargar_catalogo", _catalogo),
        ]

    def __enter__(self):
        self._activos = self.parches()
        for p in self._activos:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self._activos):
            p.stop()


class ServicioTests(SimpleTestCase):
    def test_obtener_perfil_usuario_desconocido(self):
        with _RepoFalso(usuario=False):
            with self.assertRaises(NotFoundError):
                service.obtener_perfil(USUARIO)

    def test_obtener_perfil(self):
        with _RepoFalso(dominio=[{"concepto_id": 3, "concepto_clave": "variables", "dominio": "0.600",
                                  "evidencias": 2}],
                        ultimo_evento="2026-11-01T00:00:00Z"):
            perfil = service.obtener_perfil(USUARIO)
        self.assertEqual(perfil["dominio"], {"variables": 0.6})
        self.assertEqual(perfil["evidencias"], {"variables": 2})
        self.assertEqual(perfil["usuario_id"], USUARIO)

    def test_actualizar_dominio_por_tema_hace_upsert_de_los_conceptos_del_modulo(self):
        with _RepoFalso(dominio=[{"concepto_id": 3, "concepto_clave": "variables", "dominio": 0.5,
                                  "evidencias": 1}]) as repo:
            service.actualizar_dominio_por_tema(USUARIO, 11, 1.0)
        filas = sorted((e[2], e[3], e[4]) for e in repo.escrituras)
        self.assertEqual(filas, [(3, nuevo_dominio(0.5, 1.0, 0.5, 0.5), 2), (4, nuevo_dominio(None, 1.0, 0.5), 1)])
        self.assertTrue(all(e[0] == "guardar_dominio" and e[1] == USUARIO for e in repo.escrituras))

    def test_sembrar_dominio(self):
        with _RepoFalso() as repo:
            service.sembrar_dominio(USUARIO, {101: True, 103: False}, "Intermedio")
        self.assertEqual(sorted((e[2], e[3], e[4]) for e in repo.escrituras), [(3, 0.7, 1), (5, 0.2, 1)])

    def test_guardar_intereses_declarados_sustituye_solo_los_declarados(self):
        existentes = [
            {"concepto_id": 1, "concepto_clave": "fundamentos", "origen": "declarado", "peso": 1.0},
            {"concepto_id": 2, "concepto_clave": "datos", "origen": "declarado", "peso": 1.0},
            {"concepto_id": 4, "concepto_clave": "colecciones", "origen": "inferido", "peso": 0.5},
        ]
        with _RepoFalso(intereses=existentes) as repo:
            service.guardar_intereses_declarados(
                USUARIO, [("datos", 0.4), ("datos", 0.9), ("desconocida", 1.0), ("variables", 1.0)])
        self.assertEqual(repo.escrituras, [
            ("guardar_interes", USUARIO, 2, "declarado", 0.9),
            ("retirar_intereses", USUARIO, "declarado", [1]),
        ])


class RecalcularPerfilesTests(SimpleTestCase):
    def _repo(self):
        return _RepoFalso(
            inscripciones=[
                {"curso_id": 1, "estado": "completado", "porcentaje_avance_global": 100,
                 "calificacion_final": 90, "fecha_inscripcion": "2026-09-01T00:00:00Z",
                 "completado_en": "2026-10-01T00:00:00Z", "origen": None},
                {"curso_id": 2, "estado": "activo", "porcentaje_avance_global": 10,
                 "calificacion_final": None, "fecha_inscripcion": "2026-09-01T00:00:00Z",
                 "completado_en": None, "origen": None},
            ],
            intereses=[{"concepto_id": 6, "concepto_clave": "pandas", "origen": "inferido", "peso": 0.2}],
            vistas=[{"curso_id": 2, "fecha": "2026-11-19T00:00:00Z"}],
        )

    def test_recalcula_y_escribe(self):
        with self._repo() as repo:
            resumen = service.recalcular_perfil(USUARIO, _catalogo(), AHORA)
        self.assertEqual(resumen["abandonados"], [2])
        nombres = [e[0] for e in repo.escrituras]
        self.assertEqual(nombres.count("guardar_interes"), 3)
        self.assertIn(("retirar_intereses", USUARIO, "inferido", [6]), repo.escrituras)
        self.assertIn(("marcar_abandonado", USUARIO, 2), repo.escrituras)
        snapshot = [e for e in repo.escrituras if e[0] == "guardar_snapshot"][0]
        self.assertEqual(snapshot[1], USUARIO)
        self.assertEqual(snapshot[4], "2026-11-20T16:20:00Z")
        self.assertIn("tasa_aprobacion_modulos", snapshot[3])
        self.assertIn("dominio", snapshot[3])
        json.dumps(snapshot[3])

    def test_simular_no_escribe(self):
        with self._repo() as repo:
            resumen = service.recalcular_perfil(USUARIO, _catalogo(), AHORA, simular=True)
        self.assertEqual(repo.escrituras, [])
        self.assertEqual(resumen["abandonados"], [2])

    def test_orden_pagina_y_sigue_tras_un_fallo(self):
        ids = [f"{i:08d}-0000-0000-0000-000000000000" for i in range(101)]
        paginas = {None: ids[:100], ids[99]: ids[100:]}

        def recalcular(usuario_id, catalogo, simular=False):
            if usuario_id == ids[1]:
                raise RuntimeError("fallo")
            return {"nivel": "Principiante", "nivel_inferido": None, "intereses_inferidos": 0,
                    "abandonados": [], "simulado": simular}

        salida = StringIO()
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        with mock.patch.object(repository, "listar_usuarios", side_effect=lambda d, n: paginas[d]), \
                mock.patch("features.motor.management.commands.recalcular_perfiles.cargar_catalogo"), \
                mock.patch.object(service, "recalcular_perfil", side_effect=recalcular) as llamada:
            call_command("recalcular_perfiles", "--simular", stdout=salida)
        self.assertEqual(llamada.call_count, 101)
        self.assertTrue(all(c.kwargs["simular"] for c in llamada.call_args_list))
        self.assertIn("Total: 100 procesados, 1 con error (simulado, sin escrituras).", salida.getvalue())

    def test_un_usuario(self):
        salida = StringIO()
        with mock.patch.object(repository, "listar_usuarios") as listar, \
                mock.patch("features.motor.management.commands.recalcular_perfiles.cargar_catalogo"), \
                mock.patch.object(service, "recalcular_perfil", return_value={
                    "nivel": "Intermedio", "nivel_inferido": None, "intereses_inferidos": 0,
                    "abandonados": [], "simulado": False}) as llamada:
            call_command("recalcular_perfiles", "--usuario", USUARIO, stdout=salida)
        listar.assert_not_called()
        self.assertEqual(llamada.call_args.args[0], USUARIO)


# --- Vistas -----------------------------------------------------------------


def _verificar_falso(token):
    return {"id": USUARIO}


class VistasPerfilTests(SimpleTestCase):
    def _pedir(self, metodo, ruta, cuerpo=None, token="t"):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        kwargs = {"data": json.dumps(cuerpo), "content_type": "application/json"} if cuerpo is not None else {}
        return getattr(Client(), metodo)(ruta, **kwargs, **extra)

    def test_401_sin_token(self):
        with mock.patch("core.auth._verify_token") as verificar, \
                mock.patch.object(service, "obtener_perfil_publico") as obtener:
            self.assertEqual(self._pedir("get", f"/api/perfil/{USUARIO}", token=None).status_code, 401)
            self.assertEqual(self._pedir("put", f"/api/perfil/{USUARIO}/intereses", {"areas": []},
                                         token=None).status_code, 401)
        verificar.assert_not_called()
        obtener.assert_not_called()

    def test_403_otro_usuario(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(service, "obtener_perfil_publico") as obtener, \
                mock.patch.object(service, "guardar_intereses_declarados") as guardar:
            self.assertEqual(self._pedir("get", f"/api/perfil/{OTRO}").status_code, 403)
            self.assertEqual(self._pedir("put", f"/api/perfil/{OTRO}/intereses", {"areas": ["datos"]}).status_code, 403)
        obtener.assert_not_called()
        guardar.assert_not_called()

    def test_get_devuelve_el_perfil_publico(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(service, "obtener_perfil_publico", return_value={"nivel": "Intermedio"}):
            r = self._pedir("get", f"/api/perfil/{USUARIO}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"success": True, "perfil": {"nivel": "Intermedio"}})

    def test_put_guarda_con_el_peso_declarado(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch("features.motor.perfil.views.cargar_catalogo", _catalogo), \
                mock.patch.object(service, "guardar_intereses_declarados") as guardar:
            r = self._pedir("put", f"/api/perfil/{USUARIO}/intereses", {"areas": ["datos", "fundamentos", "datos"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"success": True, "intereses": ["datos", "fundamentos"]})
        guardar.assert_called_once_with(
            USUARIO, [("datos", config.PESO_INTERES_DECLARADO), ("fundamentos", config.PESO_INTERES_DECLARADO)])

    def test_put_validacion(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch("features.motor.perfil.views.cargar_catalogo", _catalogo), \
                mock.patch.object(service, "guardar_intereses_declarados") as guardar:
            for cuerpo in ({"areas": ["datos", "inexistente"]},
                           {"areas": ["variables"]},  # concepto, no área
                           {"areas": ["a", "b", "c", "d", "e"]},
                           {"areas": "datos"},
                           {}):
                with self.subTest(cuerpo=cuerpo):
                    r = self._pedir("put", f"/api/perfil/{USUARIO}/intereses", cuerpo)
                    self.assertEqual(r.status_code, 400)
                    self.assertEqual(r.json()["code"], "VALIDATION_ERROR")
        guardar.assert_not_called()
