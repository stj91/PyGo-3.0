"""Umbrales y pesos del motor (00-arquitectura.md §7).

Léelos siempre como `from features.motor import config` y `config.NOMBRE` en el
momento de usarlos: la evaluación (10) los sobrescribe temporalmente y un
nombre importado directamente no vería el cambio.
"""

MOTOR_VERSION = "hibrido-v1"
EXPERIMENTO = "motor-v1"
# Con el experimento apagado todos los alumnos reciben el motor; encenderlo
# envía la mitad al grupo de control (orden del temario) para medir el efecto.
EXPERIMENTO_ACTIVO = False
CATALOGO_CACHE_SEGUNDOS = 300

# Dominio (04)
ALFA_DOMINIO = 0.3
DOMINIO_DIAGNOSTICO_ACIERTO = 0.7
DOMINIO_DIAGNOSTICO_FALLO = 0.2
DOMINIO_INICIAL_POR_NIVEL = {"Principiante": 0.2, "Intermedio": 0.5, "Avanzado": 0.7}
DOMINIO_SIN_EVIDENCIA = 0.2
UMBRAL_NIVEL_INFERIDO = {"Avanzado": 0.75, "Intermedio": 0.45}
EVIDENCIAS_MIN_NIVEL_INFERIDO = 5
DIAS_PARA_ABANDONO = 30

# Intereses (02, 04)
PESO_INTERES_DECLARADO = 1.0
PESO_INTERES_OBJETIVO = 0.5
OBJETIVO_A_AREA = {
    "Aprobar materia universitaria de programación": "fundamentos",
    "Automatizar tareas o procesos cotidianos": "automatizacion",
    "Análisis de datos y Ciencia de Datos": "datos",
}
PESO_INTERES_INFERIDO_COMPLETADO = 0.5
PESO_INTERES_INFERIDO_VISTO = 0.2

# Calificación (02)
UMBRAL_APROBADO = 80          # el mismo que usa evaluaciones hoy
UMBRAL_REFUERZO = 70

# Reglas y filtros (05)
F02_DOMINIO_MINIMO = 0.6

# Colaborativo (06)
VALOR_INTERACCION = {"completado": 1.0, "activo": 0.6, "abandonado": 0.2}
BONO_CALIFICACION_ALTA = 0.2  # si calificacion_final >= 90
SOPORTE_MINIMO = 5

# Modelo (07)
MODELO_NOMBRE = "aprobacion"
UMBRAL_ETIQUETA_APROBO = 80
DOMINIO_SIN_EVIDENCIA_MODELO = 0.4

# Híbrido (08)
PESOS_ESTRATEGIA = {
    "nuevo":        {"reglas": 0.6, "contenido": 0.4, "colaborativo": 0.0, "modelo": 0.0},
    "con_historia": {"reglas": 0.4, "contenido": 0.3, "colaborativo": 0.3, "modelo": 0.0},
    "con_modelo":   {"reglas": 0.3, "contenido": 0.2, "colaborativo": 0.2, "modelo": 0.3},
}
MIN_CURSOS_COMPLETADOS_PARA_HISTORIA = 1
BONO_SIGUIENTE_EN_RUTA = 0.15
LAMBDA_DIVERSIDAD = 0.2
LIMITE_POR_DEFECTO = 3
LIMITE_MAXIMO = 8
MAX_CONTINUAR = 3
MINUTOS_ESTABILIDAD = 30      # reutiliza las últimas recomendaciones si no pasó nada relevante desde entonces
