"""Pruebas de la calificación de módulos (paquete 02). Sin red ni base de datos."""

from itertools import product
from unittest import mock

from django.test import SimpleTestCase

from core.errors import ValidationError
from features.cursos import service as cursos_service

from . import service

EJERCICIOS = [
    {"id": 1, "tema_id": 5, "tipo": "ejercicio_practico"},
    {"id": 2, "tema_id": 5, "tipo": "ejercicio_practico"},
    {"id": 9, "tema_id": 5, "tipo": "evaluacion_tecnica"},
]
OPCIONES = [
    {"id": 11, "ejercicio_id": 1, "es_correcta": True},
    {"id": 12, "ejercicio_id": 1, "es_correcta": False},
    {"id": 21, "ejercicio_id": 2, "es_correcta": True},
    {"id": 22, "ejercicio_id": 2, "es_correcta": False},
    {"id": 91, "ejercicio_id": 9, "es_correcta": True},
]


class CorregirTests(SimpleTestCase):
    def test_opcion_ajena_rechazada(self):
        respuestas = [
            {"ejercicio_id": 1, "opcion_id": 11},
            {"ejercicio_id": 2, "opcion_id": 777},  # de otro módulo
            {"ejercicio_id": 9, "opcion_id": 91},  # del diagnóstico
        ]
        aciertos, retro, rechazadas = service.corregir(respuestas, OPCIONES, EJERCICIOS)
        self.assertEqual(aciertos, 1)
        self.assertEqual(rechazadas, [777, 91])
        self.assertEqual([r["ejercicio_id"] for r in retro], [1, 2])

    def test_sin_responder_cuenta_como_fallo(self):
        aciertos, retro, _ = service.corregir([{"ejercicio_id": 1, "opcion_id": 11}], OPCIONES, EJERCICIOS)
        self.assertEqual(aciertos, 1)
        self.assertEqual(
            retro[1],
            {"ejercicio_id": 2, "opcion_id": None, "es_correcta": False, "retroalimentacion": "Sin responder."},
        )

    def test_denominador_es_el_numero_de_ejercicios(self):
        aciertos, retro, _ = service.corregir([{"opcion_id": 11}], OPCIONES, EJERCICIOS[:2])
        self.assertEqual(len(retro), 2)
        self.assertEqual(service.calificar(aciertos, len(retro)), 50)

    def test_gana_la_ultima_respuesta(self):
        respuestas = [{"opcion_id": 11}, {"opcion_id": 12}, {"opcion_id": 22}, {"opcion_id": 21}]
        aciertos, retro, rechazadas = service.corregir(respuestas, OPCIONES, EJERCICIOS)
        self.assertEqual(aciertos, 1)
        self.assertEqual([r["opcion_id"] for r in retro], [12, 21])
        self.assertEqual(rechazadas, [])

    def test_todas_las_opciones_no_aprueban(self):
        respuestas = [{"opcion_id": o["id"]} for o in OPCIONES]
        aciertos, retro, _ = service.corregir(respuestas, OPCIONES, EJERCICIOS)
        self.assertEqual(aciertos, 0)

    def test_forma_de_la_retroalimentacion(self):
        _, retro, _ = service.corregir([{"opcion_id": 11}, {"opcion_id": 22}], OPCIONES, EJERCICIOS)
        self.assertEqual(
            retro,
            [
                {"ejercicio_id": 1, "opcion_id": 11, "es_correcta": True, "retroalimentacion": "¡Correcto!"},
                {"ejercicio_id": 2, "opcion_id": 22, "es_correcta": False, "retroalimentacion": "Respuesta incorrecta."},
            ],
        )

    def test_intentos_incluyen_no_respondidos(self):
        _, retro, _ = service.corregir([{"opcion_id": 11}], OPCIONES, EJERCICIOS)
        intentos = service.construir_intentos("u", retro, 7)
        self.assertEqual([(i["ejercicio_id"], i["calificacion_obtenida"]) for i in intentos], [(1, 100), (2, 0)])
        self.assertEqual(sum(i["tiempo_resolucion_segundos"] for i in intentos), 7)


class AvanzaEstadoTests(SimpleTestCase):
    RANGO = ["Bloqueado", "desbloqueado", "actividades_de_refuerzo", "completado"]

    def test_cada_par_del_orden(self):
        for (i, actual), (j, nuevo) in product(enumerate(self.RANGO), repeat=2):
            self.assertEqual(service.avanza_estado([actual], nuevo), j > i, (actual, nuevo))

    def test_desconocido_y_none_valen_cero(self):
        self.assertTrue(service.avanza_estado([None, "raro"], "desbloqueado"))
        self.assertFalse(service.avanza_estado(["desbloqueado"], "raro"))

    def test_duplicados_debe_superar_a_todos(self):
        self.assertFalse(service.avanza_estado(["desbloqueado", "completado"], "actividades_de_refuerzo"))
        self.assertTrue(service.avanza_estado(["desbloqueado", "actividades_de_refuerzo"], "completado"))

    def test_sin_filas_cualquiera_avanza(self):
        for estado in self.RANGO[1:]:
            self.assertTrue(service.avanza_estado([], estado))


