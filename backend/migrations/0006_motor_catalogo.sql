-- 0006_motor_catalogo.sql
--
-- Catálogo que lee el motor de recomendación (docs/motor/01-cimientos.md §2):
--   1. áreas y conceptos (un área es un concepto sin padre);
--   2. dificultad y nivel de los 8 cursos;
--   3. etiquetas de concepto por curso y por módulo (tema);
--   4. prerrequisitos entre cursos;
--   5. áreas afines a cada carrera.
--
-- Requiere 0005 (tablas y columnas) y los cursos/temas de 0002 y 0003.
-- Todas las claves ajenas se resuelven por clave natural (codigo_curso,
-- (codigo_curso, orden), conceptos.clave, carreras.clave), nunca por id literal.
--
-- Idempotente: los INSERT llevan ON CONFLICT y los UPDATE fijan valores.
-- Los pesos se actualizan si cambian (DO UPDATE), así reaplicarla tras revisar
-- un valor corrige el dato en vez de ignorarlo.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;


-- 1. Áreas y conceptos -------------------------------------------------------

INSERT INTO public.conceptos (clave, nombre, padre_id)
VALUES
  ('fundamentos',    'Fundamentos',                       NULL),
  ('poo',            'Programación orientada a objetos',  NULL),
  ('datos',          'Datos',                             NULL),
  ('automatizacion', 'Automatización',                    NULL)
ON CONFLICT (clave) DO UPDATE
SET nombre = EXCLUDED.nombre, padre_id = NULL;

INSERT INTO public.conceptos (clave, nombre, padre_id)
SELECT v.clave, v.nombre, a.id
FROM (VALUES
  ('variables_tipos',        'Variables y tipos',        'fundamentos'),
  ('colecciones',            'Listas y tuplas',          'fundamentos'),
  ('condicionales',          'Condicionales',            'fundamentos'),
  ('bucles',                 'Bucles',                   'fundamentos'),
  ('funciones',              'Funciones',                'fundamentos'),
  ('poo_clases',             'Clases y objetos',         'poo'),
  ('herencia_polimorfismo',  'Herencia y polimorfismo',  'poo'),
  ('diccionarios_conjuntos', 'Diccionarios y conjuntos', 'datos'),
  ('comprensiones',          'Comprensiones',            'datos'),
  ('json_apis',              'JSON y APIs',              'datos'),
  ('excepciones',            'Excepciones',              'automatizacion'),
  ('archivos',               'Archivos',                 'automatizacion'),
  ('libreria_estandar',      'Librería estándar',        'automatizacion'),
  ('modulos',                'Módulos',                  'automatizacion')
) AS v(clave, nombre, area)
JOIN public.conceptos a ON a.clave = v.area AND a.padre_id IS NULL
ON CONFLICT (clave) DO UPDATE
SET nombre = EXCLUDED.nombre, padre_id = EXCLUDED.padre_id;


-- 2. Dificultad y nivel de los cursos ---------------------------------------

CREATE TEMP TABLE _motor_cursos ON COMMIT DROP AS
SELECT *
FROM (VALUES
  ('PY-101', 1, 'Principiante'),
  ('PY-201', 1, 'Principiante'),
  ('PY-401', 2, 'Principiante'),
  ('PY-301', 3, 'Intermedio'),
  ('PY-501', 3, 'Intermedio'),
  ('PY-601', 3, 'Intermedio'),
  ('PY-701', 4, 'Avanzado'),
  ('PY-801', 4, 'Avanzado')
) AS v(codigo, dificultad, nivel);

UPDATE public.cursos c
SET dificultad = v.dificultad,
    nivel      = v.nivel::public.nivel_estudiante
FROM _motor_cursos v
WHERE c.codigo_curso = v.codigo;


-- 3. Etiquetas de concepto ---------------------------------------------------

-- 3a. Antes de etiquetar, cada curso y cada módulo referenciado debe existir.
-- Un JOIN silencioso se saltaría la fila que falta; aquí se aborta con el
-- nombre exacto de lo que no está.

