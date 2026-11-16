-- metricas_en_linea.sql: métricas del motor de recomendación con datos reales (paquete 10).
--
-- SOLO LECTURA. Ninguna consulta modifica datos. Las ejecuta únicamente la
-- persona responsable, contra la base real, con un rol de solo lectura o desde
-- el editor SQL de Supabase. Ningún proceso automático (tests, órdenes de
-- gestión, la API) las lanza.
--
-- Uso: ejecuta las consultas de una en una (el editor de Supabase solo muestra
-- el resultado de la última). La primera línea pone la sesión en solo lectura:
-- si alguien pegara aquí un UPDATE por error, Postgres lo rechazaría.
--
-- Tablas: `recomendaciones` (una fila por curso recomendado; `estado` guarda
-- la última etapa: emitida -> mostrada -> clic -> aceptada, o descartada),
-- `eventos` (`recomendacion_clic` lleva `datos.recomendacion_id`) y
-- `usuario_cursos` (`origen` = de dónde vino la inscripción).
--
-- Ventana: las consultas sobre recomendaciones miran los últimos 30 días
-- (`interval '30 days'`); cámbiala en cada consulta si hace falta. Las de
-- inscripciones miran todo el histórico.
--
-- Interpretación: con grupos del tamaño de una clase, diferencias de unos
-- pocos puntos porcentuales son casi siempre ruido. Reporta siempre los
-- tamaños (n) junto a las tasas.

SET default_transaction_read_only = on;


-- 1. Tasa de clic, por motor y grupo (últimos 30 días) -------------------------
-- ¿Qué proporción de las recomendaciones que el alumno llegó a ver abrió?
-- Numerador: estado `clic` o `aceptada`, o `descartada` después de un clic
-- (hay un evento `recomendacion_clic` con su id). Denominador: recomendaciones
-- en `mostrada` o cualquier etapa posterior.

WITH clics AS (
  SELECT DISTINCT datos ->> 'recomendacion_id' AS recomendacion_id
  FROM public.eventos
  WHERE tipo = 'recomendacion_clic'
    AND fecha >= now() - interval '30 days'
)
SELECT r.motor,
       r.grupo,
       count(*) AS mostradas,
       count(*) FILTER (
         WHERE r.estado IN ('clic', 'aceptada')
            OR (r.estado = 'descartada' AND c.recomendacion_id IS NOT NULL)
       ) AS con_clic,
       round(
         count(*) FILTER (
           WHERE r.estado IN ('clic', 'aceptada')
              OR (r.estado = 'descartada' AND c.recomendacion_id IS NOT NULL)
         )::numeric / nullif(count(*), 0), 3
       ) AS tasa_clic
FROM public.recomendaciones r
LEFT JOIN clics c ON c.recomendacion_id = r.id
WHERE r.creada_en >= now() - interval '30 days'
  AND r.estado IN ('mostrada', 'clic', 'aceptada', 'descartada')
GROUP BY r.motor, r.grupo
ORDER BY r.motor, r.grupo;


-- 2. Tasa de aceptación, por motor y grupo (últimos 30 días) -------------------
-- ¿Qué proporción de las recomendaciones vistas terminó en inscripción?
-- `aceptada` ÷ recomendaciones en `mostrada` o posterior.

SELECT motor,
       grupo,
       count(*) AS mostradas,
       count(*) FILTER (WHERE estado = 'aceptada') AS aceptadas,
       round(count(*) FILTER (WHERE estado = 'aceptada')::numeric / nullif(count(*), 0), 3) AS tasa_aceptacion
FROM public.recomendaciones
WHERE creada_en >= now() - interval '30 days'
  AND estado IN ('mostrada', 'clic', 'aceptada', 'descartada')
GROUP BY motor, grupo
ORDER BY motor, grupo;


-- 3. Aporte por estrategia (últimos 30 días) -----------------------------------
-- ¿Las recomendaciones en las que interviene cada estrategia o regla
-- funcionan mejor o peor? Una recomendación cuenta para cada valor de su
-- `origen` ('regla:R02', 'contenido', 'colaborativo', 'modelo:aprobacion@…',
-- 'control:temario'), así que las filas no suman el total.

WITH clics AS (
  SELECT DISTINCT datos ->> 'recomendacion_id' AS recomendacion_id
  FROM public.eventos
  WHERE tipo = 'recomendacion_clic'
    AND fecha >= now() - interval '30 days'
),
vistas AS (
  SELECT r.id, r.estado, o.origen, c.recomendacion_id IS NOT NULL AS hubo_clic
  FROM public.recomendaciones r
  CROSS JOIN LATERAL jsonb_array_elements_text(r.origen) AS o(origen)
  LEFT JOIN clics c ON c.recomendacion_id = r.id
  WHERE r.creada_en >= now() - interval '30 days'
    AND r.estado IN ('mostrada', 'clic', 'aceptada', 'descartada')
)
SELECT origen,
       count(*) AS mostradas,
       round(count(*) FILTER (
         WHERE estado IN ('clic', 'aceptada') OR (estado = 'descartada' AND hubo_clic)
       )::numeric / nullif(count(*), 0), 3) AS tasa_clic,
       round(count(*) FILTER (WHERE estado = 'aceptada')::numeric / nullif(count(*), 0), 3) AS tasa_aceptacion
