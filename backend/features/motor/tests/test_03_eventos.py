"""Tests del paquete 03: validación de eventos, registro, límites e inscripción. Sin red."""

import copy
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest import mock

from django.core.cache import cache
from django.test import Client, SimpleTestCase

from core.errors import DataAccessError, ForbiddenError, NotFoundError, ValidationError
from features.motor.eventos import limite, service as eventos_service
from features.motor.eventos.validacion import TIPOS, es_duplicado, validar_evento
from features.motor.inscripcion import service as inscripcion_service

USUARIO = "11111111-1111-1111-1111-111111111111"
OTRO = "22222222-2222-2222-2222-222222222222"
REC = "r-5c1e0a2b-1234"
AHORA = datetime(2026, 11, 20, 16, 20, tzinfo=timezone.utc)


def _valido(tipo):
    """Cuerpo mínimo válido para cada tipo del catálogo."""
    _, objeto_tipo, rango = TIPOS[tipo]
    cuerpo = {"tipo": tipo}
    if objeto_tipo in ("curso", "tema"):
        cuerpo["objeto_id"] = 5
    if rango is not None:
        cuerpo["valor"] = rango[1]
    if objeto_tipo == "recomendacion":
        cuerpo["datos"] = {"recomendacion_id": REC, "posicion": 1}
    return cuerpo


