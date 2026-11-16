-- 0008_motor_reglas.sql
--
-- Reglas iniciales del motor de recomendación (docs/motor/05-reglas-y-candidatos.md §5):
--   - F01–F03, filtros duros (se aplican en código, en features/motor/candidatos.py;
--     aquí solo se documentan y, F01/F02, se activan o desactivan con `activa`);
--   - R01–R06, reglas de recomendación que suman o restan puntos a un curso.
--
-- Requiere 0005 (tabla `reglas`).
--
-- Cada regla lleva en `descripcion` su enunciado en lenguaje llano y su
-- justificación pedagógica. `condicion` se evalúa sobre los hechos del alumno;
-- `accion.filtro`, sobre los hechos de cada curso candidato. El evaluador solo
-- conoce los operadores = != < <= > >= en contiene existe: el JSON nunca se
-- ejecuta como código.
--
-- Idempotente: INSERT ... ON CONFLICT (codigo) DO UPDATE, así reaplicarla tras
-- editar una regla corrige su contenido. `activa` NO se sobrescribe: si alguien
-- apagó una regla (por ejemplo F02), reaplicar la migración no la vuelve a
-- encender.
--
-- Formato de cada fila: (codigo, ambito, prioridad, condicion, accion, nombre,
-- descripcion). Los tests de features/motor/tests/test_05_reglas.py leen este
-- fichero y comprueban que coincide con sus reglas de ejemplo.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;

INSERT INTO public.reglas (codigo, ambito, prioridad, condicion, accion, nombre, descripcion)
VALUES
  ('F01', 'filtro', 100,
   '{}'::jsonb,
   '{}'::jsonb,
   'Prerrequisitos completados',
   'Un curso solo se recomienda si el alumno completó cada uno de sus prerrequisitos con al menos la calificación mínima. Por qué: el contenido de un curso se apoya en lo aprendido en los anteriores; saltarse esa base lleva a frustración y abandono.'),

  ('F02', 'filtro', 90,
   '{}'::jsonb,
   '{}'::jsonb,
   'Prerrequisito cubierto por nivel y dominio',
   'Un prerrequisito no completado cuenta como cumplido si el nivel del alumno es igual o superior al del curso requerido y su dominio de los conceptos de ese curso llega al mínimo configurado (F02_DOMINIO_MINIMO). Por qué: quien ya sabe algo no debería repetirlo para avanzar; la evidencia de dominio sustituye al trámite.'),

  ('F03', 'filtro', 100,
   '{}'::jsonb,
   '{}'::jsonb,
   'Sin cursos ya inscritos',
   'No se recomiendan cursos en los que el alumno ya está inscrito como activo o completado; los abandonados vuelven a ser candidatos. Siempre se aplica: esta fila solo lo documenta. Por qué: recomendar lo que ya se cursa no aporta nada; los cursos en marcha aparecen aparte, en Continúa.'),

  ('R01', 'recomendacion', 50,
   '{"ninguna": [{"campo": "cursos_completados", "op": "existe"}]}'::jsonb,
   '{"filtro": {"campo": "curso.dificultad", "op": "=", "valor": 1}, "puntos": 3, "explicacion": "Es un buen punto de partida para empezar con Python."}'::jsonb,
   'Punto de partida',
   'Si el alumno aún no ha completado ningún curso, se favorecen los cursos de dificultad 1. Por qué: empezar con éxitos tempranos y alcanzables refuerza la motivación y construye la base del resto de la ruta.'),

  ('R02', 'recomendacion', 90,
   '{"campo": "cursos_completados", "op": "existe"}'::jsonb,
   '{"filtro": {"campo": "curso.es_siguiente_en_ruta", "op": "=", "valor": true}, "puntos": 4, "explicacion": "Es el siguiente paso después de {curso.prerrequisito_titulo}."}'::jsonb,
   'Siguiente en la ruta',
   'Si el alumno ha completado algún curso, se favorecen los cursos cuyos prerrequisitos están todos aprobados. Por qué: continuar justo donde se dejó aprovecha lo recién aprendido mientras está fresco y mantiene una progresión coherente.'),

  ('R03a', 'recomendacion', 60,
   '{"campo": "nivel", "op": "=", "valor": "Principiante"}'::jsonb,
   '{"filtro": {"campo": "curso.nivel", "op": "=", "valor": "Principiante"}, "puntos": 2, "explicacion": "Encaja con tu nivel {nivel}."}'::jsonb,
   'Encaja con el nivel (Principiante)',
   'Si el nivel del alumno es Principiante, se favorecen los cursos de nivel Principiante. Por qué: un reto ajustado al nivel (ni trivial ni inalcanzable) es el que más aprendizaje produce.'),

  ('R03b', 'recomendacion', 60,
   '{"campo": "nivel", "op": "=", "valor": "Intermedio"}'::jsonb,
   '{"filtro": {"campo": "curso.nivel", "op": "=", "valor": "Intermedio"}, "puntos": 2, "explicacion": "Encaja con tu nivel {nivel}."}'::jsonb,
   'Encaja con el nivel (Intermedio)',
   'Si el nivel del alumno es Intermedio, se favorecen los cursos de nivel Intermedio. Por qué: un reto ajustado al nivel (ni trivial ni inalcanzable) es el que más aprendizaje produce.'),

  ('R03c', 'recomendacion', 60,
   '{"campo": "nivel", "op": "=", "valor": "Avanzado"}'::jsonb,
   '{"filtro": {"campo": "curso.nivel", "op": "=", "valor": "Avanzado"}, "puntos": 2, "explicacion": "Encaja con tu nivel {nivel}."}'::jsonb,
   'Encaja con el nivel (Avanzado)',
   'Si el nivel del alumno es Avanzado, se favorecen los cursos de nivel Avanzado. Por qué: un reto ajustado al nivel (ni trivial ni inalcanzable) es el que más aprendizaje produce.'),

  ('R04', 'recomendacion', 70,
   '{"campo": "intereses", "op": "existe"}'::jsonb,
   '{"filtro": {"campo": "curso.coincide_interes", "op": "=", "valor": true}, "puntos": 2, "explicacion": "Coincide con tu interés en {curso.area_nombre}."}'::jsonb,
   'Coincide con sus intereses',
   'Si el alumno tiene intereses, se favorecen los cursos que tratan alguno de esos temas. Por qué: aprender sobre lo que a uno le importa aumenta la motivación intrínseca y la persistencia.'),

  ('R05', 'recomendacion', 80,
   '{"campo": "tiene_refuerzo", "op": "=", "valor": true}'::jsonb,
   '{"filtro": {"campo": "curso.prerrequisito_en_refuerzo", "op": "=", "valor": true}, "puntos": -3, "explicacion": "Te conviene terminar el repaso de {curso.prerrequisito_refuerzo_titulo} antes."}'::jsonb,
   'Repaso pendiente',
   'Si el alumno tiene módulos en refuerzo, se penalizan los cursos que dependen del curso que está repasando. Por qué: avanzar sobre una base que aún no se domina acumula lagunas; conviene consolidar antes de seguir.'),

  ('R06', 'recomendacion', 40,
   '{}'::jsonb,
   '{"filtro": {"todas": [{"campo": "curso.dificultad", "op": ">=", "valor": 4}, {"campo": "curso.dominio_conceptos_curso", "op": "<", "valor": 0.4}]}, "puntos": -2, "explicacion": ""}'::jsonb,
   'Demasiado difícil por ahora',
   'Se penalizan los cursos de dificultad 4 o más cuando el dominio del alumno sobre sus conceptos es menor que 0.4. Solo baja la puntuación, sin mostrar un motivo. Por qué: un reto muy por encima de lo que se domina desanima; es mejor proponerlo cuando el alumno esté más cerca.')
