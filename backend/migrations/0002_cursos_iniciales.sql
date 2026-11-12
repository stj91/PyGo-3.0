-- 0002_cursos_iniciales.sql
--
-- Contenido del catálogo que ya existía al empezar a versionar (los 3 cursos
-- creados a mano desde el dashboard de Supabase): 3 cursos, 5 temas,
-- 10 ejercicios y 40 opciones. Generado mecánicamente con
--
--   pg_dump --data-only --column-inserts -t cursos -t temas \
--           -t ejercicios -t opciones_ejercicios
--
-- Igual que 0001, en la base que ya existe esta migración se SELLA, no se
-- ejecuta: las filas ya están ahí y reinsertarlas chocaría con
-- cursos_codigo_curso_key. Existe para que una base recreada desde cero tenga
-- el catálogo completo antes de aplicar 0003; sin ella, 0003 insertaría los
-- cursos PY-401..PY-801 sobre un catálogo sin PY-101..PY-301.
--
-- Los ids van explícitos con OVERRIDING SYSTEM VALUE porque las claves primarias
-- son GENERATED ALWAYS AS IDENTITY, y los setval del final dejan las secuencias
-- justo detrás del último id para que 0003 siga la numeración sin colisionar.

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
-- Data for Name: cursos; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.cursos (id, codigo_curso, titulo, descripcion) OVERRIDING SYSTEM VALUE VALUES (1, 'PY-101', 'Fundamentos de Python', 'Aprende las bases esenciales del lenguaje: variables, sintaxis y tipos de datos compuestas.');
INSERT INTO public.cursos (id, codigo_curso, titulo, descripcion) OVERRIDING SYSTEM VALUE VALUES (2, 'PY-201', 'Estructuras de Control', 'Domina la toma de decisiones con bloques condicionales (if/else) e iteraciones con bucles (for/while).');
INSERT INTO public.cursos (id, codigo_curso, titulo, descripcion) OVERRIDING SYSTEM VALUE VALUES (3, 'PY-301', 'Programación Orientada a Objetos', 'Diseña software modular creando clases, objetos, métodos y atributos en Python.');


--
-- Data for Name: temas; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.temas (id, curso_id, titulo, orden, descripcion) OVERRIDING SYSTEM VALUE VALUES (1, 1, 'Sintaxis y Variables', 1, 'En Python, una variable guarda datos sin necesidad de declarar su tipo explícitamente. Se asignan con el operador = y las cadenas usan comillas.');
INSERT INTO public.temas (id, curso_id, titulo, orden, descripcion) OVERRIDING SYSTEM VALUE VALUES (2, 1, 'Tipos de Datos Compuestos', 2, 'Las listas [] son colecciones ordenadas y mutables. Las tuplas () son inmutables. Se acceden mediante índices numéricos desde 0.');
INSERT INTO public.temas (id, curso_id, titulo, orden, descripcion) OVERRIDING SYSTEM VALUE VALUES (3, 2, 'Condicionales if / else', 1, 'Las sentencias if, elif y else evalúan condiciones booleanas. Es obligatorio mantener la indentación (sangría de 4 espacios) para definir el bloque de código.');
INSERT INTO public.temas (id, curso_id, titulo, orden, descripcion) OVERRIDING SYSTEM VALUE VALUES (4, 2, 'Bucles e Iteraciones', 2, 'El bucle for recorre secuencias como listas o rangos generados con range(inicio, fin, paso). El bucle while se repite mientras la condición sea verdadera.');
INSERT INTO public.temas (id, curso_id, titulo, orden, descripcion) OVERRIDING SYSTEM VALUE VALUES (5, 3, 'Clases y Objetos', 1, 'Una clase es la plantilla para crear objetos. El método constructor __init__ inicializa los atributos y self representa la instancia actual.');


