-- 0007_diagnostico_inicial.sql
--
-- Las 5 preguntas del diagnóstico inicial, que hasta ahora estaban fijas en
-- frontend/src/pages/ColdStart.jsx (PREGUNTAS_TECNICAS), pasan a la base de
-- datos como `ejercicios` de tipo 'evaluacion_tecnica', con 4 opciones cada una
-- y exactamente una correcta. Así el backend corrige con ids reales y el
-- cliente nunca ve `es_correcta`.
--
-- Cada pregunta cuelga del módulo que diagnostica, para que la evidencia se
-- traduzca a conceptos a través de las etiquetas de ese módulo (0006):
--
--   print("5" + "5")            PY-101, tema 1
--   palabra clave de función    PY-401, tema 1
--   len([10, 20, 30])           PY-101, tema 2
--   for i in range(3)           PY-201, tema 2
--   estructura inmutable        PY-101, tema 2
--
-- Las claves ajenas se resuelven por clave natural (codigo_curso -> temas.orden
-- -> ejercicios.titulo + tipo), igual que 0003. El ORDER BY de la inserción
-- deja los ids en el orden de las preguntas, que es como las devuelve la API.
--
-- Idempotente: cada INSERT lleva su guarda NOT EXISTS. Termina con una
-- comprobación que aborta si no quedan exactamente 5 ejercicios de diagnóstico
-- con 4 opciones y 1 correcta cada uno.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;


-- 1. Ejercicios --------------------------------------------------------------

INSERT INTO public.ejercicios (tema_id, titulo, tipo, consigna)
SELECT t.id, v.titulo, 'evaluacion_tecnica'::public.tipo_ejercicio, v.consigna
FROM (VALUES
  (1, 'PY-101', 1, 'Diagnóstico: concatenación de cadenas',
   '¿Cuál es la salida del siguiente código en Python?

```python
print("5" + "5")
```'),
  (2, 'PY-401', 1, 'Diagnóstico: definición de funciones',
   '¿Qué palabra clave se utiliza para definir una función en Python?

```python
___ mi_funcion():
    return "Hola"
```'),
  (3, 'PY-101', 2, 'Diagnóstico: longitud de una lista',
   '¿Qué resultado produce la expresión len([10, 20, 30])?

```python
numeros = [10, 20, 30]
print(len(numeros))
```'),
  (4, 'PY-201', 2, 'Diagnóstico: bucle for con range',
   '¿Cuál es la salida del siguiente bucle for?

```python
for i in range(3):
    print(i, end=" ")
```'),
  (5, 'PY-101', 2, 'Diagnóstico: estructuras inmutables',
   '¿Qué estructura de datos es inmutable en Python?

```python
a = (1, 2, 3)
```')
) AS v(n, codigo, tema_orden, titulo, consigna)
JOIN public.cursos c ON c.codigo_curso = v.codigo
JOIN public.temas  t ON t.curso_id = c.id AND t.orden = v.tema_orden
WHERE NOT EXISTS (
  SELECT 1 FROM public.ejercicios e
  WHERE e.tema_id = t.id
    AND e.titulo = v.titulo
    AND e.tipo = 'evaluacion_tecnica'::public.tipo_ejercicio
)
ORDER BY v.n;


-- 2. Opciones ----------------------------------------------------------------

INSERT INTO public.opciones_ejercicios (ejercicio_id, texto_opcion, es_correcta, orden)
SELECT e.id, v.texto_opcion, v.es_correcta, v.orden
FROM (VALUES
  ('PY-101', 1, 'Diagnóstico: concatenación de cadenas', 1, '10',        false),
  ('PY-101', 1, 'Diagnóstico: concatenación de cadenas', 2, '55',        true),
  ('PY-101', 1, 'Diagnóstico: concatenación de cadenas', 3, 'TypeError', false),
  ('PY-101', 1, 'Diagnóstico: concatenación de cadenas', 4, '"10"',      false),

  ('PY-401', 1, 'Diagnóstico: definición de funciones', 1, 'function', false),
  ('PY-401', 1, 'Diagnóstico: definición de funciones', 2, 'def',      true),
  ('PY-401', 1, 'Diagnóstico: definición de funciones', 3, 'func',     false),
  ('PY-401', 1, 'Diagnóstico: definición de funciones', 4, 'void',     false),

  ('PY-101', 2, 'Diagnóstico: longitud de una lista', 1, '30',              false),
  ('PY-101', 2, 'Diagnóstico: longitud de una lista', 2, '2',               false),
  ('PY-101', 2, 'Diagnóstico: longitud de una lista', 3, '3',               true),
  ('PY-101', 2, 'Diagnóstico: longitud de una lista', 4, 'Error de índice', false),

  ('PY-201', 2, 'Diagnóstico: bucle for con range', 1, '1 2 3',   false),
  ('PY-201', 2, 'Diagnóstico: bucle for con range', 2, '0 1 2',   true),
  ('PY-201', 2, 'Diagnóstico: bucle for con range', 3, '0 1 2 3', false),
  ('PY-201', 2, 'Diagnóstico: bucle for con range', 4, '1 2',     false),

  ('PY-101', 2, 'Diagnóstico: estructuras inmutables', 1, 'Lista',          false),
  ('PY-101', 2, 'Diagnóstico: estructuras inmutables', 2, 'Diccionario',    false),
  ('PY-101', 2, 'Diagnóstico: estructuras inmutables', 3, 'Tupla',          true),
  ('PY-101', 2, 'Diagnóstico: estructuras inmutables', 4, 'Conjunto (Set)', false)
) AS v(codigo, tema_orden, ejercicio_titulo, orden, texto_opcion, es_correcta)
JOIN public.cursos     c ON c.codigo_curso = v.codigo
JOIN public.temas      t ON t.curso_id = c.id AND t.orden = v.tema_orden
JOIN public.ejercicios e ON e.tema_id = t.id
                        AND e.titulo = v.ejercicio_titulo
                        AND e.tipo = 'evaluacion_tecnica'::public.tipo_ejercicio
WHERE NOT EXISTS (
  SELECT 1 FROM public.opciones_ejercicios o
  WHERE o.ejercicio_id = e.id AND o.orden = v.orden
);


-- 3. Comprobación ------------------------------------------------------------
-- Exactamente 5 ejercicios de diagnóstico, cada uno con 4 opciones y 1
-- correcta. Si no, se aborta la transacción entera.

DO $$
DECLARE
  total integer;
  malos integer;
BEGIN
  SELECT count(*) INTO total
  FROM public.ejercicios
  WHERE tipo = 'evaluacion_tecnica'::public.tipo_ejercicio;

  SELECT count(*) INTO malos
  FROM public.ejercicios e
  WHERE e.tipo = 'evaluacion_tecnica'::public.tipo_ejercicio
    AND (
      (SELECT count(*) FROM public.opciones_ejercicios o WHERE o.ejercicio_id = e.id) <> 4
      OR
      (SELECT count(*) FROM public.opciones_ejercicios o
        WHERE o.ejercicio_id = e.id AND o.es_correcta) <> 1
    );

  IF total <> 5 OR malos > 0 THEN
    RAISE EXCEPTION
      'Migración 0007 abortada: % ejercicio(s) de diagnóstico (se esperaban 5), % sin 4 opciones con exactamente 1 correcta.',
      total, malos;
  END IF;
END $$;


COMMIT;
