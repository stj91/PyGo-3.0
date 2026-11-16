"""Pruebas del diagnóstico inicial (paquete 02). Sin red ni base de datos."""

from unittest import mock

from django.test import SimpleTestCase

from features.motor import config

from . import service

# Dos preguntas de diagnóstico (10 y 20) y una de lección (30), 4 opciones cada una.
OPCIONES = {
    101: {"id": 101, "ejercicio_id": 10, "es_correcta": False},
    102: {"id": 102, "ejercicio_id": 10, "es_correcta": True},
    103: {"id": 103, "ejercicio_id": 10, "es_correcta": False},
    104: {"id": 104, "ejercicio_id": 10, "es_correcta": False},
    201: {"id": 201, "ejercicio_id": 20, "es_correcta": False},
    202: {"id": 202, "ejercicio_id": 20, "es_correcta": False},
    203: {"id": 203, "ejercicio_id": 20, "es_correcta": True},
    204: {"id": 204, "ejercicio_id": 20, "es_correcta": False},
    301: {"id": 301, "ejercicio_id": 30, "es_correcta": True},
}
DIAGNOSTICO = [10, 20]


class CorregirDiagnosticoTests(SimpleTestCase):
    def test_correcta_e_incorrecta(self):
        respuestas = [
            {"ejercicio_id": 10, "opcion_id": 102},
            {"ejercicio_id": 20, "opcion_id": 201},
        ]
        self.assertEqual(
            service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO), {10: True, 20: False}
        )

    def test_respuesta_duplicada_gana_la_ultima(self):
        respuestas = [
            {"ejercicio_id": 10, "opcion_id": 102},
            {"ejercicio_id": 10, "opcion_id": 101},
        ]
        self.assertEqual(service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO), {10: False})

    def test_opcion_de_otro_ejercicio_no_cuenta(self):
        respuestas = [{"ejercicio_id": 10, "opcion_id": 203}]
        self.assertEqual(service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO), {})

    def test_opcion_de_ejercicio_no_diagnostico_no_cuenta(self):
        respuestas = [{"ejercicio_id": 30, "opcion_id": 301}]
        self.assertEqual(service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO), {})

    def test_opcion_inexistente_o_basura_no_cuenta(self):
        respuestas = [
            {"ejercicio_id": 10, "opcion_id": 999},
            {"ejercicio_id": 10, "opcion_id": True},
            {"ejercicio_id": "x", "opcion_id": 102},
            "no es un dict",
        ]
        self.assertEqual(service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO), {})

    def test_enviar_todas_las_opciones_no_sube_el_nivel(self):
        con_ejercicio = [
            {"ejercicio_id": o["ejercicio_id"], "opcion_id": o["id"]} for o in OPCIONES.values()
        ]
        sin_ejercicio = [{"opcion_id": o["id"]} for o in OPCIONES.values()]
        for respuestas in (con_ejercicio, sin_ejercicio, con_ejercicio + sin_ejercicio):
            resultados = service.corregir_diagnostico(respuestas, OPCIONES, DIAGNOSTICO)
            self.assertLessEqual(len(resultados), len(DIAGNOSTICO))
            # La última opción enviada de cada pregunta es incorrecta: 0 aciertos.
            self.assertEqual(sum(resultados.values()), 0)
            self.assertEqual(
                service.nivel_por_aciertos(sum(resultados.values())), service.NIVEL_PRINCIPIANTE
            )

    def test_ids_de_opciones_solo_enteros_sin_repetir(self):
        respuestas = [{"opcion_id": 1}, {"opcion_id": "2"}, {"opcion_id": 1}, {"opcion_id": "x)"}, {}]
        self.assertEqual(service.ids_de_opciones(respuestas), [1, 2])


class NivelPorAciertosTests(SimpleTestCase):
    def test_umbrales(self):
        esperado = ["Principiante", "Principiante", "Intermedio", "Intermedio", "Avanzado", "Avanzado"]
        self.assertEqual([service.nivel_por_aciertos(n) for n in range(6)], esperado)