ON CONFLICT (codigo) DO UPDATE
SET ambito      = EXCLUDED.ambito,
    prioridad   = EXCLUDED.prioridad,
    condicion   = EXCLUDED.condicion,
    accion      = EXCLUDED.accion,
    nombre      = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion;


-- Comprobación final ---------------------------------------------------------

DO $$
DECLARE
  n_filtro        integer;
  n_recomendacion integer;
  mal_formadas    text;
BEGIN
  SELECT count(*) INTO n_filtro
  FROM public.reglas
  WHERE ambito = 'filtro' AND codigo IN ('F01', 'F02', 'F03');

  SELECT count(*) INTO n_recomendacion
  FROM public.reglas
  WHERE ambito = 'recomendacion'
    AND codigo IN ('R01', 'R02', 'R03a', 'R03b', 'R03c', 'R04', 'R05', 'R06');

  SELECT string_agg(codigo, ', ' ORDER BY codigo) INTO mal_formadas
  FROM public.reglas
  WHERE codigo IN ('F01', 'F02', 'F03', 'R01', 'R02', 'R03a', 'R03b', 'R03c', 'R04', 'R05', 'R06')
    AND (
      jsonb_typeof(condicion) IS DISTINCT FROM 'object'
      OR jsonb_typeof(accion) IS DISTINCT FROM 'object'
      OR (ambito = 'recomendacion' AND (
            jsonb_typeof(accion -> 'filtro') IS DISTINCT FROM 'object'
            OR jsonb_typeof(accion -> 'puntos') IS DISTINCT FROM 'number'
            OR jsonb_typeof(accion -> 'explicacion') IS DISTINCT FROM 'string'))
    );

  IF n_filtro <> 3 THEN
    RAISE EXCEPTION 'Migración 0008 abortada: se esperaban 3 reglas de filtro y hay %.', n_filtro;
  END IF;

  IF n_recomendacion <> 8 THEN
    RAISE EXCEPTION
      'Migración 0008 abortada: se esperaban 8 reglas de recomendación y hay %.', n_recomendacion;
  END IF;

  IF mal_formadas IS NOT NULL THEN
    RAISE EXCEPTION
      'Migración 0008 abortada: reglas con condicion/accion mal formadas: %.', mal_formadas;
  END IF;
END $$;


COMMIT;