--
-- Data for Name: ejercicios; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (1, 1, 'Concatenación de Texto', 'ejercicio_practico', '¿Cuál es la salida de ejecutar: a = "10"; b = "20"; print(a + b)?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (2, 1, 'Retorno de la función input()', 'ejercicio_practico', 'Si un usuario ingresa el número 5 en la función input(), ¿qué tipo de dato retorna Python?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (3, 2, 'Agregar a una lista', 'ejercicio_practico', '¿Qué método se utiliza para agregar un elemento al final de una lista en Python?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (4, 2, 'Inmutabilidad de Tuplas', 'ejercicio_practico', '¿Cuál de las siguientes estructuras NO permite modificar sus elementos después de creada?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (5, 3, 'Evaluación de Condiciones', 'ejercicio_practico', 'Dado x = 5 y y = 10, ¿qué imprime: if x > 3 and y < 8: print("A") elif x == 5: print("B") else: print("C")?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (6, 3, 'Delimitación de Bloques', 'ejercicio_practico', 'En Python, ¿cómo se delimita el bloque de código dentro de una estructura condicional if?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (7, 4, 'Uso de range()', 'ejercicio_practico', '¿Cuántas veces se ejecuta un bucle for k in range(0, 5, 2):?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (8, 4, 'Interrupción de bucles', 'ejercicio_practico', '¿Qué palabra reservada detiene inmediatamente la ejecución de un bucle?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (9, 5, 'El parámetro self', 'ejercicio_practico', '¿Cuál es el propósito del parámetro self en los métodos de una clase?');
INSERT INTO public.ejercicios (id, tema_id, titulo, tipo, consigna) OVERRIDING SYSTEM VALUE VALUES (10, 5, 'Constructor de Clase', 'ejercicio_practico', '¿Cuál es el nombre del método reservado utilizado para inicializar los atributos de un objeto al instanciarlo?');


--
-- Data for Name: opciones_ejercicios; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (1, 1, '30', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (2, 1, '1020', true, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (3, 1, 'TypeError', false, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (4, 1, '"30"', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (5, 2, '<class "int">', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (6, 2, '<class "float">', false, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (7, 2, '<class "str">', true, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (8, 2, '<class "bool">', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (9, 3, 'mi_lista.add(4)', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (10, 3, 'mi_lista.push(4)', false, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (11, 3, 'mi_lista.append(4)', true, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (12, 3, 'mi_lista.insert(4)', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (13, 4, 'Lista []', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (14, 4, 'Diccionario {}', false, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (15, 4, 'Tupla ()', true, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (16, 4, 'Conjunto set()', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (17, 5, 'A', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (18, 5, 'B', true, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (19, 5, 'C', false, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (20, 5, 'Error de Sintaxis', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (21, 6, 'Con llaves {}', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (22, 6, 'Con palabras clave begin/end', false, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (23, 6, 'Mediante Indentación / Sangría', true, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (24, 6, 'Con paréntesis ()', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (25, 7, '5 veces', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (26, 7, '3 veces (para 0, 2 y 4)', true, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (27, 7, '2 veces', false, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (28, 7, '4 veces', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (29, 8, 'stop', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (30, 8, 'exit', false, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (31, 8, 'break', true, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (32, 8, 'continue', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (33, 9, 'Es opcional y se puede omitir siempre', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (34, 9, 'Representa la instancia del objeto que invoca el método', true, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (35, 9, 'Indica que el método es privado', false, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (36, 9, 'Convierte la función en un método estático', false, 4);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (37, 10, '__construct__', false, 1);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (38, 10, '__init__', true, 2);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (39, 10, 'main()', false, 3);
INSERT INTO public.opciones_ejercicios (id, ejercicio_id, texto_opcion, es_correcta, orden) OVERRIDING SYSTEM VALUE VALUES (40, 10, 'create()', false, 4);


--
-- Name: cursos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.cursos_id_seq', 3, true);


--
-- Name: ejercicios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.ejercicios_id_seq', 10, true);


--
-- Name: opciones_ejercicios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.opciones_ejercicios_id_seq', 40, true);


--
-- Name: temas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.temas_id_seq', 5, true);


--
-- PostgreSQL database dump complete
--


