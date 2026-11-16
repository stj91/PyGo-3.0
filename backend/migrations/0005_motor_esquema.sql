-- 0005_motor_esquema.sql
--
-- Esquema del motor de recomendación (docs/motor-recomendacion.md §3). Solo
-- estructura: el catálogo de conceptos, etiquetas y prerrequisitos va en 0006.
--
-- Pasos, en este orden porque cada uno depende del anterior:
--   1. Elimina filas duplicadas de `usuario_temas` y `usuario_cursos`. El
--      backend Node insertaba una fila nueva en cada evaluación, y sin limpiar
--      los índices únicos del paso 2 no se pueden crear.
--   2. Índices únicos (usuario_id, tema_id) y (usuario_id, curso_id). Con ellos
--      `upsert(..., on_conflict=...)` ya es atómico.
--   3. Columnas nuevas en `cursos` y `usuario_cursos`, con su relleno.
--   4. Tablas nuevas del motor.
--   5. RLS activado sin políticas en todas las tablas nuevas: solo la
--      service-role key del backend puede leerlas o escribirlas.
--
-- Idempotente: se puede reaplicar sin efectos (IF NOT EXISTS y guardas).

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;


-- 1. Duplicados --------------------------------------------------------------

-- 1a. usuario_temas: por (usuario_id, tema_id) se conserva el estado más
-- avanzado y, a igualdad, el id más alto. Los metadatos de las filas que se
-- borran se reasignan antes a la fila conservada; si no, el ON DELETE CASCADE
-- de usuario_tema_metadatos se los llevaría por delante.

CREATE TEMP TABLE _motor_usuario_temas_dup ON COMMIT DROP AS
WITH ordenadas AS (
  SELECT
    id,
    first_value(id) OVER w AS conservar_id,
    row_number()    OVER w AS rn
  FROM public.usuario_temas
  WINDOW w AS (
    PARTITION BY usuario_id, tema_id
    ORDER BY
      CASE estado
        WHEN 'completado'              THEN 3
        WHEN 'actividades_de_refuerzo' THEN 2
        WHEN 'desbloqueado'            THEN 1
        ELSE 0
      END DESC,
      id DESC
  )
)
SELECT id AS borrar_id, conservar_id
FROM ordenadas
WHERE rn > 1;

UPDATE public.usuario_tema_metadatos m
SET usuario_temas_id = d.conservar_id
FROM _motor_usuario_temas_dup d
WHERE m.usuario_temas_id = d.borrar_id;

DELETE FROM public.usuario_temas ut
USING _motor_usuario_temas_dup d
WHERE ut.id = d.borrar_id;

-- 1b. usuario_cursos: por (usuario_id, curso_id) se conserva el mayor avance y,
-- a igualdad, el id más alto. Ninguna tabla referencia usuario_cursos.

WITH ordenadas AS (
  SELECT
    id,
    row_number() OVER (
      PARTITION BY usuario_id, curso_id
      ORDER BY coalesce(porcentaje_avance_global, 0) DESC, id DESC
    ) AS rn
  FROM public.usuario_cursos
)
DELETE FROM public.usuario_cursos uc
USING ordenadas o
WHERE uc.id = o.id
  AND o.rn > 1;

DO $$
DECLARE
  dup_temas  integer;
  dup_cursos integer;
BEGIN
  SELECT count(*) INTO dup_temas FROM (
    SELECT 1 FROM public.usuario_temas
    GROUP BY usuario_id, tema_id HAVING count(*) > 1
  ) x;

  SELECT count(*) INTO dup_cursos FROM (
    SELECT 1 FROM public.usuario_cursos
    GROUP BY usuario_id, curso_id HAVING count(*) > 1
  ) x;

  IF dup_temas > 0 OR dup_cursos > 0 THEN
    RAISE EXCEPTION
      'Migración 0005 abortada: quedan duplicados (usuario_temas=%, usuario_cursos=%).',
      dup_temas, dup_cursos;
  END IF;
END $$;


-- 2. Índices únicos ----------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS usuario_temas_usuario_tema_uk
  ON public.usuario_temas (usuario_id, tema_id);

CREATE UNIQUE INDEX IF NOT EXISTS usuario_cursos_usuario_curso_uk
  ON public.usuario_cursos (usuario_id, curso_id);


-- 3. Columnas nuevas ---------------------------------------------------------