CREATE TEMP TABLE _motor_etiquetas_tema ON COMMIT DROP AS
SELECT *
FROM (VALUES
  ('PY-101', 1, 'variables_tipos',        1.0),
  ('PY-101', 2, 'colecciones',            1.0),
  ('PY-201', 1, 'condicionales',          1.0),
  ('PY-201', 2, 'bucles',                 1.0),
  ('PY-301', 1, 'poo_clases',             1.0),
  ('PY-401', 1, 'funciones',              1.0),
  ('PY-401', 2, 'modulos',                0.7),
  ('PY-401', 2, 'funciones',              0.3),
  ('PY-501', 1, 'diccionarios_conjuntos', 1.0),
  ('PY-501', 2, 'comprensiones',          1.0),
  ('PY-601', 1, 'excepciones',            1.0),
  ('PY-601', 2, 'archivos',               1.0),
  ('PY-701', 1, 'herencia_polimorfismo',  1.0),
  ('PY-701', 2, 'herencia_polimorfismo',  0.7),
  ('PY-701', 2, 'poo_clases',             0.3),
  ('PY-801', 1, 'libreria_estandar',      1.0),
  ('PY-801', 2, 'json_apis',              1.0)
) AS v(codigo, orden, concepto, peso);

CREATE TEMP TABLE _motor_etiquetas_curso ON COMMIT DROP AS
SELECT *
FROM (VALUES
  ('PY-101', 'variables_tipos',        1.0),
  ('PY-101', 'colecciones',            0.6),
  ('PY-201', 'condicionales',          1.0),
  ('PY-201', 'bucles',                 1.0),
  ('PY-401', 'funciones',              1.0),
  ('PY-401', 'modulos',                0.7),
  ('PY-301', 'poo_clases',             1.0),
  ('PY-501', 'diccionarios_conjuntos', 1.0),
  ('PY-501', 'comprensiones',          1.0),
  ('PY-501', 'colecciones',            0.5),
  ('PY-601', 'excepciones',            1.0),
  ('PY-601', 'archivos',               1.0),
  ('PY-701', 'herencia_polimorfismo',  1.0),
  ('PY-701', 'poo_clases',             0.6),
  ('PY-801', 'libreria_estandar',      1.0),
  ('PY-801', 'json_apis',              1.0),
  ('PY-801', 'modulos',                0.5)
) AS v(codigo, concepto, peso);

DO $$
DECLARE
  faltan text;
BEGIN
  SELECT string_agg(DISTINCT e.codigo, ', ') INTO faltan
  FROM _motor_etiquetas_curso e
  LEFT JOIN public.cursos c ON c.codigo_curso = e.codigo
  WHERE c.id IS NULL;

  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0006 abortada: no existen los cursos %.', faltan;
  END IF;

  SELECT string_agg(DISTINCT e.codigo || ' orden ' || e.orden, ', ') INTO faltan
  FROM _motor_etiquetas_tema e
  LEFT JOIN public.cursos c ON c.codigo_curso = e.codigo
  LEFT JOIN public.temas  t ON t.curso_id = c.id AND t.orden = e.orden
  WHERE t.id IS NULL;

  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0006 abortada: no existen los módulos (temas) %.', faltan;
  END IF;

  SELECT string_agg(DISTINCT x.concepto, ', ') INTO faltan
  FROM (
    SELECT concepto FROM _motor_etiquetas_curso
    UNION SELECT concepto FROM _motor_etiquetas_tema
  ) x
  LEFT JOIN public.conceptos k ON k.clave = x.concepto
  WHERE k.id IS NULL;

  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0006 abortada: no existen los conceptos %.', faltan;
  END IF;
END $$;

-- 3b. Etiquetas de curso.