class CalificacionFinalTests(SimpleTestCase):
    def test_ultimo_por_ejercicio_sin_diagnostico(self):
        intentos = [
            {"id": 1, "ejercicio_id": 1, "calificacion_obtenida": 0, "fecha_intento": "2026-11-01T10:00:00+00:00"},
            {"id": 2, "ejercicio_id": 1, "calificacion_obtenida": 100, "fecha_intento": "2026-11-02T10:00:00+00:00"},
            {"id": 3, "ejercicio_id": 2, "calificacion_obtenida": "100.00", "fecha_intento": "2026-11-02T10:00:00+00:00"},
            {"id": 4, "ejercicio_id": 2, "calificacion_obtenida": 0, "fecha_intento": "2026-11-01T10:00:00+00:00"},
            {"id": 5, "ejercicio_id": 9, "calificacion_obtenida": 0, "fecha_intento": "2026-11-03T10:00:00+00:00"},
        ]
        agrupados = service.agrupar_intentos(intentos, EJERCICIOS)
        self.assertEqual(set(agrupados), {1, 2})
        self.assertEqual(service.calificacion_final(agrupados), 100.0)

    def test_redondeo_y_vacio(self):
        agrupados = {
            1: [{"id": 1, "calificacion_obtenida": 100}],
            2: [{"id": 2, "calificacion_obtenida": 0}],
            3: [{"id": 3, "calificacion_obtenida": 0}],
        }
        self.assertEqual(service.calificacion_final(agrupados), 33.33)
        self.assertEqual(service.calificacion_final({}), 0.0)


class SinDiagnosticoTests(SimpleTestCase):
    def test_quita_evaluacion_tecnica(self):
        self.assertEqual([e["id"] for e in cursos_service.sin_diagnostico(EJERCICIOS)], [1, 2])
        self.assertEqual(cursos_service.sin_diagnostico(None), [])

    @mock.patch.object(cursos_service, "repository")
    def test_curso_y_leccion(self, repo):
        repo.buscar_curso.return_value = {"id": 1, "temas": [{"id": 5, "ejercicios": list(EJERCICIOS)}]}
        repo.buscar_tema.return_value = {"id": 5, "ejercicios": list(EJERCICIOS)}
        curso = cursos_service.obtener_curso(1)
        leccion = cursos_service.obtener_leccion(5)
        self.assertEqual([e["id"] for e in curso["temas"][0]["ejercicios"]], [1, 2])
        self.assertEqual([e["id"] for e in leccion["ejercicios"]], [1, 2])