class MetasEstudioTests(SimpleTestCase):
    def test_los_cuatro_textos(self):
        casos = {
            "5 a 10 minutos al día (Sesiones micro)": (10, 70),
            "Un par de horas a la semana": (17, 120),
            "Fines de semana exclusivamente": (26, 180),
            "1 hora diaria estructurada": (60, 420),
        }
        for texto, (diaria, semanal) in casos.items():
            self.assertEqual(
                service.metas_estudio(texto),
                {"meta_diaria_minutos": diaria, "meta_semanal_minutos": semanal},
                texto,
            )

    def test_numero_son_minutos_diarios(self):
        self.assertEqual(
            service.metas_estudio(45), {"meta_diaria_minutos": 45, "meta_semanal_minutos": 315}
        )
        self.assertEqual(
            service.metas_estudio("20"), {"meta_diaria_minutos": 20, "meta_semanal_minutos": 140}
        )

    def test_texto_desconocido(self):
        defecto = {"meta_diaria_minutos": 30, "meta_semanal_minutos": 210}
        for valor in ("Cuando pueda", None, 0, -5, True):
            self.assertEqual(service.metas_estudio(valor), defecto, valor)


class AreasDeInteresesTests(SimpleTestCase):
    VALIDAS = {"fundamentos", "datos", "automatizacion", "web"}

    def test_deduplica_y_descarta_invalidas(self):
        self.assertEqual(
            service.areas_de_intereses(["web", "inventada", "web", 3], None, self.VALIDAS),
            [("web", config.PESO_INTERES_DECLARADO)],
        )

    def test_objetivo_suma_su_area(self):
        self.assertEqual(
            service.areas_de_intereses(["web"], "Análisis de datos y Ciencia de Datos", self.VALIDAS),
            [("web", config.PESO_INTERES_DECLARADO), ("datos", config.PESO_INTERES_OBJETIVO)],
        )

    def test_objetivo_ya_declarado_no_se_repite(self):
        self.assertEqual(
            service.areas_de_intereses(["datos"], "Análisis de datos y Ciencia de Datos", self.VALIDAS),
            [("datos", config.PESO_INTERES_DECLARADO)],
        )

    def test_objetivo_sin_area_o_intereses_no_lista(self):
        self.assertEqual(
            service.areas_de_intereses("web", "Curiosidad personal y desarrollo profesional", self.VALIDAS),
            [],
        )


class FormatearPreguntasTests(SimpleTestCase):
    def test_sin_es_correcta_y_ordenadas(self):
        ejercicios = [
            {
                "id": 20,
                "consigna": "B",
                "tipo": "evaluacion_tecnica",
                "opciones_ejercicios": [
                    {"id": 7, "texto_opcion": "y", "orden": 2, "es_correcta": True},
                    {"id": 8, "texto_opcion": "x", "orden": 1, "es_correcta": False},
                ],
            },
            {"id": 10, "consigna": None, "opciones_ejercicios": None},
        ]
        salida = service.formatear_preguntas(ejercicios)
        self.assertEqual(
            salida,
            [
                {"id": 10, "consigna": "", "opciones": []},
                {
                    "id": 20,
                    "consigna": "B",
                    "opciones": [{"id": 8, "texto_opcion": "x"}, {"id": 7, "texto_opcion": "y"}],
                },
            ],
        )
        self.assertNotIn("es_correcta", repr(salida))

    def test_la_consulta_no_selecciona_es_correcta(self):
        from . import repository

        self.assertNotIn("es_correcta", repository.PREGUNTA_COLUMNS)


