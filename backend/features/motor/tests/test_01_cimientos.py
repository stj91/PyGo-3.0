"""Tests del paquete 01: catálogo, ganchos, stubs, rutas y errores. Sin red."""

import importlib
import inspect
import json
import logging
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase

from core.errors import NoImplementadoError, error_payload, error_status
from features.motor import catalogo, config, ganchos
from features.motor.areas_views import areas_publicas

USUARIO = "11111111-1111-1111-1111-111111111111"
OTRO = "22222222-2222-2222-2222-222222222222"


def _filas():
    """Filas planas de un catálogo pequeño: 3 cursos (uno sin publicar)."""
    return {
        "cursos": [
            {"id": 1, "codigo_curso": "PY-101", "titulo": "Fundamentos", "descripcion": "d1",
             "dificultad": 1, "nivel": "Principiante", "publicado": True},
            {"id": 2, "codigo_curso": "PY-201", "titulo": "Control", "descripcion": None,
             "dificultad": 1, "nivel": "Principiante", "publicado": True},
            {"id": 9, "codigo_curso": "PY-901", "titulo": "Oculto", "descripcion": "x",
             "dificultad": 5, "nivel": "Avanzado", "publicado": False},
        ],
        "temas": [
            {"id": 11, "curso_id": 1, "orden": 2, "titulo": "Colecciones"},
            {"id": 10, "curso_id": 1, "orden": 1, "titulo": "Variables"},
            {"id": 20, "curso_id": 2, "orden": 1, "titulo": "If"},
            {"id": 90, "curso_id": 9, "orden": 1, "titulo": "Oculto"},
        ],
        "conceptos": [
            {"id": 1, "clave": "fundamentos", "nombre": "Fundamentos", "padre_id": None},
            {"id": 2, "clave": "datos", "nombre": "Datos", "padre_id": None},
            {"id": 3, "clave": "variables_tipos", "nombre": "Variables y tipos", "padre_id": 1},
            {"id": 4, "clave": "colecciones", "nombre": "Listas y tuplas", "padre_id": 1},
            {"id": 5, "clave": "condicionales", "nombre": "Condicionales", "padre_id": 1},
            {"id": 6, "clave": "comprensiones", "nombre": "Comprensiones", "padre_id": 2},
        ],
        "contenido": [
            {"objeto_tipo": "curso", "objeto_id": 1, "concepto_clave": "variables_tipos", "peso": 1.0},
            {"objeto_tipo": "curso", "objeto_id": 1, "concepto_clave": "colecciones", "peso": 0.2},
            {"objeto_tipo": "tema", "objeto_id": 10, "concepto_clave": "variables_tipos", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 11, "concepto_clave": "colecciones", "peso": 1.0},
            {"objeto_tipo": "tema", "objeto_id": 11, "concepto_clave": "comprensiones", "peso": 0.4},
            {"objeto_tipo": "curso", "objeto_id": 2, "concepto_clave": "condicionales", "peso": "1.00"},
            {"objeto_tipo": "curso", "objeto_id": 2, "concepto_clave": "desconocido", "peso": 1.0},
            {"objeto_tipo": "curso", "objeto_id": 9, "concepto_clave": "comprensiones", "peso": 1.0},
        ],
        "prerrequisitos": [
            {"curso_id": 2, "requiere_curso_id": 1, "calificacion_minima": 80},
            {"curso_id": 9, "requiere_curso_id": 2, "calificacion_minima": "75.50"},
        ],
        "carrera_areas": [
            {"carrera_clave": "INCO", "area_clave": "datos", "peso": 0.3},
            {"carrera_clave": "INCO", "area_clave": "fundamentos", "peso": 0.5},
            {"carrera_clave": "LMAT", "area_clave": "datos", "peso": "0.50"},
            {"carrera_clave": "LMAT", "area_clave": "inexistente", "peso": 0.5},
        ],
        "ejercicios_diagnostico": [{"id": 101, "tema_id": 10}, {"id": 102, "tema_id": 20}],
    }


def _ensamblar(**cambios):
    filas = {**_filas(), **cambios}
    return catalogo.ensamblar_catalogo(
        filas["cursos"], filas["temas"], filas["conceptos"], filas["contenido"],
        filas["prerrequisitos"], filas["carrera_areas"], filas["ejercicios_diagnostico"],
    )


