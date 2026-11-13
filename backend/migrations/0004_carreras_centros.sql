-- 0004_carreras_centros.sql
--
-- Convierte la carrera y el centro del usuario en catálogos con clave ajena, en
-- vez de dos campos de texto libre.
--
-- Motivo: el formulario de registro los pedía como <input type="text">, y la
-- tabla `usuarios` ya tiene la basura esperable — una carrera que dice
-- "lskdjfklsdfkjs" y el mismo campus escrito de dos formas distintas
-- ("CUCEI - D01" y "CUCEI - Sección D01"). Sin un catálogo no hay forma de
-- agrupar usuarios por centro ni de ofrecer un desplegable.
--
-- Vocabulario, para que las tablas digan lo que son:
--   centro  = el campus (CUCEI, CUCEA, CUCS...), los centros universitarios
--             de la Universidad de Guadalajara.
--   carrera = la licenciatura o ingeniería que estudia la persona.
--
-- Va todo en una migración a propósito: el relleno de `carrera_id`/`centro_id`
-- necesita que el catálogo ya tenga filas para poder mapear el texto antiguo a
-- un id, así que crear, sembrar y rellenar no se pueden separar en ficheros
-- distintos sin dejar la base en un estado intermedio sin sentido.
--
-- Las columnas de texto `carrera_area_estudio` y `centro_universitario` NO se
-- eliminan aquí. Son el único sitio donde sobrevive la sección ("Sección D01")
-- que el catálogo de centros no representa, y tirarlas sería irreversible. Una
-- vez comprobado que nada las lee, se quitan en una migración posterior.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;


-- 1. Catálogo de centros (campus) --------------------------------------------

CREATE TABLE IF NOT EXISTS public.centros (
  id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clave  varchar(16)  NOT NULL UNIQUE,
  nombre varchar(160) NOT NULL UNIQUE,
  activo boolean      NOT NULL DEFAULT true
);

COMMENT ON TABLE public.centros IS
  'Centros universitarios (campus) de la UdG. `activo` permite retirar uno del desplegable sin borrarlo, porque hay usuarios apuntando a él.';

INSERT INTO public.centros (clave, nombre)
VALUES
  ('CUAAD',       'CUAAD - Arte, Arquitectura y Diseño'),
  ('CUCBA',       'CUCBA - Ciencias Biológicas y Agropecuarias'),
  ('CUCEA',       'CUCEA - Ciencias Económico Administrativas'),
  ('CUCEI',       'CUCEI - Ciencias Exactas e Ingenierías'),
  ('CUCS',        'CUCS - Ciencias de la Salud'),
  ('CUCSH',       'CUCSH - Ciencias Sociales y Humanidades'),
  ('CUALTOS',     'CUAltos - Los Altos'),
  ('CUCIENEGA',   'CUCiénega - La Ciénega'),
  ('CUCOSTA',     'CUCosta - Costa'),
  ('CUCSUR',      'CUCSur - Costa Sur'),
  ('CULAGOS',     'CULagos - Los Lagos'),
  ('CUNORTE',     'CUNorte - Norte'),
  ('CUSUR',       'CUSur - Sur'),
  ('CUTONALA',    'CUTonalá - Tonalá'),
  ('CUVALLES',    'CUValles - Valles'),
  ('CUTLAJOMULCO','CUTlajomulco - Tlajomulco'),
  ('SUV',         'SUV - Sistema de Universidad Virtual')
ON CONFLICT (clave) DO NOTHING;


-- 2. Catálogo de carreras ----------------------------------------------------

CREATE TABLE IF NOT EXISTS public.carreras (
  id     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  clave  varchar(16)  NOT NULL UNIQUE,
  nombre varchar(160) NOT NULL UNIQUE,
  activo boolean      NOT NULL DEFAULT true
);

COMMENT ON TABLE public.carreras IS
  'Licenciaturas e ingenierías. Catálogo plano: no cuelga de `centros` porque el formulario de registro pide los dos campos de forma independiente.';