@mock.patch.object(service.ganchos, "al_completar_curso")
@mock.patch.object(service.ganchos, "al_evaluar_modulo")
@mock.patch.object(service, "repository")
class EvaluarModuloTests(SimpleTestCase):
    def _configurar(self, repo, estados=None, completados=1, total_temas=2, inscripcion="activo"):
        estados = estados or {}
        repo.buscar_tema.return_value = {"id": 5, "curso_id": 3, "orden": 1}
        repo.listar_ejercicios_de_temas.return_value = EJERCICIOS
        repo.listar_opciones_de_ejercicios.return_value = OPCIONES
        repo.estados_tema.side_effect = lambda u, t: estados.get(t, [])
        repo.buscar_tema_por_orden.return_value = {"id": 6}
        repo.listar_temas_de_curso.return_value = [{"id": i} for i in range(5, 5 + total_temas)]
        repo.contar_temas_completados.return_value = completados
        repo.buscar_inscripcion.return_value = {"id": 1, "estado": inscripcion}
        repo.listar_intentos.return_value = [
            {"id": 1, "ejercicio_id": 1, "calificacion_obtenida": 100, "fecha_intento": "2026-11-01"},
            {"id": 2, "ejercicio_id": 2, "calificacion_obtenida": 50, "fecha_intento": "2026-11-01"},
        ]

    def _datos(self, respuestas):
        return {"usuario_id": "u-1", "tema_id": "5", "respuestas": respuestas, "tiempo_resolucion_segundos": 10}

    def test_aprobar_llama_al_gancho(self, repo, gancho, gancho_curso):
        self._configurar(repo)
        salida = service.evaluar_modulo(self._datos([{"opcion_id": 11}, {"opcion_id": 21}]))

        self.assertEqual(
            set(salida), {"calificacion", "aprobado", "requiere_refuerzo", "retroalimentacion"}
        )
        self.assertEqual((salida["calificacion"], salida["aprobado"], salida["requiere_refuerzo"]), (100, True, False))
        gancho.assert_called_once_with(
            "u-1",
            {"id": 5, "curso_id": 3, "orden": 1},
            100,
            [{"ejercicio_id": 1, "es_correcta": True}, {"ejercicio_id": 2, "es_correcta": True}],
            True,
        )
        repo.marcar_estado_tema.assert_any_call("u-1", 5, "completado")
        repo.marcar_estado_tema.assert_any_call("u-1", 6, "desbloqueado")
        repo.guardar_avance_curso.assert_called_once_with("u-1", 3, 50)
        repo.completar_curso.assert_not_called()
        gancho_curso.assert_not_called()

    def test_suspender_llama_al_gancho_sin_aprobar(self, repo, gancho, _):
        self._configurar(repo)
        salida = service.evaluar_modulo(self._datos([{"opcion_id": 12}]))
        self.assertEqual((salida["calificacion"], salida["aprobado"], salida["requiere_refuerzo"]), (0, False, True))
        gancho.assert_called_once_with(
            "u-1",
            {"id": 5, "curso_id": 3, "orden": 1},
            0,
            [{"ejercicio_id": 1, "es_correcta": False}, {"ejercicio_id": 2, "es_correcta": False}],
            False,
        )
        repo.marcar_estado_tema.assert_called_once_with("u-1", 5, "actividades_de_refuerzo")
        self.assertEqual(len(repo.registrar_intentos.call_args.args[0]), 2)

    def test_suspender_un_completado_no_lo_toca(self, repo, *_):
        self._configurar(repo, estados={5: ["completado"]})
        service.evaluar_modulo(self._datos([{"opcion_id": 12}]))
        repo.marcar_estado_tema.assert_not_called()

    def test_desbloquear_no_pisa_un_siguiente_completado(self, repo, *_):
        self._configurar(repo, estados={5: ["completado"], 6: ["completado"]})
        service.evaluar_modulo(self._datos([{"opcion_id": 11}, {"opcion_id": 21}]))
        repo.marcar_estado_tema.assert_not_called()

    def test_aprobar_en_refuerzo_lo_completa(self, repo, *_):
        self._configurar(repo, estados={5: ["actividades_de_refuerzo"]})
        service.evaluar_modulo(self._datos([{"opcion_id": 11}, {"opcion_id": 21}]))
        repo.marcar_estado_tema.assert_any_call("u-1", 5, "completado")

    def test_completar_curso(self, repo, gancho, gancho_curso):
        self._configurar(repo, completados=2, total_temas=2)
        service.evaluar_modulo(self._datos([{"opcion_id": 11}, {"opcion_id": 21}]))
        repo.listar_intentos.assert_called_once_with("u-1", [1, 2])
        args, kwargs = repo.completar_curso.call_args
        self.assertEqual(args, ("u-1", 3))
        self.assertEqual(kwargs["calificacion_final"], 75.0)
        self.assertTrue(kwargs["completado_en"])
        gancho_curso.assert_called_once_with("u-1", 3, 75.0)

    def test_curso_ya_completado_no_se_repite(self, repo, gancho, gancho_curso):
        self._configurar(repo, completados=2, total_temas=2, inscripcion="completado")
        service.evaluar_modulo(self._datos([{"opcion_id": 11}, {"opcion_id": 21}]))
        repo.completar_curso.assert_not_called()
        gancho_curso.assert_not_called()

    def test_tema_id_no_entero_es_400(self, repo, *_):
        with self.assertRaises(ValidationError):
            service.evaluar_modulo({"usuario_id": "u-1", "tema_id": "abc", "respuestas": [{"opcion_id": 1}]})
        repo.buscar_tema.assert_not_called()

    def test_modulo_sin_ejercicios_calificables_es_400(self, repo, gancho, _):
        self._configurar(repo)
        repo.listar_ejercicios_de_temas.return_value = [EJERCICIOS[2]]
        with self.assertRaises(ValidationError):
            service.evaluar_modulo(self._datos([{"opcion_id": 91}]))
        gancho.assert_not_called()


class VistaTests(SimpleTestCase):
    def _pedir(self, cuerpo, token=None):
        import json

        from django.test import Client

        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        return Client().post(
            "/api/evaluaciones/evaluar-modulo", data=json.dumps(cuerpo), content_type="application/json", **extra
        )

    def test_sin_token_es_401(self):
        self.assertEqual(self._pedir({}).status_code, 401)

    @mock.patch("core.auth._verify_token", return_value={"id": "u-1"})
    def test_otro_usuario_es_403(self, _):
        r = self._pedir({"usuario_id": "u-2", "tema_id": 1, "respuestas": [{"opcion_id": 1}]}, token="t")
        self.assertEqual(r.status_code, 403)