FROM vistas
GROUP BY origen
ORDER BY mostradas DESC, origen;


-- 4. Finalización según el origen de la inscripción ----------------------------
-- ¿Se terminan más los cursos que llegaron por una recomendación que los
-- elegidos en el catálogo? Las inscripciones recientes aún no han tenido
-- tiempo de terminarse: compara cohortes de la misma antigüedad si puedes.

SELECT coalesce(origen, 'sin_origen') AS origen,
       count(*) AS inscripciones,
       count(*) FILTER (WHERE estado = 'completado') AS completadas,
       count(*) FILTER (WHERE estado = 'activo') AS activas,
       count(*) FILTER (WHERE estado = 'abandonado') AS abandonadas,
       round(count(*) FILTER (WHERE estado = 'completado')::numeric / nullif(count(*), 0), 3) AS tasa_finalizacion
FROM public.usuario_cursos
GROUP BY coalesce(origen, 'sin_origen')
ORDER BY inscripciones DESC;


-- 5. Motivos de descarte (últimos 30 días) -------------------------------------
-- ¿Por qué descartan los alumnos las recomendaciones? (ya_lo_conozco,
-- no_me_interesa, no_es_mi_nivel, otro; `sin_motivo` si no eligieron ninguno.)

SELECT coalesce(motivo_descarte, 'sin_motivo') AS motivo,
       count(*) AS descartes,
       round(count(*)::numeric / nullif(sum(count(*)) OVER (), 0), 3) AS proporcion
FROM public.recomendaciones
WHERE estado = 'descartada'
  AND creada_en >= now() - interval '30 days'
GROUP BY coalesce(motivo_descarte, 'sin_motivo')
ORDER BY descartes DESC;


-- 6. Prueba A/B: aceptación por grupo con estadístico z (últimos 30 días) -----
-- ¿Acepta más recomendaciones el grupo `motor` que el grupo `control`
-- (orden del temario)? La unidad es el alumno, no la recomendación (las de un
-- mismo alumno no son independientes): proporción de alumnos que vieron al
-- menos una recomendación y aceptaron al menos una.
--
-- z = (p_motor − p_control) / sqrt(p·(1 − p)·(1/n_motor + 1/n_control)), con p
-- la proporción conjunta. |z| < 1.96 significa que la diferencia no es
-- significativa al 5 %. Ojo: con grupos del tamaño de una clase (decenas de
-- alumnos) solo diferencias grandes llegan a ser significativas; las pequeñas
-- son ruido, aunque una tasa parezca mejor que la otra. Con menos de ~10
-- aceptaciones por grupo la aproximación normal tampoco es fiable.

WITH por_alumno AS (
  SELECT grupo,
         usuario_id,
         bool_or(estado = 'aceptada') AS acepto
  FROM public.recomendaciones
  WHERE creada_en >= now() - interval '30 days'
    AND estado IN ('mostrada', 'clic', 'aceptada', 'descartada')
  GROUP BY grupo, usuario_id
),
grupos AS (
  SELECT grupo,
         count(*)::numeric AS n,
         count(*) FILTER (WHERE acepto)::numeric AS aceptaron
  FROM por_alumno
  GROUP BY grupo
),
ab AS (
  SELECT m.n AS n_motor, m.aceptaron AS aceptaron_motor,
         c.n AS n_control, c.aceptaron AS aceptaron_control,
         m.aceptaron / m.n AS p_motor,
         c.aceptaron / c.n AS p_control,
         (m.aceptaron + c.aceptaron) / (m.n + c.n) AS p_conjunta
  FROM grupos m
  CROSS JOIN grupos c
  WHERE m.grupo = 'motor' AND c.grupo = 'control'
)
SELECT n_motor, aceptaron_motor, round(p_motor, 3) AS p_motor,
       n_control, aceptaron_control, round(p_control, 3) AS p_control,
       round(p_motor - p_control, 3) AS diferencia,
       round(
         (p_motor - p_control)
         / nullif(sqrt(p_conjunta * (1 - p_conjunta) * (1 / n_motor + 1 / n_control)), 0),
         2
       ) AS z
FROM ab;


-- 7. Abandono según el origen de la inscripción --------------------------------
-- ¿Qué proporción de las inscripciones acaba abandonada (30 días sin
-- actividad, DIAS_PARA_ABANDONO), según de dónde vino?

SELECT coalesce(origen, 'sin_origen') AS origen,
       count(*) AS inscripciones,
       count(*) FILTER (WHERE estado = 'abandonado') AS abandonadas,
       round(count(*) FILTER (WHERE estado = 'abandonado')::numeric / nullif(count(*), 0), 3) AS tasa_abandono
FROM public.usuario_cursos
GROUP BY coalesce(origen, 'sin_origen')
ORDER BY inscripciones DESC;