class ValidarEventoTests(SimpleTestCase):
    def test_todos_los_tipos_validos(self):
        for tipo, (origen, objeto_tipo, _) in TIPOS.items():
            with self.subTest(tipo=tipo):
                evento = validar_evento(_valido(tipo), USUARIO, "servidor")
                self.assertEqual(evento["tipo"], tipo)
                self.assertEqual(evento["usuario_id"], USUARIO)
                self.assertEqual(evento["objeto_tipo"], objeto_tipo)
                if origen == "cliente":
                    self.assertEqual(validar_evento(_valido(tipo), USUARIO, "cliente")["tipo"], tipo)

    def test_tipo_desconocido(self):
        for tipo in ("inventado", None, 3, ["curso_vista"]):
            with self.subTest(tipo=tipo), self.assertRaises(ValidationError):
                validar_evento({"tipo": tipo}, USUARIO, "cliente")

    def test_cliente_no_puede_enviar_tipos_del_servidor(self):
        for tipo, (origen, _, _) in TIPOS.items():
            if origen != "servidor":
                continue
            with self.subTest(tipo=tipo):
                with self.assertRaisesMessage(ValidationError, "Este evento solo lo registra el servidor"):
                    validar_evento(_valido(tipo), USUARIO, "cliente")

    def test_otro_usuario_prohibido(self):
        with self.assertRaises(ForbiddenError):
            validar_evento({**_valido("curso_vista"), "usuario_id": OTRO}, USUARIO, "cliente")

    def test_usuario_ausente_es_el_autenticado(self):
        self.assertEqual(validar_evento(_valido("busqueda"), USUARIO, "cliente")["usuario_id"], USUARIO)
        self.assertEqual(
            validar_evento({**_valido("busqueda"), "usuario_id": USUARIO}, USUARIO, "cliente")["usuario_id"],
            USUARIO,
        )

    def test_valor_fuera_de_rango_o_ausente(self):
        for valor in (0, 6, 5.5, None, "3", True, float("nan"), float("inf")):
            with self.subTest(valor=valor), self.assertRaises(ValidationError):
                validar_evento({"tipo": "valoracion", "objeto_id": 1, "valor": valor}, USUARIO, "cliente")
        self.assertEqual(
            validar_evento({"tipo": "valoracion", "objeto_id": 1, "valor": 4}, USUARIO, "cliente")["valor"], 4
        )

    def test_valor_sin_rango_acotado(self):
        self.assertIsNone(validar_evento(_valido("busqueda"), USUARIO, "cliente")["valor"])
        with self.assertRaises(ValidationError):
            validar_evento({**_valido("busqueda"), "valor": 10 ** 9}, USUARIO, "cliente")

    def test_recomendacion_id_invalido(self):
        for rid in (None, "x-12345678", "r-ABCDEF12", "r-123", "r-" + "a" * 41, "r-12345678\n", 7):
            with self.subTest(rid=rid), self.assertRaises(ValidationError):
                validar_evento(
                    {"tipo": "recomendacion_clic", "datos": {"recomendacion_id": rid}}, USUARIO, "servidor"
                )

    def test_claves_extra_de_datos_descartadas(self):
        evento = validar_evento(
            {"tipo": "curso_vista", "objeto_id": 3,
             "datos": {"origen": "catalogo", "recomendacion_id": REC, "intruso": 1}},
            USUARIO, "cliente",
        )
        self.assertEqual(evento["datos"], {"origen": "catalogo", "recomendacion_id": REC})
        self.assertEqual(
            validar_evento({"tipo": "curso_vista", "objeto_id": 3,
                            "datos": {"origen": "hackeo", "recomendacion_id": "malo"}},
                           USUARIO, "cliente")["datos"],
            {},
        )
        self.assertEqual(
            validar_evento({"tipo": "busqueda", "datos": {"texto": "a" * 300, "x": 1}}, USUARIO, "cliente")["datos"],
            {"texto": "a" * 100},
        )
        self.assertEqual(
            validar_evento({"tipo": "sesion_inicio", "datos": {"dispositivo": ["movil"]}}, USUARIO, "cliente")["datos"],
            {},
        )
        self.assertEqual(
            validar_evento({"tipo": "tema_abierto", "objeto_id": 2, "datos": {"x": 1}}, USUARIO, "cliente")["datos"],
            {},
        )

    def test_datos_del_servidor_libres_pero_acotados(self):
        evento = validar_evento({"tipo": "diagnostico", "valor": 0.5, "datos": {"nivel": "Intermedio"}},
                                USUARIO, "servidor")
        self.assertEqual(evento["datos"], {"nivel": "Intermedio"})
        with self.assertRaises(ValidationError):
            validar_evento({"tipo": "diagnostico", "valor": 0.5, "datos": {"x": "a" * 5000}}, USUARIO, "servidor")
        with self.assertRaises(ValidationError):
            validar_evento({"tipo": "diagnostico", "valor": 0.5, "datos": {"x": object()}}, USUARIO, "servidor")

    def test_datos_no_objeto(self):
        with self.assertRaises(ValidationError):
            validar_evento({"tipo": "busqueda", "datos": ["texto"]}, USUARIO, "cliente")

    def test_fecha_del_cuerpo_ignorada(self):
        evento = validar_evento({**_valido("busqueda"), "fecha": "2000-01-01T00:00:00Z"}, USUARIO, "cliente")
        self.assertNotIn("fecha", evento)

    def test_objeto_tipo_forzado(self):
        evento = validar_evento({**_valido("curso_vista"), "objeto_tipo": "tema"}, USUARIO, "cliente")
        self.assertEqual(evento["objeto_tipo"], "curso")
        self.assertIsNone(validar_evento({"tipo": "busqueda", "objeto_tipo": "x"}, USUARIO, "cliente")["objeto_tipo"])

    def test_ids_enteros_positivos(self):
        for campo in ("objeto_id", "curso_id"):
            for valor in (0, -1, "3", 2.0, True):
                with self.subTest(campo=campo, valor=valor), self.assertRaises(ValidationError):
                    validar_evento({**_valido("curso_vista"), campo: valor}, USUARIO, "cliente")

    def test_sesion_id(self):
        uuid = "0b6f6c1e-2c3d-4e5f-8a9b-0c1d2e3f4a5b"
        self.assertEqual(validar_evento({**_valido("busqueda"), "sesion_id": uuid}, USUARIO, "cliente")["sesion_id"], uuid)
        for malo in ("a" * 41, "con espacio", "", "abc\n", 5):
            with self.subTest(sesion_id=malo), self.assertRaises(ValidationError):
                validar_evento({**_valido("busqueda"), "sesion_id": malo}, USUARIO, "cliente")

    def test_no_muta_la_entrada(self):
        cuerpo = {"tipo": "curso_vista", "objeto_id": 3, "objeto_tipo": "tema", "fecha": "x",
                  "datos": {"origen": "catalogo", "intruso": 1}}
        original = copy.deepcopy(cuerpo)
        evento = validar_evento(cuerpo, USUARIO, "cliente")
        self.assertEqual(cuerpo, original)
        self.assertIsNot(evento["datos"], cuerpo["datos"])

    def test_cuerpo_no_objeto(self):
        with self.assertRaises(ValidationError):
            validar_evento(["curso_vista"], USUARIO, "cliente")