@mock.patch.object(service, "_areas_validas", return_value={"datos", "web"})
@mock.patch("features.motor.perfil.service.guardar_intereses_declarados")
@mock.patch.object(service.ganchos, "al_completar_diagnostico")
@mock.patch.object(service, "repository")
class EvaluarTests(SimpleTestCase):
    def _configurar(self, repo):
        repo.listar_ids_diagnostico.return_value = DIAGNOSTICO
        repo.buscar_opciones.side_effect = lambda ids: [OPCIONES[i] for i in ids if i in OPCIONES]

    def test_llama_al_gancho_con_resultados_y_nivel(self, repo, gancho, intereses, _areas):
        self._configurar(repo)
        datos = {
            "usuario_id": "u-1",
            "familiaridad": "Apenas inicio",
            "respuestas_tecnicas": [
                {"ejercicio_id": 10, "opcion_id": 102},
                {"ejercicio_id": 20, "opcion_id": 203},
            ],
            "objetivo": "Análisis de datos y Ciencia de Datos",
            "disponibilidad": "1 hora diaria estructurada",
            "intereses": ["web"],
        }
        salida = service.evaluar(datos)

        self.assertEqual(salida, {"nivel_asignado": "Intermedio", "aciertos": 2, "total": 2})
        gancho.assert_called_once_with("u-1", {10: True, 20: True}, "Intermedio")
        repo.buscar_opciones.assert_called_once_with([102, 203])
        repo.actualizar_nivel.assert_called_once_with(
            "u-1", nivel_asignado="Intermedio", objetivo_aprendizaje="Análisis de datos y Ciencia de Datos"
        )
        repo.guardar_metas.assert_called_once_with(
            "u-1", meta_diaria_minutos=60, meta_semanal_minutos=420
        )
        intentos = repo.registrar_intentos.call_args.args[0]
        self.assertEqual([i["ejercicio_id"] for i in intentos], [10, 20])
        self.assertEqual({i["calificacion_obtenida"] for i in intentos}, {100})
        intereses.assert_called_once_with(
            "u-1", [("web", config.PESO_INTERES_DECLARADO), ("datos", config.PESO_INTERES_OBJETIVO)]
        )

    def test_atajo_no_se_nada(self, repo, gancho, intereses, _areas):
        self._configurar(repo)
        salida = service.evaluar(
            {
                "usuario_id": "u-1",
                "familiaridad": "No sé nada",
                "respuestas_tecnicas": [{"ejercicio_id": 10, "opcion_id": 102}],
            }
        )
        self.assertEqual(salida, {"nivel_asignado": "Principiante", "aciertos": 0, "total": 0})
        repo.buscar_opciones.assert_not_called()
        repo.guardar_metas.assert_not_called()
        gancho.assert_called_once_with("u-1", {}, "Principiante")

    def test_intereses_pendientes_no_rompen(self, repo, gancho, intereses, _areas):
        self._configurar(repo)
        intereses.side_effect = NotImplementedError("pendiente: paquete 04")
        salida = service.evaluar({"usuario_id": "u-1", "familiaridad": "No sé nada"})
        self.assertEqual(salida["nivel_asignado"], "Principiante")
        gancho.assert_called_once()


class VistasTests(SimpleTestCase):
    """Auth de las vistas y que `es_correcta` no viaja en la respuesta."""

    def _pedir(self, metodo, ruta, cuerpo=None, token=None):
        import json

        from django.test import Client

        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        kwargs = {"data": json.dumps(cuerpo), "content_type": "application/json"} if cuerpo is not None else {}
        return getattr(Client(), metodo)(ruta, **kwargs, **extra)

    def test_preguntas_sin_token_es_401(self):
        self.assertEqual(self._pedir("get", "/api/cold-start/preguntas").status_code, 401)

    def test_evaluar_sin_token_es_401(self):
        self.assertEqual(self._pedir("post", "/api/cold-start/evaluar", {}).status_code, 401)

    @mock.patch("core.auth._verify_token", return_value={"id": "u-1"})
    def test_evaluar_otro_usuario_es_403(self, _):
        r = self._pedir("post", "/api/cold-start/evaluar", {"usuario_id": "u-2"}, token="t")
        self.assertEqual(r.status_code, 403)

    @mock.patch("core.auth._verify_token", return_value={"id": "u-1"})
    @mock.patch.object(service.repository, "listar_preguntas")
    def test_preguntas_sin_es_correcta(self, listar, _):
        listar.return_value = [
            {"id": 1, "consigna": "¿?", "opciones_ejercicios": [
                {"id": 3, "texto_opcion": "a", "orden": 1, "es_correcta": True}]},
        ]
        r = self._pedir("get", "/api/cold-start/preguntas", token="t")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.json(),
            {"success": True, "preguntas": [
                {"id": 1, "consigna": "¿?", "opciones": [{"id": 3, "texto_opcion": "a"}]}]},
        )
        self.assertNotIn("es_correcta", r.content.decode())