INSERT INTO public.contenido_concepto (objeto_tipo, objeto_id, concepto_id, peso)
SELECT 'curso', c.id, k.id, e.peso
FROM _motor_etiquetas_curso e
JOIN public.cursos    c ON c.codigo_curso = e.codigo
JOIN public.conceptos k ON k.clave = e.concepto
ON CONFLICT (objeto_tipo, objeto_id, concepto_id) DO UPDATE
SET peso = EXCLUDED.peso;

-- 3c. Etiquetas de módulo.

INSERT INTO public.contenido_concepto (objeto_tipo, objeto_id, concepto_id, peso)
SELECT 'tema', t.id, k.id, e.peso
FROM _motor_etiquetas_tema e
JOIN public.cursos    c ON c.codigo_curso = e.codigo
JOIN public.temas     t ON t.curso_id = c.id AND t.orden = e.orden
JOIN public.conceptos k ON k.clave = e.concepto
ON CONFLICT (objeto_tipo, objeto_id, concepto_id) DO UPDATE
SET peso = EXCLUDED.peso;


-- 4. Prerrequisitos ----------------------------------------------------------

INSERT INTO public.curso_prerrequisitos (curso_id, requiere_curso_id, calificacion_minima)
SELECT c.id, r.id, 80
FROM (VALUES
  ('PY-201', 'PY-101'),
  ('PY-401', 'PY-201'),
  ('PY-301', 'PY-401'),
  ('PY-501', 'PY-401'),
  ('PY-601', 'PY-401'),
  ('PY-701', 'PY-301'),
  ('PY-801', 'PY-501'),
  ('PY-801', 'PY-601')
) AS v(codigo, requiere)
JOIN public.cursos c ON c.codigo_curso = v.codigo
JOIN public.cursos r ON r.codigo_curso = v.requiere
ON CONFLICT (curso_id, requiere_curso_id) DO UPDATE
SET calificacion_minima = EXCLUDED.calificacion_minima;


-- 5. Carreras -> áreas -------------------------------------------------------
-- Las carreras que no aparecen no tienen afinidad declarada: no llevan fila.

CREATE TEMP TABLE _motor_carrera_areas ON COMMIT DROP AS
SELECT *
FROM (VALUES
  ('INCO', 'automatizacion', 0.5), ('INCO', 'datos', 0.3),
  ('INNI', 'automatizacion', 0.5), ('INNI', 'datos', 0.3),
  ('ICOM', 'automatizacion', 0.5), ('ICOM', 'datos', 0.3),
  ('IROB', 'automatizacion', 0.5), ('IROB', 'datos', 0.3),

  ('LMAT', 'datos', 0.5),
  ('LFIS', 'datos', 0.5),
  ('LQUI', 'datos', 0.5),
  ('IQUI', 'datos', 0.5),
  ('IBIO', 'datos', 0.5),
  ('IFOT', 'datos', 0.5),
  ('IALI', 'datos', 0.5),
  ('LBIO', 'datos', 0.5),

  ('IIND', 'automatizacion', 0.5),
  ('IMEC', 'automatizacion', 0.5),
  ('ICIV', 'automatizacion', 0.5),
  ('ITOP', 'automatizacion', 0.5),
  ('LARQ', 'automatizacion', 0.5),

  ('LADM', 'datos', 0.5), ('LADM', 'automatizacion', 0.3),
  ('LCPU', 'datos', 0.5), ('LCPU', 'automatizacion', 0.3),
  ('LECO', 'datos', 0.5), ('LECO', 'automatizacion', 0.3),
  ('LNIN', 'datos', 0.5), ('LNIN', 'automatizacion', 0.3)
) AS v(carrera, area, peso);

DO $$
DECLARE
  faltan text;
BEGIN
  SELECT string_agg(DISTINCT e.carrera, ', ') INTO faltan
  FROM _motor_carrera_areas e
  LEFT JOIN public.carreras ca ON ca.clave = e.carrera
  WHERE ca.id IS NULL;

  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0006 abortada: no existen las carreras %.', faltan;
  END IF;
END $$;