INSERT INTO public.carreras (clave, nombre)
VALUES
  ('INCO',  'Ingeniería en Computación'),
  ('INNI',  'Ingeniería en Informática'),
  ('ICOM',  'Ingeniería en Comunicaciones y Electrónica'),
  ('IROB',  'Ingeniería Robótica'),
  ('IBIO',  'Ingeniería Biomédica'),
  ('IFOT',  'Ingeniería Fotónica'),
  ('IIND',  'Ingeniería Industrial'),
  ('IMEC',  'Ingeniería Mecánica Eléctrica'),
  ('ICIV',  'Ingeniería Civil'),
  ('IQUI',  'Ingeniería Química'),
  ('IALI',  'Ingeniería en Alimentos y Biotecnología'),
  ('ITOP',  'Ingeniería en Topografía'),
  ('LMAT',  'Licenciatura en Matemáticas'),
  ('LFIS',  'Licenciatura en Física'),
  ('LQUI',  'Licenciatura en Química'),
  ('LADM',  'Licenciatura en Administración'),
  ('LCPU',  'Licenciatura en Contaduría Pública'),
  ('LECO',  'Licenciatura en Economía'),
  ('LNIN',  'Licenciatura en Negocios Internacionales'),
  ('LMED',  'Licenciatura en Medicina'),
  ('LENF',  'Licenciatura en Enfermería'),
  ('LPSI',  'Licenciatura en Psicología'),
  ('LDER',  'Licenciatura en Derecho'),
  ('LARQ',  'Licenciatura en Arquitectura'),
  ('LDIS',  'Licenciatura en Diseño'),
  ('LBIO',  'Licenciatura en Biología'),
  ('LAGR',  'Licenciatura en Agronomía'),
  ('LEDU',  'Licenciatura en Educación'),
  ('LLET',  'Licenciatura en Letras Hispánicas'),
  ('LHIS',  'Licenciatura en Historia')
ON CONFLICT (clave) DO NOTHING;


-- 3. Claves ajenas en `usuarios` ---------------------------------------------
-- ON DELETE RESTRICT: borrar una carrera que alguien estudia debe fallar, no
-- dejar al usuario con un id huérfano ni borrarlo en cascada.

ALTER TABLE public.usuarios
  ADD COLUMN IF NOT EXISTS carrera_id integer,
  ADD COLUMN IF NOT EXISTS centro_id  integer;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_carrera_id_fkey'
  ) THEN
    ALTER TABLE public.usuarios
      ADD CONSTRAINT usuarios_carrera_id_fkey
      FOREIGN KEY (carrera_id) REFERENCES public.carreras(id) ON DELETE RESTRICT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'usuarios_centro_id_fkey'
  ) THEN
    ALTER TABLE public.usuarios
      ADD CONSTRAINT usuarios_centro_id_fkey
      FOREIGN KEY (centro_id) REFERENCES public.centros(id) ON DELETE RESTRICT;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS usuarios_carrera_id_idx ON public.usuarios (carrera_id);
CREATE INDEX IF NOT EXISTS usuarios_centro_id_idx  ON public.usuarios (centro_id);


-- 4. Relleno de los usuarios existentes --------------------------------------
-- La carrera se resuelve por nombre exacto. Lo que no case se queda en NULL a
-- propósito: inventar una carrera para "lskdjfklsdfkjs" sería falsear el dato.

UPDATE public.usuarios u
SET carrera_id = ca.id
FROM public.carreras ca
WHERE u.carrera_id IS NULL
  AND lower(trim(u.carrera_area_estudio)) = lower(ca.nombre);

-- El centro venía con la sección pegada ("CUCEI - Sección D01"), así que se
-- busca la clave del campus dentro del texto. Se ordena por longitud de clave
-- descendente para que "CUCSH - ..." no lo capture la clave más corta "CUCS".

UPDATE public.usuarios u
SET centro_id = elegido.id
FROM (
  SELECT u2.id AS usuario_id, ce.id
  FROM public.usuarios u2
  CROSS JOIN LATERAL (
    SELECT c.id
    FROM public.centros c
    WHERE u2.centro_universitario ILIKE '%' || c.clave || '%'
    ORDER BY length(c.clave) DESC
    LIMIT 1
  ) ce
  WHERE u2.centro_id IS NULL
    AND u2.centro_universitario IS NOT NULL
) AS elegido
WHERE u.id = elegido.usuario_id;


-- 5. Comprobación ------------------------------------------------------------
-- No se exige que todos los usuarios queden mapeados (hay texto basura que no
-- debe mapear a nada), pero sí que no quede ningún id apuntando a una fila
-- inexistente ni ningún catálogo vacío.

DO $$
DECLARE
  n_centros  integer;
  n_carreras integer;
  huerfanos  integer;
BEGIN
  SELECT count(*) INTO n_centros  FROM public.centros;
  SELECT count(*) INTO n_carreras FROM public.carreras;

  IF n_centros = 0 OR n_carreras = 0 THEN
    RAISE EXCEPTION
      'Migración 0004 abortada: catálogo vacío (centros=%, carreras=%).',
      n_centros, n_carreras;
  END IF;

  SELECT count(*) INTO huerfanos
  FROM public.usuarios u
  WHERE (u.carrera_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM public.carreras c WHERE c.id = u.carrera_id))
     OR (u.centro_id IS NOT NULL
         AND NOT EXISTS (SELECT 1 FROM public.centros c WHERE c.id = u.centro_id));

  IF huerfanos > 0 THEN
    RAISE EXCEPTION
      'Migración 0004 abortada: % usuario(s) con carrera_id o centro_id huérfano.',
      huerfanos;
  END IF;
END $$;


COMMIT;
