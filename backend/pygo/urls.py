"""Mapa de URLs de la API PyGo.

Replica exactamente las rutas que servía Express en `src/index.js`, sin barra
final, para que el frontend React no necesite ningún cambio.
"""

from django.urls import path

from core.http import json_response, not_found, server_error
from django.views.decorators.csrf import csrf_exempt

from features.academico import views as academico
from features.adaptativo import views as adaptativo
from features.autenticacion import views as autenticacion
from features.cold_start import views as cold_start
from features.cursos import views as cursos
from features.evaluaciones import views as evaluaciones
from features.motor import areas_views as motor_areas
from features.motor import recomendaciones_views as motor_recomendaciones
from features.motor.eventos import views as motor_eventos
from features.motor.inscripcion import views as motor_inscripcion
from features.motor.perfil import views as motor_perfil
from features.usuarios import views as usuarios


@csrf_exempt
def health(request):
    """GET /health — comprobación de vida, sin autenticación."""
    return json_response({"status": "ok", "server": "PyGo Django API running"})


urlpatterns = [
    # Autenticación (pública: es la puerta de entrada)
    path("api/auth/registro", autenticacion.registro),
    path("api/auth/login", autenticacion.login),

    # Catálogos académicos (públicos: alimentan los desplegables del registro)
    path("api/centros", academico.listar_centros),
    path("api/carreras", academico.listar_carreras),

    # Evaluación inicial
    path("api/cold-start/preguntas", cold_start.preguntas),
    path("api/cold-start/evaluar", cold_start.evaluar),

    # Cursos. Lecciones e inscripción van primero para que no las capture <curso_id>.
    path("api/cursos/lecciones/<str:leccion_id>", cursos.detalle_leccion),
    path("api/cursos/<str:curso_id>/inscripcion", motor_inscripcion.inscribirse),
    path("api/cursos/<str:curso_id>", cursos.detalle_curso),
    path("api/cursos", cursos.listar_cursos),

    # Alias de lecciones que montaba Express con app.use('/api/lecciones', ...)
    path("api/lecciones/<str:leccion_id>", cursos.detalle_leccion),

    # Evaluaciones y motor adaptativo
    path("api/evaluaciones/evaluar-modulo", evaluaciones.evaluar_modulo),
    path("api/adaptativo/estado/<str:usuario_id>", adaptativo.estado),

    # Perfil de usuario
    path("api/usuarios/configuracion/<str:usuario_id>", usuarios.configuracion),

    # Motor de recomendación
    path("api/motor/areas", motor_areas.listar_areas),
    path("api/eventos", motor_eventos.registrar),
    path("api/perfil/<str:usuario_id>/intereses", motor_perfil.intereses),
    path("api/perfil/<str:usuario_id>", motor_perfil.detalle),
    path("api/recomendaciones/cursos", motor_recomendaciones.recomendaciones_cursos),
    path("api/retroalimentacion", motor_recomendaciones.retroalimentacion),

    # Salud del servicio
    path("health", health),
]

handler404 = not_found
handler500 = server_error