class EnsamblarCatalogoTests(SimpleTestCase):
    def test_mapa_de_ejercicios_de_diagnostico(self):
        self.assertEqual(_ensamblar()["ejercicios_diagnostico"], {101: 10, 102: 20})

    def test_combina_conceptos_de_curso_y_modulo_por_maximo(self):
        c = _ensamblar()["cursos"][1]
        # curso 1.0 vs módulo 0.5 × 1.0 -> 1.0; curso 0.2 vs 0.5 × 1.0 -> 0.5;
        # solo en módulo 0.5 × 0.4 -> 0.2.
        self.assertEqual(c["conceptos"], {"variables_tipos": 1.0, "colecciones": 0.5, "comprensiones": 0.2})

    def test_areas_derivadas_de_los_conceptos(self):
        cat = _ensamblar()
        self.assertEqual(cat["cursos"][1]["areas"], ["datos", "fundamentos"])
        self.assertEqual(cat["cursos"][2]["areas"], ["fundamentos"])

    def test_curso_no_publicado_excluido(self):
        cursos = _ensamblar()["cursos"]
        self.assertEqual(sorted(cursos), [1, 2])

    def test_modulos_ordenados(self):
        temas = _ensamblar()["cursos"][1]["temas"]
        self.assertEqual([t["orden"] for t in temas], [1, 2])
        self.assertEqual(temas[0], {"id": 10, "curso_id": 1, "orden": 1, "titulo": "Variables",
                                    "conceptos": {"variables_tipos": 1.0}})

    def test_forma_de_prerrequisitos(self):
        cat = _ensamblar()
        self.assertEqual(cat["cursos"][2]["prerrequisitos"], [{"curso_id": 1, "calificacion_minima": 80.0}])
        self.assertEqual(cat["cursos"][1]["prerrequisitos"], [])

    def test_carreras_mapeadas_por_clave(self):
        self.assertEqual(
            _ensamblar()["carrera_areas"],
            {"INCO": {"datos": 0.3, "fundamentos": 0.5}, "LMAT": {"datos": 0.5}},
        )

    def test_conceptos_y_areas(self):
        cat = _ensamblar()
        self.assertEqual(cat["conceptos"]["colecciones"]["area"], "fundamentos")
        self.assertIsNone(cat["conceptos"]["datos"]["area"])
        self.assertEqual(cat["areas"], {
            "fundamentos": ["colecciones", "condicionales", "variables_tipos"],
            "datos": ["comprensiones"],
        })

    def test_campos_del_curso(self):
        c = _ensamblar()["cursos"][2]
        self.assertEqual(c["descripcion"], "")
        self.assertEqual((c["dificultad"], c["nivel"], c["publicado"]), (1, "Principiante", True))
        self.assertEqual(c["conceptos"], {"condicionales": 1.0})

    def test_no_muta_la_entrada(self):
        filas = _filas()
        copia = json.loads(json.dumps(filas))
        catalogo.ensamblar_catalogo(*filas.values())
        self.assertEqual(filas, copia)

    def test_sin_diagnostico_es_vacio(self):
        self.assertEqual(_ensamblar(ejercicios_diagnostico=[])["ejercicios_diagnostico"], {})


class CargarCatalogoTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    @staticmethod
    def _select_falso(llamadas):
        filas = _filas()
        por_tabla = {
            "cursos": [c for c in filas["cursos"] if c["publicado"]],
            "temas": filas["temas"],
            "conceptos": filas["conceptos"],
            "contenido_concepto": [
                {"objeto_tipo": f["objeto_tipo"], "objeto_id": f["objeto_id"], "peso": f["peso"],
                 "conceptos": {"clave": f["concepto_clave"]}}
                for f in filas["contenido"]
            ],
            "curso_prerrequisitos": filas["prerrequisitos"],
            "carrera_areas": [
                {"peso": f["peso"], "carreras": {"clave": f["carrera_clave"]},
                 "conceptos": {"clave": f["area_clave"]}}
                for f in filas["carrera_areas"]
            ],
            "ejercicios": filas["ejercicios_diagnostico"],
        }

        def select(tabla, **kwargs):
            llamadas.append((tabla, kwargs))
            return por_tabla[tabla]

        return select

    def test_lee_una_vez_por_tabla_y_memoiza(self):
        llamadas = []
        with mock.patch.object(catalogo.supabase, "select", self._select_falso(llamadas)):
            primero = catalogo.cargar_catalogo()
            segundo = catalogo.cargar_catalogo()

        tablas = [t for t, _ in llamadas]
        self.assertEqual(sorted(tablas), sorted([
            "cursos", "temas", "conceptos", "contenido_concepto",
            "curso_prerrequisitos", "carrera_areas", "ejercicios",
        ]))
        self.assertNotIn("opciones_ejercicios", tablas)
        self.assertEqual(primero, segundo)
        self.assertEqual(primero["cursos"][1]["conceptos"]["colecciones"], 0.5)
        self.assertEqual(primero["carrera_areas"]["INCO"], {"datos": 0.3, "fundamentos": 0.5})

        filtros = dict(llamadas)
        self.assertIn(("tipo", "eq.evaluacion_tecnica"), filtros["ejercicios"]["filters"])
        self.assertIn(("publicado", "eq.true"), filtros["cursos"]["filters"])

    def test_invalidar_vuelve_a_leer(self):
        llamadas = []
        with mock.patch.object(catalogo.supabase, "select", self._select_falso(llamadas)):
            catalogo.cargar_catalogo()
            catalogo.invalidar_catalogo()
            catalogo.cargar_catalogo()
        self.assertEqual(len(llamadas), 14)

    def test_cero_segundos_desactiva_la_cache(self):
        llamadas = []
        with mock.patch.object(config, "CATALOGO_CACHE_SEGUNDOS", 0), \
                mock.patch.object(catalogo.supabase, "select", self._select_falso(llamadas)):
            catalogo.cargar_catalogo()
            catalogo.cargar_catalogo()
        self.assertEqual(len(llamadas), 14)


class AreasTests(SimpleTestCase):
    def test_areas_por_nombre(self):
        self.assertEqual(areas_publicas(_ensamblar()), [
            {"clave": "datos", "nombre": "Datos"},
            {"clave": "fundamentos", "nombre": "Fundamentos"},
        ])

    def test_endpoint_publico(self):
        with mock.patch("features.motor.areas_views.cargar_catalogo", return_value=_ensamblar()):
            respuesta = Client().get("/api/motor/areas")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["areas"][0], {"clave": "datos", "nombre": "Datos"})


class GanchosTests(SimpleTestCase):
    TEMA = {"id": 10, "curso_id": 1, "orden": 1}

    def _con_destinos(self, error):
        return (
            mock.patch("features.motor.eventos.service.registrar_servidor", side_effect=error),
            mock.patch("features.motor.perfil.service.actualizar_dominio_por_tema", side_effect=error),
            mock.patch("features.motor.perfil.service.sembrar_dominio", side_effect=error),
        )

    def test_ningun_gancho_lanza(self):
        for error in (NotImplementedError("pendiente"), RuntimeError("roto")):
            eventos, dominio, sembrar = self._con_destinos(error)
            with self.subTest(error=type(error).__name__), eventos as ev, dominio as dom, sembrar as sem, \
                    self.assertLogs("features.motor.ganchos", level="DEBUG"):
                self.assertIsNone(ganchos.al_evaluar_modulo(USUARIO, self.TEMA, 85, [], True))
                self.assertIsNone(ganchos.al_completar_curso(USUARIO, 1, 90.0))
                self.assertIsNone(ganchos.al_completar_diagnostico(USUARIO, {101: True, 102: False}, "Intermedio"))
                # Un fallo no corta las llamadas siguientes.
                self.assertEqual(ev.call_count, 4)
                dom.assert_called_once_with(USUARIO, 10, 0.85)
                sem.assert_called_once_with(USUARIO, {101: True, 102: False}, "Intermedio")

    def test_stubs_reales_no_rompen(self):
        with mock.patch("features.motor.eventos.service.registrar_servidor"), \
                mock.patch("features.motor.perfil.service.actualizar_dominio_por_tema"), \
                mock.patch("features.motor.perfil.service.sembrar_dominio"):
            self._llamar_ganchos()

    def _llamar_ganchos(self):
        self.assertIsNone(ganchos.al_evaluar_modulo(USUARIO, self.TEMA, 50, [], False))
        self.assertIsNone(ganchos.al_completar_curso(USUARIO, 1, 90.0))
        self.assertIsNone(ganchos.al_completar_diagnostico(USUARIO, {}, "Principiante"))

    def test_argumentos_invalidos_no_lanzan(self):
        with self.assertLogs("features.motor.ganchos", level="ERROR"):
            self.assertIsNone(ganchos.al_evaluar_modulo(USUARIO, {}, 50, [], False))

    def test_llamadas_segun_contrato(self):
        with mock.patch("features.motor.eventos.service.registrar_servidor") as ev, \
                mock.patch("features.motor.perfil.service.actualizar_dominio_por_tema"), \
                mock.patch("features.motor.perfil.service.sembrar_dominio"):
            ganchos.al_evaluar_modulo(USUARIO, self.TEMA, 80, [{"ejercicio_id": 1, "es_correcta": True}], True)
            ganchos.al_evaluar_modulo(USUARIO, self.TEMA, 40, [], False)
            ganchos.al_completar_curso(USUARIO, 1, 92.5)
            ganchos.al_completar_diagnostico(USUARIO, {101: True, 102: False}, "Intermedio")

        self.assertEqual(ev.call_args_list, [
            mock.call(USUARIO, "quiz_intento", objeto_tipo="tema", objeto_id=10, curso_id=1, valor=0.8,
                      datos={"detalle": [{"ejercicio_id": 1, "es_correcta": True}]}),
            mock.call(USUARIO, "tema_completado", objeto_tipo="tema", objeto_id=10, curso_id=1),
            mock.call(USUARIO, "quiz_intento", objeto_tipo="tema", objeto_id=10, curso_id=1, valor=0.4,
                      datos={"detalle": []}),
            mock.call(USUARIO, "curso_completado", objeto_tipo="curso", objeto_id=1, curso_id=1, valor=92.5),
            mock.call(USUARIO, "diagnostico", valor=0.5,
                      datos={"resultados": {"101": True, "102": False}, "nivel": "Intermedio"}),
        ])