class EsDuplicadoTests(SimpleTestCase):
    def _evento(self, segundos=0, **extra):
        return {"usuario_id": USUARIO, "tipo": "curso_vista", "objeto_id": 3,
                "datos": {}, "fecha": AHORA + timedelta(seconds=segundos), **extra}

    def test_dentro_de_la_ventana(self):
        self.assertTrue(es_duplicado(self._evento(), [self._evento(-0.5)]))

    def test_fuera_de_la_ventana(self):
        self.assertFalse(es_duplicado(self._evento(), [self._evento(-1.5)]))

    def test_otro_objeto_o_recomendacion(self):
        self.assertFalse(es_duplicado(self._evento(), [self._evento(-0.2, objeto_id=4)]))
        self.assertFalse(es_duplicado(self._evento(datos={"recomendacion_id": REC}), [self._evento(-0.2)]))
        self.assertFalse(es_duplicado(self._evento(), [self._evento(-0.2, usuario_id=OTRO)]))
        self.assertFalse(es_duplicado(self._evento(), []))


class RegistrarTests(SimpleTestCase):
    def setUp(self):
        reloj = mock.patch.object(eventos_service, "_ahora", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)

    def test_registrar_cliente_inserta(self):
        with mock.patch.object(eventos_service.repository, "recientes", return_value=[]) as recientes, \
                mock.patch.object(eventos_service.repository, "insertar",
                                  return_value={"id": 7, "tipo": "curso_vista", "fecha": AHORA}) as insertar:
            resultado = eventos_service.registrar_cliente({"tipo": "curso_vista", "objeto_id": 3}, {"id": USUARIO})
        self.assertEqual(resultado, {"id": 7, "tipo": "curso_vista", "fecha": AHORA})
        recientes.assert_called_once_with(USUARIO, "curso_vista", AHORA - timedelta(seconds=1))
        insertado = insertar.call_args.args[0]
        self.assertEqual(insertado["fecha"], AHORA)
        self.assertEqual(insertado["usuario_id"], USUARIO)

    def test_registrar_cliente_descarta_doble_clic(self):
        previo = {"id": 6, "usuario_id": USUARIO, "tipo": "curso_vista", "objeto_id": 3, "datos": {},
                  "fecha": AHORA - timedelta(milliseconds=300)}
        with mock.patch.object(eventos_service.repository, "recientes", return_value=[previo]), \
                mock.patch.object(eventos_service.repository, "insertar") as insertar:
            resultado = eventos_service.registrar_cliente({"tipo": "curso_vista", "objeto_id": 3}, {"id": USUARIO})
        insertar.assert_not_called()
        self.assertEqual(resultado, {"id": 6, "tipo": "curso_vista", "fecha": previo["fecha"]})

    def test_registrar_servidor(self):
        with mock.patch.object(eventos_service.repository, "insertar") as insertar:
            self.assertIsNone(eventos_service.registrar_servidor(
                USUARIO, "curso_completado", objeto_tipo="curso", objeto_id=1, curso_id=1, valor=92.5))
        self.assertEqual(insertar.call_args.args[0], {
            "usuario_id": USUARIO, "tipo": "curso_completado", "objeto_tipo": "curso", "objeto_id": 1,
            "curso_id": 1, "valor": 92.5, "datos": {}, "sesion_id": None, "fecha": AHORA,
        })

    def test_registrar_servidor_lanza_si_no_es_valido(self):
        with mock.patch.object(eventos_service.repository, "insertar") as insertar:
            with self.assertRaises(ValidationError):
                eventos_service.registrar_servidor(USUARIO, "inventado")
        insertar.assert_not_called()


