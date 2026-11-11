-- 0001_esquema_base.sql
--
-- Línea base del esquema: estado de la base de datos en el momento de empezar a
-- versionar las migraciones (2026-11-11). Generado mecánicamente con
--
--   pg_dump --schema-only --schema=public --no-owner --no-privileges \
--           --no-publications --no-subscriptions --no-comments
--
-- IMPORTANTE: esta migración NO se ejecuta contra la base de datos que ya
-- existe; ahí se registra como aplicada sin correrla (`manage.py migrar_sql
-- --sellar 0001`). Correrla sobre un esquema que ya tiene estas tablas falla con
-- 42P07 "relation already exists", y eso es lo correcto: su única función es
-- permitir recrear la base desde cero (otro entorno, una rama de Supabase, un
-- Postgres local) ejecutando 0001, 0002 y 0003 en orden.
--
-- No editar a mano. Para cambiar el esquema, añade una migración nueva.

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: formato_vista; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.formato_vista AS ENUM (
    'pantalla_dividida',
    'pantalla_completa'
);


--
-- Name: nivel_estudiante; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.nivel_estudiante AS ENUM (
    'Principiante',
    'Intermedio',
    'Avanzado'
);


--
-- Name: tema_interfaz; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tema_interfaz AS ENUM (
    'modo_claro',
    'modo_oscuro'
);


--
-- Name: tipo_ejercicio; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipo_ejercicio AS ENUM (
    'ejercicio_practico',
    'evaluacion_tecnica',
    'examen_final'
);