def _verificar_falso(token):
    return {"id": USUARIO}


class VistasStubTests(SimpleTestCase):
    """Cada vista del motor exige su autenticación y responde 501."""

    RUTAS = [
        ("get", "/api/cold-start/preguntas", None),
        ("post", "/api/eventos", {"tipo": "sesion_inicio"}),
        ("post", "/api/cursos/1/inscripcion", {}),
        ("get", f"/api/perfil/{USUARIO}", None),
        ("put", f"/api/perfil/{USUARIO}/intereses", {"areas": ["datos"]}),
        ("get", f"/api/recomendaciones/cursos?usuario_id={USUARIO}", None),
        ("post", "/api/retroalimentacion", {"recomendacion_id": "r-x", "accion": "clic"}),
    ]

    def setUp(self):
        # @endpoint registra con traza todo error >= 500, 501 incluido.
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def _pedir(self, metodo, ruta, cuerpo, token=None):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        kwargs = {"data": json.dumps(cuerpo), "content_type": "application/json"} if cuerpo is not None else {}
        return getattr(Client(), metodo)(ruta, **kwargs, **extra)

    def test_401_sin_token(self):
        with mock.patch("core.auth._verify_token") as verificar:
            for metodo, ruta, cuerpo in self.RUTAS:
                with self.subTest(ruta=ruta):
                    self.assertEqual(self._pedir(metodo, ruta, cuerpo).status_code, 401)
            verificar.assert_not_called()

    def test_403_para_otro_usuario(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso):
            for metodo, ruta, cuerpo in [
                ("get", f"/api/perfil/{OTRO}", None),
                ("put", f"/api/perfil/{OTRO}/intereses", {"areas": []}),
                ("get", f"/api/recomendaciones/cursos?usuario_id={OTRO}", None),
            ]:
                with self.subTest(ruta=ruta):
                    self.assertEqual(self._pedir(metodo, ruta, cuerpo, token="t").status_code, 403)

    def test_recomendaciones_sin_usuario_id_es_400(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso):
            self.assertEqual(self._pedir("get", "/api/recomendaciones/cursos", None, token="t").status_code, 400)

    def test_metodo_incorrecto_es_405(self):
        self.assertEqual(Client().get("/api/eventos").status_code, 405)


class NoImplementadoErrorTests(SimpleTestCase):
    def test_traduccion_http(self):
        error = NoImplementadoError()
        self.assertEqual(error_status(error), 501)
        self.assertEqual(error_payload(error)["code"], "NOT_IMPLEMENTED")
        self.assertFalse(error_payload(error)["success"])