class LimiteTests(SimpleTestCase):
    def test_ventana_deslizante(self):
        permitido, marcas = limite.consumir([0.0, 10.0, 59.0], 61.0, 3, 60)
        self.assertTrue(permitido)
        self.assertEqual(marcas, [10.0, 59.0, 61.0])
        permitido, marcas = limite.consumir([10.0, 20.0, 30.0], 40.0, 3, 60)
        self.assertFalse(permitido)
        self.assertEqual(marcas, [10.0, 20.0, 30.0])


def _verificar_falso(token):
    return {"id": USUARIO}


class VistasTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)

    def _post(self, ruta, cuerpo, token="t", crudo=None):
        extra = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
        datos = crudo if crudo is not None else json.dumps(cuerpo)
        return Client().post(ruta, data=datos, content_type="application/json", **extra)

    def test_401_sin_token(self):
        with mock.patch("core.auth._verify_token") as verificar:
            self.assertEqual(self._post("/api/eventos", {"tipo": "busqueda"}, token=None).status_code, 401)
            self.assertEqual(self._post("/api/cursos/1/inscripcion", {}, token=None).status_code, 401)
        verificar.assert_not_called()

    def test_403_si_el_cuerpo_nombra_a_otro(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(eventos_service.repository, "insertar") as insertar:
            r = self._post("/api/eventos", {"tipo": "busqueda", "usuario_id": OTRO})
        self.assertEqual(r.status_code, 403)
        insertar.assert_not_called()

    def test_400_si_supera_8_kb(self):
        crudo = json.dumps({"tipo": "busqueda", "datos": {"texto": "a" * 9000}})
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(eventos_service, "registrar_cliente") as registrar:
            r = self._post("/api/eventos", None, crudo=crudo)
        self.assertEqual(r.status_code, 400)
        registrar.assert_not_called()

    def test_400_si_el_cliente_envia_un_tipo_del_servidor(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso):
            r = self._post("/api/eventos", {"tipo": "curso_completado", "objeto_id": 1, "valor": 100})
        self.assertEqual(r.status_code, 400)

    def test_201_con_el_evento(self):
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(eventos_service.repository, "recientes", return_value=[]), \
                mock.patch.object(eventos_service.repository, "insertar",
                                  return_value={"id": 9, "tipo": "busqueda", "fecha": AHORA}):
            r = self._post("/api/eventos", {"tipo": "busqueda", "datos": {"texto": "bucles"}})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), {"success": True,
                                    "evento": {"id": 9, "tipo": "busqueda", "fecha": "2026-11-20T16:20:00Z"}})

    def test_429_en_el_evento_121_del_minuto(self):
        resumen = {"id": 1, "tipo": "busqueda", "fecha": AHORA}
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(eventos_service, "registrar_cliente", return_value=resumen) as registrar:
            codigos = [self._post("/api/eventos", {"tipo": "busqueda"}).status_code for _ in range(121)]
        self.assertEqual(codigos[:120], [201] * 120)
        self.assertEqual(codigos[120], 429)
        self.assertEqual(registrar.call_count, 120)

    def test_429_codigo(self):
        with mock.patch.object(limite, "MAX_EVENTOS_POR_MINUTO", 0), \
                mock.patch("core.auth._verify_token", side_effect=_verificar_falso):
            r = self._post("/api/eventos", {"tipo": "busqueda"})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["code"], "RATE_LIMITED")

    def test_inscripcion_201_y_luego_200(self):
        inscripcion = {"curso_id": 1, "estado": "activo", "porcentaje_avance_global": 0.0,
                       "calificacion_final": None, "fecha_inscripcion": AHORA, "completado_en": None,
                       "origen": "catalogo"}
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso), \
                mock.patch.object(inscripcion_service, "inscribir_o_recuperar",
                                  side_effect=[(inscripcion, True), (inscripcion, False)]) as inscribir:
            primera = self._post("/api/cursos/1/inscripcion", {"origen": "dashboard", "recomendacion_id": REC})
            segunda = self._post("/api/cursos/1/inscripcion", {})
        self.assertEqual(primera.status_code, 201)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual((primera.json()["nueva"], segunda.json()["nueva"]), (True, False))
        self.assertEqual(primera.json()["inscripcion"]["fecha_inscripcion"], "2026-11-20T16:20:00Z")
        self.assertEqual(inscribir.call_args_list[0], mock.call(USUARIO, "1", "dashboard", REC))
        self.assertEqual(inscribir.call_args_list[1], mock.call(USUARIO, "1", None, None))