ALTER TABLE public.cursos
  ADD COLUMN IF NOT EXISTS dificultad smallint NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS nivel      public.nivel_estudiante NOT NULL DEFAULT 'Principiante',
  ADD COLUMN IF NOT EXISTS publicado  boolean NOT NULL DEFAULT true;

ALTER TABLE public.usuario_cursos
  ADD COLUMN IF NOT EXISTS estado           varchar(12) NOT NULL DEFAULT 'activo',
  ADD COLUMN IF NOT EXISTS origen           varchar(20),
  ADD COLUMN IF NOT EXISTS recomendacion_id varchar(40),
  ADD COLUMN IF NOT EXISTS completado_en    timestamptz;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'cursos_dificultad_check') THEN
    ALTER TABLE public.cursos
      ADD CONSTRAINT cursos_dificultad_check CHECK (dificultad BETWEEN 1 AND 5);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'usuario_cursos_estado_check') THEN
    ALTER TABLE public.usuario_cursos
      ADD CONSTRAINT usuario_cursos_estado_check
      CHECK (estado IN ('activo', 'completado', 'abandonado'));
  END IF;
END $$;

-- Relleno: un curso al 100 % ya está terminado. La fecha real no se conoce, así
-- que se usa la de la migración (y nunca se pisa una que ya exista).
UPDATE public.usuario_cursos
SET estado        = 'completado',
    completado_en = coalesce(completado_en, now())
WHERE porcentaje_avance_global >= 100
  AND estado <> 'completado';


-- 4. Tablas nuevas -----------------------------------------------------------

-- 4a. Dominio: conceptos, etiquetas, prerrequisitos, carreras -> áreas.
-- Un área es un concepto con padre_id NULL.

CREATE TABLE IF NOT EXISTS public.conceptos (
  id       serial PRIMARY KEY,
  clave    varchar(60)  NOT NULL UNIQUE,
  nombre   varchar(120) NOT NULL,
  padre_id integer REFERENCES public.conceptos(id)
);

-- Sin clave ajena en objeto_id: apunta a cursos o a temas según objeto_tipo.
CREATE TABLE IF NOT EXISTS public.contenido_concepto (
  objeto_tipo varchar(10) NOT NULL CHECK (objeto_tipo IN ('curso', 'tema')),
  objeto_id   integer     NOT NULL,
  concepto_id integer     NOT NULL REFERENCES public.conceptos(id),
  peso        numeric(3,2) NOT NULL DEFAULT 1.0,
  PRIMARY KEY (objeto_tipo, objeto_id, concepto_id)
);

CREATE TABLE IF NOT EXISTS public.curso_prerrequisitos (
  curso_id            integer NOT NULL REFERENCES public.cursos(id) ON DELETE CASCADE,
  requiere_curso_id   integer NOT NULL REFERENCES public.cursos(id) ON DELETE CASCADE,
  calificacion_minima numeric(5,2) NOT NULL DEFAULT 80,
  PRIMARY KEY (curso_id, requiere_curso_id),
  CHECK (curso_id <> requiere_curso_id)
);

CREATE TABLE IF NOT EXISTS public.carrera_areas (
  carrera_id integer NOT NULL REFERENCES public.carreras(id) ON DELETE CASCADE,
  area_id    integer NOT NULL REFERENCES public.conceptos(id),
  peso       numeric(3,2) NOT NULL,
  PRIMARY KEY (carrera_id, area_id)
);

-- 4b. Usuario: intereses, perfil, dominio por concepto.

CREATE TABLE IF NOT EXISTS public.intereses_usuario (
  usuario_id  uuid    NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
  concepto_id integer NOT NULL REFERENCES public.conceptos(id),
  origen      varchar(10) NOT NULL DEFAULT 'declarado'
              CHECK (origen IN ('declarado', 'inferido')),
  peso        numeric(3,2) NOT NULL DEFAULT 1.0,
  PRIMARY KEY (usuario_id, concepto_id, origen)
);

CREATE TABLE IF NOT EXISTS public.perfiles (
  usuario_id      uuid PRIMARY KEY REFERENCES public.usuarios(id) ON DELETE CASCADE,
  nivel_inferido  public.nivel_estudiante,
  caracteristicas jsonb NOT NULL DEFAULT '{}',
  calculado_en    timestamptz
);

CREATE TABLE IF NOT EXISTS public.dominio_concepto (
  usuario_id     uuid    NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
  concepto_id    integer NOT NULL REFERENCES public.conceptos(id),
  dominio        numeric(4,3) NOT NULL CHECK (dominio BETWEEN 0 AND 1),
  evidencias     integer NOT NULL DEFAULT 0,
  actualizado_en timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (usuario_id, concepto_id)
);