class StubsTests(SimpleTestCase):
    #: módulo -> {función: parámetros}, según 00-arquitectura.md §5.2.
    FIRMAS = {
        "features.motor.catalogo": {
            "cargar_catalogo": [],
            "ensamblar_catalogo": ["cursos", "temas", "conceptos", "contenido", "prerrequisitos",
                                   "carrera_areas", "ejercicios_diagnostico"],
        },
        "features.motor.eventos.service": {"registrar_servidor": ["usuario_id", "tipo", "**campos"]},
        "features.motor.eventos.validacion": {"validar_evento": ["cuerpo", "usuario_id_autenticado", "origen"]},
        "features.motor.inscripcion.service": {"inscribir": ["usuario_id", "curso_id", "origen", "recomendacion_id"]},
        "features.motor.perfil.dominio": {
            "nuevo_dominio": ["anterior", "puntaje", "inicial", "peso=1.0"],
            "reproducir_dominio": ["eventos", "catalogo", "nivel_asignado", "hasta"],
        },
        "features.motor.perfil.construir": {"construir_perfil": ["entrada", "catalogo", "ahora"]},
        "features.motor.perfil.service": {
            "obtener_perfil": ["usuario_id"],
            "actualizar_dominio_por_tema": ["usuario_id", "tema_id", "puntaje"],
            "sembrar_dominio": ["usuario_id", "resultados", "nivel"],
            "guardar_intereses_declarados": ["usuario_id", "areas"],
        },
        "features.motor.candidatos": {
            "candidatos": ["perfil", "catalogo"],
            "filtrar": ["perfil", "cursos", "catalogo", "reglas"],
            "siguiente_en_ruta": ["perfil", "catalogo"],
        },
        "features.motor.estrategias.reglas": {
            "cargar_reglas": [],
            "puntuar": ["perfil", "candidatos", "contexto"],
        },
        "features.motor.estrategias.contenido": {
            "puntuar": ["perfil", "candidatos", "contexto"],
            "similitud_entre_cursos": ["a", "b"],
        },
        "features.motor.estrategias.colaborativo": {
            "cargar_similitudes": [],
            "calcular_similitudes": ["interacciones"],
            "puntuar": ["perfil", "candidatos", "contexto"],
        },
        "features.motor.estrategias.modelo": {
            "cargar_activo": ["nombre='aprobacion'"],
            "caracteristicas_para": ["perfil", "curso", "catalogo"],
            "predecir": ["arbol", "x"],
            "puntuar": ["perfil", "candidatos", "contexto"],
        },
        "features.motor.hibrido": {
            "recomendar": ["perfil", "contexto", "limite", "estrategias=None"],
            "recomendar_cursos": ["usuario_id", "limite"],
        },
        "features.motor.registro": {"marcar_aceptada": ["recomendacion_id", "usuario_id"]},
        "features.motor.experimento": {"grupo": ["usuario_id", "experimento='motor-v1'"]},
        "features.motor.ganchos": {
            "al_evaluar_modulo": ["usuario_id", "tema", "calificacion", "detalle", "aprobado"],
            "al_completar_curso": ["usuario_id", "curso_id", "calificacion_final"],
            "al_completar_diagnostico": ["usuario_id", "resultados", "nivel"],
        },
    }

    @staticmethod
    def _parametros(funcion):
        resultado = []
        for p in inspect.signature(funcion).parameters.values():
            if p.kind is p.VAR_KEYWORD:
                resultado.append(f"**{p.name}")
            elif p.default is not p.empty:
                resultado.append(f"{p.name}={p.default!r}")
            else:
                resultado.append(p.name)
        return resultado

    def test_firmas_exactas(self):
        for modulo, funciones in self.FIRMAS.items():
            m = importlib.import_module(modulo)
            for nombre, esperados in funciones.items():
                with self.subTest(funcion=f"{modulo}.{nombre}"):
                    self.assertEqual(self._parametros(getattr(m, nombre)), esperados)

    def test_ordenes_de_gestion_pendientes(self):
        for orden, paquete in [
        ]:
            with self.subTest(orden=orden):
                with self.assertRaisesMessage(CommandError, f"pendiente: paquete {paquete}"):
                    call_command(orden)

    def test_config_expone_las_constantes(self):
        self.assertEqual(config.MOTOR_VERSION, "hibrido-v1")
        self.assertEqual(config.CATALOGO_CACHE_SEGUNDOS, 300)
        self.assertEqual(set(config.PESOS_ESTRATEGIA), {"nuevo", "con_historia", "con_modelo"})
        for pesos in config.PESOS_ESTRATEGIA.values():
            self.assertAlmostEqual(sum(pesos.values()), 1.0)