def _catalogo():
    return {"cursos": {
        1: {"id": 1, "publicado": True, "temas": [{"id": 10, "curso_id": 1, "orden": 1},
                                                    {"id": 11, "curso_id": 1, "orden": 2}]},
        2: {"id": 2, "publicado": True, "temas": []},
    }}


FILA = {"curso_id": 1, "estado": "activo", "porcentaje_avance_global": 0, "calificacion_final": None,
        "fecha_inscripcion": "2026-11-20T16:20:00.12345+00:00", "completado_en": None, "origen": "catalogo"}


class InscribirTests(SimpleTestCase):
    def setUp(self):
        parches = {
            "catalogo": mock.patch.object(inscripcion_service, "cargar_catalogo", side_effect=_catalogo),
            "buscar": mock.patch.object(inscripcion_service.repository, "buscar", return_value=None),
            "insertar": mock.patch.object(inscripcion_service.repository, "insertar", return_value=FILA),
            "tiene_fila": mock.patch.object(inscripcion_service.repository, "tiene_fila_tema", return_value=False),
            "desbloquear": mock.patch.object(inscripcion_service.repository, "desbloquear_tema"),
            "evento": mock.patch.object(inscripcion_service.eventos, "registrar_servidor"),
            "aceptada": mock.patch.object(inscripcion_service.registro, "marcar_aceptada"),
        }
        self.m = {nombre: p.start() for nombre, p in parches.items()}
        for p in parches.values():
            self.addCleanup(p.stop)

    def test_inscripcion_nueva(self):
        inscripcion, nueva = inscripcion_service.inscribir_o_recuperar(USUARIO, "1", None, None)
        self.assertTrue(nueva)
        self.assertEqual(inscripcion["curso_id"], 1)
        self.assertEqual(inscripcion["porcentaje_avance_global"], 0.0)
        self.assertEqual(inscripcion["fecha_inscripcion"], datetime(2026, 11, 20, 16, 20, 0, 123450, tzinfo=timezone.utc))
        self.m["insertar"].assert_called_once_with({
            "usuario_id": USUARIO, "curso_id": 1, "estado": "activo",
            "porcentaje_avance_global": 0, "origen": "catalogo",
        })
        self.m["desbloquear"].assert_called_once_with(USUARIO, 10)
        self.m["evento"].assert_called_once_with(
            USUARIO, "curso_inscripcion", objeto_tipo="curso", objeto_id=1, curso_id=1,
            datos={"origen": "catalogo"},
        )
        self.m["aceptada"].assert_not_called()

    def test_idempotente(self):
        self.m["buscar"].return_value = {**FILA, "porcentaje_avance_global": "40.00"}
        inscripcion, nueva = inscripcion_service.inscribir_o_recuperar(USUARIO, 1, "dashboard", REC)
        self.assertFalse(nueva)
        self.assertEqual(inscripcion["porcentaje_avance_global"], 40.0)
        for nombre in ("insertar", "desbloquear", "evento", "aceptada"):
            self.m[nombre].assert_not_called()
        self.assertEqual(inscripcion_service.inscribir(USUARIO, 1, None, None), inscripcion)

    def test_con_recomendacion(self):
        inscripcion_service.inscribir_o_recuperar(USUARIO, 1, "recomendacion", REC)
        self.assertEqual(self.m["insertar"].call_args.args[0]["recomendacion_id"], REC)
        self.assertEqual(self.m["evento"].call_args.kwargs["datos"], {"origen": "recomendacion", "recomendacion_id": REC})
        self.m["aceptada"].assert_called_once_with(REC, USUARIO)

    def test_recomendacion_mal_formada_se_ignora(self):
        inscripcion_service.inscribir_o_recuperar(USUARIO, 1, "recomendacion", "r-NOPE")
        self.assertNotIn("recomendacion_id", self.m["insertar"].call_args.args[0])
        self.m["aceptada"].assert_not_called()

    def test_marcar_aceptada_pendiente_no_rompe(self):
        self.m["aceptada"].side_effect = NotImplementedError("pendiente: paquete 08")
        _, nueva = inscripcion_service.inscribir_o_recuperar(USUARIO, 1, None, REC)
        self.assertTrue(nueva)

    def test_fallo_del_evento_no_rompe(self):
        self.m["evento"].side_effect = DataAccessError("caído")
        with self.assertLogs("features.motor.inscripcion.service", level="ERROR"):
            _, nueva = inscripcion_service.inscribir_o_recuperar(USUARIO, 1, None, None)
        self.assertTrue(nueva)

    def test_no_toca_el_primer_tema_si_ya_tiene_fila(self):
        self.m["tiene_fila"].return_value = True
        inscripcion_service.inscribir_o_recuperar(USUARIO, 1, None, None)
        self.m["desbloquear"].assert_not_called()

    def test_curso_sin_temas(self):
        inscripcion_service.inscribir_o_recuperar(USUARIO, 2, None, None)
        self.m["tiene_fila"].assert_not_called()

    def test_curso_desconocido_404(self):
        for curso_id in (99, "99", "abc", "0", "-1", "١"):
            with self.subTest(curso_id=curso_id), self.assertRaises(NotFoundError):
                inscripcion_service.inscribir_o_recuperar(USUARIO, curso_id, None, None)
        self.m["buscar"].assert_not_called()

    def test_origen_invalido(self):
        for origen in ("hackeo", ["catalogo"], 3):
            with self.subTest(origen=origen), self.assertRaises(ValidationError):
                inscripcion_service.inscribir_o_recuperar(USUARIO, 1, origen, None)
        self.m["insertar"].assert_not_called()

    def test_carrera_simultanea_devuelve_la_existente(self):
        self.m["insertar"].side_effect = DataAccessError("duplicado", upstream_code="23505")
        self.m["buscar"].side_effect = [None, FILA]
        inscripcion, nueva = inscripcion_service.inscribir_o_recuperar(USUARIO, 1, None, None)
        self.assertFalse(nueva)
        self.assertEqual(inscripcion["curso_id"], 1)
        self.m["evento"].assert_not_called()

    def test_vista_404_para_curso_desconocido(self):
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        with mock.patch("core.auth._verify_token", side_effect=_verificar_falso):
            r = Client().post("/api/cursos/99/inscripcion", data="{}", content_type="application/json",
                              HTTP_AUTHORIZATION="Bearer t")
        self.assertEqual(r.status_code, 404)
