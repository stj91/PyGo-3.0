-- 0009_motor_prerrequisitos_suaves.sql
--
-- Los prerrequisitos pasan de filtro a consejo. Con F01 activa, a un alumno sin
-- cursos completados solo se le podía recomendar PY-101, aunque el diagnóstico
-- lo hubiera colocado en Avanzado. PyGo no impide inscribirse en ningún curso,
-- así que el filtro solo empobrecía las recomendaciones.
--
--   1. F01 se desactiva: todos los cursos publicados vuelven a ser candidatos.
--   2. R01 ("punto de partida") solo aplica a alumnos de nivel Principiante: el
--      diagnóstico ya dice dónde empieza cada uno.
--   3. R07 nueva: un curso con prerrequisitos pendientes baja de puntuación,
--      pero sigue en la lista si encaja por nivel e intereses.
--
-- Requiere 0008. Idempotente: se puede reaplicar sin efectos. Para volver a los
-- prerrequisitos estrictos basta con `UPDATE reglas SET activa = true WHERE codigo = 'F01'`.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;

UPDATE public.reglas
SET activa = false,
    descripcion = 'Desactivada en 0009: los prerrequisitos ya no excluyen cursos, solo restan puntos (R07). Si se activa, un curso solo se recomienda si el alumno completó cada uno de sus prerrequisitos con al menos la calificación mínima.'
WHERE codigo = 'F01';

UPDATE public.reglas
SET condicion = '{"todas": [{"ninguna": [{"campo": "cursos_completados", "op": "existe"}]}, {"campo": "nivel", "op": "=", "valor": "Principiante"}]}'::jsonb,
    descripcion = 'Si el alumno es de nivel Principiante y aún no ha completado ningún curso, se favorecen los cursos de dificultad 1. Por qué: empezar con éxitos tempranos y alcanzables refuerza la motivación; a quien el diagnóstico colocó más arriba no se le manda al principio.'
WHERE codigo = 'R01';

INSERT INTO public.reglas (codigo, ambito, prioridad, condicion, accion, nombre, descripcion)
VALUES
  ('R07', 'recomendacion', 75,
   '{}'::jsonb,
   '{"filtro": {"campo": "curso.prerrequisito_pendiente", "op": "=", "valor": true}, "puntos": -2, "explicacion": "Te conviene haber visto {curso.prerrequisito_pendiente_titulo} antes."}'::jsonb,
   'Prerrequisito pendiente',
   'Se resta puntuación a los cursos con algún prerrequisito que el alumno no ha completado ni domina (nivel y dominio suficientes, como F02). Por qué: lo recomendable es seguir el orden del temario, pero el alumno decide dónde empieza; el curso no se oculta.')
ON CONFLICT (codigo) DO UPDATE
SET ambito      = EXCLUDED.ambito,
    prioridad   = EXCLUDED.prioridad,
    condicion   = EXCLUDED.condicion,
    accion      = EXCLUDED.accion,
    nombre      = EXCLUDED.nombre,
    descripcion = EXCLUDED.descripcion;


-- Comprobación final ---------------------------------------------------------

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.reglas WHERE codigo = 'F01' AND activa = false) THEN
    RAISE EXCEPTION 'Migración 0009 abortada: F01 no existe o sigue activa (¿falta 0008?).';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.reglas
    WHERE codigo = 'R01'
      AND condicion -> 'todas' @> '[{"campo": "nivel", "op": "=", "valor": "Principiante"}]'::jsonb
  ) THEN
    RAISE EXCEPTION 'Migración 0009 abortada: R01 no quedó limitada a Principiante.';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM public.reglas
    WHERE codigo = 'R07' AND ambito = 'recomendacion' AND activa
      AND jsonb_typeof(accion -> 'puntos') = 'number'
  ) THEN
    RAISE EXCEPTION 'Migración 0009 abortada: R07 no está activa o está mal formada.';
  END IF;
END $$;

COMMIT;