--
-- Name: tipografia_tipo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.tipografia_tipo AS ENUM (
    'sans_serif',
    'serif',
    'monospace'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: cursos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cursos (
    id integer NOT NULL,
    codigo_curso character varying NOT NULL,
    titulo character varying NOT NULL,
    descripcion text
);


--
-- Name: cursos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.cursos ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cursos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: ejercicios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ejercicios (
    id integer NOT NULL,
    tema_id integer NOT NULL,
    titulo character varying NOT NULL,
    tipo public.tipo_ejercicio DEFAULT 'ejercicio_practico'::public.tipo_ejercicio NOT NULL,
    consigna text
);


--
-- Name: ejercicios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.ejercicios ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.ejercicios_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: eventos_telemetria_ux; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eventos_telemetria_ux (
    id bigint NOT NULL,
    sesion_id bigint,
    usuario_id uuid NOT NULL,
    duracion_inactividad_segundos integer DEFAULT 0,
    frecuencia_blur_events integer DEFAULT 0,
    rage_clicks_count integer DEFAULT 0,
    veces_compartio_progreso integer DEFAULT 0,
    fecha_registro timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: eventos_telemetria_ux_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.eventos_telemetria_ux ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.eventos_telemetria_ux_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: intentos_ejercicios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.intentos_ejercicios (
    id bigint NOT NULL,
    usuario_id uuid NOT NULL,
    ejercicio_id integer NOT NULL,
    calificacion_obtenida numeric(5,2),
    numero_aciertos integer DEFAULT 0,
    numero_errores integer DEFAULT 0,
    frecuencia_pistas_hints integer DEFAULT 0,
    ejecuciones_codigo_count integer DEFAULT 0,
    tiempo_resolucion_segundos integer DEFAULT 0,
    frecuencia_copiar_ctrl_c integer DEFAULT 0,
    frecuencia_pegar_ctrl_v integer DEFAULT 0,
    fecha_intento timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: intentos_ejercicios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.intentos_ejercicios ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.intentos_ejercicios_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: opciones_ejercicios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.opciones_ejercicios (
    id integer NOT NULL,
    ejercicio_id integer NOT NULL,
    texto_opcion text NOT NULL,
    es_correcta boolean DEFAULT false NOT NULL,
    orden integer DEFAULT 1
);


--
-- Name: opciones_ejercicios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.opciones_ejercicios ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.opciones_ejercicios_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sesiones_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sesiones_usuario (
    id bigint NOT NULL,
    usuario_id uuid NOT NULL,
    navegador character varying,
    dispositivo character varying,
    pais character varying,
    region_zona_horaria character varying,
    latencia_ping_ms integer,
    velocidad_conexion_kbps integer,
    frecuencia_login_habitual character varying,
    dia_semana_mayor_actividad character varying,
    inicio_sesion timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    fin_sesion timestamp with time zone,
    duracion_total_segundos integer
);


--
-- Name: sesiones_usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.sesiones_usuario ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.sesiones_usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: temas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.temas (
    id integer NOT NULL,
    curso_id integer NOT NULL,
    titulo character varying NOT NULL,
    orden integer NOT NULL,
    descripcion text
);


--
-- Name: temas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.temas ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.temas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario_cursos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_cursos (
    id integer NOT NULL,
    usuario_id uuid NOT NULL,
    curso_id integer NOT NULL,
    porcentaje_avance_global numeric(5,2) DEFAULT 0.00,
    tiempo_acumulado_segundos integer DEFAULT 0,
    calificacion_final numeric(5,2),
    fecha_inscripcion timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: usuario_cursos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario_cursos ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_cursos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario_idiomas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_idiomas (
    id integer NOT NULL,
    usuario_id uuid NOT NULL,
    idioma character varying NOT NULL
);


--
-- Name: usuario_idiomas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario_idiomas ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_idiomas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario_preferencias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_preferencias (
    usuario_id uuid NOT NULL,
    idioma_interfaz character varying DEFAULT 'es'::character varying,
    tema_interfaz public.tema_interfaz DEFAULT 'modo_claro'::public.tema_interfaz,
    paleta_acento character varying DEFAULT '#3b82f6'::character varying,
    tipografia_preferida public.tipografia_tipo DEFAULT 'sans_serif'::public.tipografia_tipo,
    formato_visualizacion public.formato_vista DEFAULT 'pantalla_dividida'::public.formato_vista,
    franja_horaria_preferida text,
    meta_diaria_minutos integer DEFAULT 30,
    meta_semanal_minutos integer DEFAULT 210,
    accesibilidad_daltonismo boolean DEFAULT false,
    accesibilidad_epilepsia boolean DEFAULT false
);


--
-- Name: usuario_tema_metadatos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_tema_metadatos (
    id integer NOT NULL,
    usuario_temas_id integer NOT NULL,
    tiempo_lectura_segundos integer DEFAULT 0,
    frecuencia_relectura_silabo integer DEFAULT 0,
    tiempo_promedio_dedicado_segundos integer DEFAULT 0,
    fecha_ultimo_acceso timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: usuario_tema_metadatos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario_tema_metadatos ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_tema_metadatos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario_temas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_temas (
    id integer NOT NULL,
    usuario_id uuid NOT NULL,
    tema_id integer NOT NULL,
    estado character varying DEFAULT 'Bloqueado'::character varying
);


--
-- Name: usuario_temas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario_temas ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_temas_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id uuid NOT NULL,
    nombre character varying NOT NULL,
    email character varying NOT NULL,
    estatus_universitario boolean DEFAULT true NOT NULL,
    carrera_area_estudio character varying,
    edad_rango character varying,
    nivel_conocimiento_python character varying,
    nivel_asignado public.nivel_estudiante DEFAULT 'Principiante'::public.nivel_estudiante,
    nivel_ingles character varying,
    familiaridad_ide boolean DEFAULT false,
    ide_preferido character varying,
    objetivo_aprendizaje text,
    estilo_aprendizaje_preferido text,
    fecha_registro timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    centro_universitario character varying
);


--
-- Name: cursos cursos_codigo_curso_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cursos
    ADD CONSTRAINT cursos_codigo_curso_key UNIQUE (codigo_curso);


--
-- Name: cursos cursos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cursos
    ADD CONSTRAINT cursos_pkey PRIMARY KEY (id);


--
-- Name: ejercicios ejercicios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejercicios
    ADD CONSTRAINT ejercicios_pkey PRIMARY KEY (id);


--
-- Name: eventos_telemetria_ux eventos_telemetria_ux_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_telemetria_ux
    ADD CONSTRAINT eventos_telemetria_ux_pkey PRIMARY KEY (id);


--
-- Name: intentos_ejercicios intentos_ejercicios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intentos_ejercicios
    ADD CONSTRAINT intentos_ejercicios_pkey PRIMARY KEY (id);


--
-- Name: opciones_ejercicios opciones_ejercicios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opciones_ejercicios
    ADD CONSTRAINT opciones_ejercicios_pkey PRIMARY KEY (id);


--
-- Name: sesiones_usuario sesiones_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesiones_usuario
    ADD CONSTRAINT sesiones_usuario_pkey PRIMARY KEY (id);


--
-- Name: temas temas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.temas
    ADD CONSTRAINT temas_pkey PRIMARY KEY (id);


--
-- Name: usuario_cursos usuario_cursos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_cursos
    ADD CONSTRAINT usuario_cursos_pkey PRIMARY KEY (id);


--
-- Name: usuario_idiomas usuario_idiomas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_idiomas
    ADD CONSTRAINT usuario_idiomas_pkey PRIMARY KEY (id);


--
-- Name: usuario_preferencias usuario_preferencias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_preferencias
    ADD CONSTRAINT usuario_preferencias_pkey PRIMARY KEY (usuario_id);


--
-- Name: usuario_tema_metadatos usuario_tema_metadatos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_tema_metadatos
    ADD CONSTRAINT usuario_tema_metadatos_pkey PRIMARY KEY (id);


--
-- Name: usuario_temas usuario_temas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_temas
    ADD CONSTRAINT usuario_temas_pkey PRIMARY KEY (id);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: ejercicios ejercicios_tema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ejercicios
    ADD CONSTRAINT ejercicios_tema_id_fkey FOREIGN KEY (tema_id) REFERENCES public.temas(id) ON DELETE CASCADE;


--
-- Name: eventos_telemetria_ux eventos_telemetria_ux_sesion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_telemetria_ux
    ADD CONSTRAINT eventos_telemetria_ux_sesion_id_fkey FOREIGN KEY (sesion_id) REFERENCES public.sesiones_usuario(id) ON DELETE SET NULL;


--
-- Name: eventos_telemetria_ux eventos_telemetria_ux_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_telemetria_ux
    ADD CONSTRAINT eventos_telemetria_ux_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: intentos_ejercicios intentos_ejercicios_ejercicio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intentos_ejercicios
    ADD CONSTRAINT intentos_ejercicios_ejercicio_id_fkey FOREIGN KEY (ejercicio_id) REFERENCES public.ejercicios(id) ON DELETE CASCADE;


--
-- Name: intentos_ejercicios intentos_ejercicios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.intentos_ejercicios
    ADD CONSTRAINT intentos_ejercicios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: opciones_ejercicios opciones_ejercicios_ejercicio_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.opciones_ejercicios
    ADD CONSTRAINT opciones_ejercicios_ejercicio_id_fkey FOREIGN KEY (ejercicio_id) REFERENCES public.ejercicios(id) ON DELETE CASCADE;


--
-- Name: sesiones_usuario sesiones_usuario_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sesiones_usuario
    ADD CONSTRAINT sesiones_usuario_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: temas temas_curso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.temas
    ADD CONSTRAINT temas_curso_id_fkey FOREIGN KEY (curso_id) REFERENCES public.cursos(id) ON DELETE CASCADE;


--
-- Name: usuario_cursos usuario_cursos_curso_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_cursos
    ADD CONSTRAINT usuario_cursos_curso_id_fkey FOREIGN KEY (curso_id) REFERENCES public.cursos(id) ON DELETE CASCADE;


--
-- Name: usuario_cursos usuario_cursos_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_cursos
    ADD CONSTRAINT usuario_cursos_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuario_idiomas usuario_idiomas_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_idiomas
    ADD CONSTRAINT usuario_idiomas_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuario_preferencias usuario_preferencias_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_preferencias
    ADD CONSTRAINT usuario_preferencias_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuario_tema_metadatos usuario_tema_metadatos_usuario_temas_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_tema_metadatos
    ADD CONSTRAINT usuario_tema_metadatos_usuario_temas_id_fkey FOREIGN KEY (usuario_temas_id) REFERENCES public.usuario_temas(id) ON DELETE CASCADE;


--
-- Name: usuario_temas usuario_temas_tema_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_temas
    ADD CONSTRAINT usuario_temas_tema_id_fkey FOREIGN KEY (tema_id) REFERENCES public.temas(id) ON DELETE CASCADE;


--
-- Name: usuario_temas usuario_temas_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_temas
    ADD CONSTRAINT usuario_temas_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuarios usuarios_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--