-- 4c. Actividad: registro de eventos, solo inserción (nunca se actualiza ni se
-- borra). `fecha` la pone el servidor, nunca el navegador.

CREATE TABLE IF NOT EXISTS public.eventos (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  usuario_id  uuid NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
  tipo        varchar(40) NOT NULL,
  objeto_tipo varchar(20),
  objeto_id   integer,
  curso_id    integer REFERENCES public.cursos(id),
  valor       numeric(10,3),
  datos       jsonb NOT NULL DEFAULT '{}',
  sesion_id   varchar(40),
  fecha       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS eventos_usuario_fecha ON public.eventos (usuario_id, fecha);
CREATE INDEX IF NOT EXISTS eventos_tipo_fecha    ON public.eventos (tipo, fecha);

-- 4d. Motor: reglas, modelos, similitudes, recomendaciones emitidas.

CREATE TABLE IF NOT EXISTS public.reglas (
  id          serial PRIMARY KEY,
  codigo      varchar(10) NOT NULL UNIQUE,
  nombre      varchar(80) NOT NULL,
  descripcion text        NOT NULL,
  ambito      varchar(20) NOT NULL
              CHECK (ambito IN ('filtro', 'recomendacion', 'adaptacion', 'inferencia')),
  condicion   jsonb   NOT NULL,
  accion      jsonb   NOT NULL,
  prioridad   integer NOT NULL DEFAULT 0,
  activa      boolean NOT NULL DEFAULT true
);

-- El árbol exportado vive en `parametros` (JSON, nunca pickle) y la lista
-- ordenada de características en `caracteristicas`. Sin rutas a ficheros.
CREATE TABLE IF NOT EXISTS public.modelos (
  id              serial PRIMARY KEY,
  nombre          varchar(80) NOT NULL,
  version         varchar(20) NOT NULL,
  algoritmo       varchar(60) NOT NULL,
  parametros      jsonb NOT NULL,
  caracteristicas jsonb NOT NULL,
  metricas        jsonb NOT NULL,
  activo          boolean NOT NULL DEFAULT false,
  entrenado_en    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (nombre, version)
);

-- Como mucho un modelo activo por nombre.
CREATE UNIQUE INDEX IF NOT EXISTS modelos_un_activo ON public.modelos (nombre) WHERE activo;

CREATE TABLE IF NOT EXISTS public.similitud_cursos (
  curso_a      integer NOT NULL REFERENCES public.cursos(id) ON DELETE CASCADE,
  curso_b      integer NOT NULL REFERENCES public.cursos(id) ON DELETE CASCADE,
  similitud    numeric(5,4) NOT NULL,
  soporte      integer NOT NULL,
  calculado_en timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (curso_a, curso_b)
);

CREATE TABLE IF NOT EXISTS public.recomendaciones (
  id              varchar(40) PRIMARY KEY,
  usuario_id      uuid    NOT NULL REFERENCES public.usuarios(id) ON DELETE CASCADE,
  curso_id        integer NOT NULL REFERENCES public.cursos(id) ON DELETE CASCADE,
  puntuacion      numeric(6,4) NOT NULL,
  posicion        smallint     NOT NULL,
  motor           varchar(40)  NOT NULL,
  grupo           varchar(20)  NOT NULL,
  origen          jsonb NOT NULL,
  explicacion     text  NOT NULL,
  perfil_snapshot jsonb NOT NULL,
  estado          varchar(20) NOT NULL DEFAULT 'emitida'
                  CHECK (estado IN ('emitida', 'mostrada', 'clic', 'aceptada', 'descartada')),
  motivo_descarte varchar(40),
  creada_en       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS recomendaciones_usuario
  ON public.recomendaciones (usuario_id, creada_en);


-- 5. Row-level security ------------------------------------------------------
-- Activado y sin políticas: los roles anon/authenticated de Supabase no ven
-- nada; solo la service-role key del backend (que ignora RLS) accede.

ALTER TABLE public.conceptos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contenido_concepto   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.curso_prerrequisitos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.carrera_areas        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.intereses_usuario    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.perfiles             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dominio_concepto     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eventos              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reglas               ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.modelos              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.similitud_cursos     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.recomendaciones      ENABLE ROW LEVEL SECURITY;


COMMIT;