INSERT INTO public.carrera_areas (carrera_id, area_id, peso)
SELECT ca.id, a.id, e.peso
FROM _motor_carrera_areas e
JOIN public.carreras  ca ON ca.clave = e.carrera
JOIN public.conceptos a  ON a.clave = e.area AND a.padre_id IS NULL
ON CONFLICT (carrera_id, area_id) DO UPDATE
SET peso = EXCLUDED.peso;


-- 6. Comprobación ------------------------------------------------------------
-- Mejor no aplicar nada que dejar un catálogo a medias: el motor daría
-- recomendaciones sin sentido sin avisar.

DO $$
DECLARE
  n_areas          integer;
  n_conceptos      integer;
  n_cursos         integer;
  n_prerrequisitos integer;
  n_carreras       integer;
  sin_etiqueta     text;
BEGIN
  SELECT count(*) INTO n_areas
  FROM public.conceptos
  WHERE padre_id IS NULL
    AND clave IN ('fundamentos', 'poo', 'datos', 'automatizacion');

  SELECT count(*) INTO n_conceptos
  FROM public.conceptos k
  JOIN public.conceptos a ON a.id = k.padre_id
  WHERE a.clave IN ('fundamentos', 'poo', 'datos', 'automatizacion');

  SELECT count(*) INTO n_cursos
  FROM _motor_cursos v
  JOIN public.cursos c
    ON c.codigo_curso = v.codigo
   AND c.dificultad   = v.dificultad
   AND c.nivel        = v.nivel::public.nivel_estudiante
  WHERE EXISTS (
    SELECT 1 FROM public.contenido_concepto cc
    WHERE cc.objeto_tipo = 'curso' AND cc.objeto_id = c.id
  );

  SELECT count(*) INTO n_prerrequisitos
  FROM public.curso_prerrequisitos p
  JOIN public.cursos c ON c.id = p.curso_id
  WHERE c.codigo_curso IN (SELECT codigo FROM _motor_cursos);

  SELECT count(DISTINCT ca.id) INTO n_carreras
  FROM public.carrera_areas x
  JOIN public.carreras ca ON ca.id = x.carrera_id
  JOIN _motor_carrera_areas e ON e.carrera = ca.clave;

  SELECT string_agg(c.codigo_curso || ' orden ' || t.orden, ', ') INTO sin_etiqueta
  FROM public.temas t
  JOIN public.cursos c ON c.id = t.curso_id
  WHERE c.codigo_curso IN (SELECT codigo FROM _motor_cursos)
    AND NOT EXISTS (
      SELECT 1 FROM public.contenido_concepto cc
      WHERE cc.objeto_tipo = 'tema' AND cc.objeto_id = t.id
    );

  IF n_areas <> 4 THEN
    RAISE EXCEPTION 'Migración 0006 abortada: se esperaban 4 áreas y hay %.', n_areas;
  END IF;

  -- 5 + 2 + 3 + 4 conceptos en las tablas de 01-cimientos.md §2.
  IF n_conceptos <> 14 THEN
    RAISE EXCEPTION 'Migración 0006 abortada: se esperaban 14 conceptos y hay %.', n_conceptos;
  END IF;

  IF n_cursos <> 8 THEN
    RAISE EXCEPTION
      'Migración 0006 abortada: se esperaban 8 cursos con dificultad y etiquetas y hay %.',
      n_cursos;
  END IF;

  -- 6 cursos con un requisito y PY-801 con dos.
  IF n_prerrequisitos <> 8 THEN
    RAISE EXCEPTION
      'Migración 0006 abortada: se esperaban 8 prerrequisitos y hay %.', n_prerrequisitos;
  END IF;

  IF n_carreras <> 21 THEN
    RAISE EXCEPTION
      'Migración 0006 abortada: se esperaban 21 carreras con áreas y hay %.', n_carreras;
  END IF;

  IF sin_etiqueta IS NOT NULL THEN
    RAISE EXCEPTION
      'Migración 0006 abortada: módulos sin etiqueta de concepto: %.', sin_etiqueta;
  END IF;
END $$;


COMMIT;
