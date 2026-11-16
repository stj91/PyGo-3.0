"""Pruebas de la lógica pura de cursos. Sin red ni base de datos."""

from django.test import SimpleTestCase

from .service import combinar_avance


class CombinarAvanceTests(SimpleTestCase):
    CURSOS = [{"id": 1, "titulo": "A"}, {"id": 2, "titulo": "B"}, {"id": 3, "titulo": "C"}]

    def test_marca_inscritos_aunque_su_avance_sea_cero(self):
        avances = [{"curso_id": 1, "porcentaje_avance_global": 40}, {"curso_id": 2, "porcentaje_avance_global": 0}]
        resultado = {c["id"]: c for c in combinar_avance(self.CURSOS, avances)}
        self.assertEqual(
            {i: (c["inscrito"], c["porcentaje_avance_global"]) for i, c in resultado.items()},
            {1: (True, 40), 2: (True, 0), 3: (False, 0)},
        )

    def test_no_muta_la_entrada(self):
        combinar_avance(self.CURSOS, [{"curso_id": 1, "porcentaje_avance_global": 10}])
        self.assertNotIn("inscrito", self.CURSOS[0])
