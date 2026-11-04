"""Mapa de URLs de la API PyGo.

Replica exactamente las rutas que servía Express en `src/index.js`, sin barra
final, para que el frontend React no necesite ningún cambio.
"""

from django.urls import path

from core.http import json_response, not_found, server_error
from django.views.decorators.csrf import csrf_exempt

from features.adaptativo import views as adaptativo
from features.autenticacion import views as autenticacion
from features.cold_start import views as cold_start
from features.cursos import views as cursos
from features.evaluaciones import views as evaluaciones
from features.usuarios import views as usuarios


@csrf_exempt
def health(request):
    """GET /health — comprobación de vida, sin autenticación."""
    return json_response({"status": "ok", "server": "PyGo Django API running"})


urlpatterns = [
    # Autenticación (pública: es la puerta de entrada)
    path("api/auth/registro", autenticacion.registro),
    path("api/auth/login", autenticacion.login),

    # Evaluación inicial
    path("api/cold-start/evaluar", cold_start.evaluar),

    # Cursos. La ruta de lecciones va primero para que no la capture <curso_id>.
    path("api/cursos/lecciones/<str:leccion_id>", cursos.detalle_leccion),
    path("api/cursos/<str:curso_id>", cursos.detalle_curso),
    path("api/cursos", cursos.listar_cursos),

    # Alias de lecciones que montaba Express con app.use('/api/lecciones', ...)
    path("api/lecciones/<str:leccion_id>", cursos.detalle_leccion),

    # Evaluaciones y motor adaptativo
    path("api/evaluaciones/evaluar-modulo", evaluaciones.evaluar_modulo),
    path("api/adaptativo/estado/<str:usuario_id>", adaptativo.estado),

    # Perfil de usuario
    path("api/usuarios/configuracion/<str:usuario_id>", usuarios.configuracion),

    # Salud del servicio
    path("health", health),
]

handler404 = not_found
handler500 = server_error
