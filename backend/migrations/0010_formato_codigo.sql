-- 0010_formato_codigo.sql
--
-- Marca el código dentro del contenido de los cursos para que la interfaz lo
-- muestre como código (fuente monoespaciada) y no como texto normal:
--   - código dentro de una frase, entre comillas invertidas: `print(a + b)`;
--   - código de varias líneas, en un bloque ```python … ``` con sus saltos de
--     línea y su sangría reales.
-- La interfaz (frontend/src/components/TextoConCodigo.jsx) interpreta solo esas
-- dos marcas; el resto del texto se muestra tal cual.
--
-- Afecta a `temas.descripcion` (explicación de la lección), `ejercicios.consigna`
-- y `opciones_ejercicios.texto_opcion` de los ejercicios de práctica. Los del
-- diagnóstico inicial (0007) ya usan bloques de código y no se tocan.
--
-- Corrige además un dato: Python escribe `<class 'str'>` con comillas simples.
--
-- Las filas se localizan por clave natural (código de curso, orden del módulo,
-- título del ejercicio, orden de la opción), nunca por id. Si alguna no existe,
-- la migración se aborta con su nombre. Idempotente: reaplicarla deja el mismo
-- texto.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;

-- 1. Explicaciones de las lecciones -------------------------------------------

CREATE TEMP TABLE _fmt_temas ON COMMIT DROP AS
SELECT * FROM (VALUES
  ('PY-101', 1, $t$En Python, una variable guarda datos sin necesidad de declarar su tipo explícitamente. Se asignan con el operador `=` y las cadenas usan comillas.$t$),
  ('PY-101', 2, $t$Las listas `[]` son colecciones ordenadas y mutables. Las tuplas `()` son inmutables. Se acceden mediante índices numéricos desde `0`.$t$),
  ('PY-201', 1, $t$Las sentencias `if`, `elif` y `else` evalúan condiciones booleanas. Es obligatorio mantener la indentación (sangría de 4 espacios) para definir el bloque de código.$t$),
  ('PY-201', 2, $t$El bucle `for` recorre secuencias como listas o rangos generados con `range(inicio, fin, paso)`. El bucle `while` se repite mientras la condición sea verdadera.$t$),
  ('PY-301', 1, $t$Una clase es la plantilla para crear objetos. El método constructor `__init__` inicializa los atributos y `self` representa la instancia actual.$t$),
  ('PY-401', 1, $t$Las funciones se declaran con `def` y pueden recibir parámetros con valores por defecto. La sentencia `return` devuelve un resultado; sin ella la función devuelve `None`.$t$),
  ('PY-401', 2, $t$Una variable asignada dentro de una función es local y no existe fuera de ella. Con `import` se reutiliza código de otros módulos, y `from modulo import nombre` trae solo una parte.$t$),
  ('PY-501', 1, $t$Un diccionario `{}` guarda pares clave-valor y se consulta por clave, no por posición. Un conjunto `set()` no admite elementos repetidos ni conserva el orden de inserción.$t$),
  ('PY-501', 2, $t$Una comprensión con la forma `[expresion for elemento in secuencia if condicion]` construye una lista nueva recorriendo otra, y sustituye al bucle `for` con `append`.$t$),
  ('PY-601', 1, $t$El bloque `try` contiene el código que puede fallar y `except` captura el error indicado. El bloque `finally` se ejecuta siempre, haya ocurrido una excepción o no.$t$),
  ('PY-601', 2, $t$La función `open()` abre un fichero en modo `"r"` para leer, `"w"` para sobrescribir y `"a"` para añadir al final. Usar `with open(...) as f` cierra el fichero automáticamente.$t$),
  ('PY-701', 1, $t$Una subclase declarada como `class Hija(Padre)` hereda los atributos y métodos de la clase padre. La llamada `super().__init__()` invoca el constructor heredado.$t$),
  ('PY-801', 1, $t$Python incluye módulos listos para usar: `datetime` para fechas y horas, `random` para valores aleatorios, `os` para el sistema de ficheros y `json` para intercambio de datos.$t$),
  ('PY-801', 2, $t$JSON es el formato estándar para intercambiar datos entre cliente y servidor. `json.loads()` convierte texto JSON en estructuras de Python y `json.dumps()` hace lo contrario.$t$)
) AS v(codigo, orden, texto);


-- 2. Enunciados de los ejercicios ---------------------------------------------

CREATE TEMP TABLE _fmt_ejercicios ON COMMIT DROP AS
SELECT * FROM (VALUES
  ('PY-101', 1, 'Concatenación de Texto', $t$¿Cuál es la salida de este código?
```python
a = "10"
b = "20"
print(a + b)
```$t$),
  ('PY-101', 1, 'Retorno de la función input()', $t$Si un usuario ingresa el número 5 en la función `input()`, ¿qué tipo de dato retorna Python?$t$),
  ('PY-201', 1, 'Evaluación de Condiciones', $t$Dado `x = 5` y `y = 10`, ¿qué imprime este código?
```python
if x > 3 and y < 8:
    print("A")
elif x == 5:
    print("B")
else:
    print("C")
```$t$),
  ('PY-201', 1, 'Delimitación de Bloques', $t$En Python, ¿cómo se delimita el bloque de código dentro de una estructura condicional `if`?$t$),
  ('PY-201', 2, 'Uso de range()', $t$¿Cuántas veces se ejecuta el cuerpo de este bucle?
```python
for k in range(0, 5, 2):
    print(k)
```$t$),
  ('PY-301', 1, 'El parámetro self', $t$¿Cuál es el propósito del parámetro `self` en los métodos de una clase?$t$),
  ('PY-401', 1, 'Parámetros con valor por defecto', $t$Dada esta función:
```python
def saludar(nombre, saludo="Hola"):
    return saludo + ", " + nombre
```
¿Qué devuelve la llamada `saludar("Ana")`?$t$),
  ('PY-401', 1, 'Retorno implícito', $t$¿Qué valor devuelve una función que termina sin ejecutar ninguna sentencia `return`?$t$),
  ('PY-401', 2, 'Importar un solo nombre', $t$¿Qué sentencia importa únicamente la función `sqrt` del módulo `math`?$t$),
  ('PY-501', 1, 'Eliminación de duplicados', $t$¿Cuántos elementos tiene el conjunto `set([1, 2, 2, 3, 3, 3])`?$t$),
  ('PY-501', 1, 'Acceso seguro a un diccionario', $t$¿Qué devuelve la expresión `{"a": 1}.get("b", 0)` cuando la clave `"b"` no existe?$t$),
  ('PY-501', 2, 'Filtrado con condición', $t$¿Qué lista produce la comprensión `[n for n in [1, 2, 3, 4, 5, 6] if n % 2 == 0]`?$t$),
  ('PY-501', 2, 'Resultado de una comprensión', $t$¿Qué lista produce la comprensión `[n * 2 for n in range(4)]`?$t$),
  ('PY-601', 1, 'El bloque finally', $t$¿Cuándo se ejecuta el bloque `finally` de una estructura `try`/`except`?$t$),
  ('PY-601', 1, 'División por cero', $t$¿Qué excepción lanza Python al ejecutar la operación `10 / 0`?$t$),
  ('PY-601', 2, 'Cierre automático con with', $t$¿Cuál es la ventaja de usar `with open("datos.txt") as f` en lugar de `f = open("datos.txt")`?$t$),
  ('PY-601', 2, 'Modo de apertura que no borra', $t$¿Qué modo de `open()` añade texto al final de un fichero sin borrar su contenido?$t$),
  ('PY-701', 1, 'Sintaxis de herencia', $t$¿Cómo se declara una clase `Perro` que hereda de la clase `Animal`?$t$),
  ('PY-701', 1, 'Constructor de la clase padre', $t$¿Qué función se usa dentro de una subclase para invocar el método `__init__` de su clase padre?$t$),
  ('PY-701', 2, 'Método sobrescrito', $t$Si `Animal` define el método `hablar()` y `Gato(Animal)` también lo define, ¿qué método ejecuta la llamada `Gato().hablar()`?$t$),
  ('PY-801', 1, 'Entero aleatorio', $t$¿Qué función del módulo `random` devuelve un entero aleatorio entre 1 y 10, ambos incluidos?$t$),
  ('PY-801', 1, 'Fechas y horas', $t$¿Qué módulo de la librería estándar se usa para trabajar con fechas y horas?$t$),
  ('PY-801', 2, 'De texto JSON a Python', $t$¿Qué función convierte una cadena con formato JSON en un diccionario de Python?$t$),
  ('PY-801', 2, 'Equivalente de un objeto JSON', $t$Al convertir el JSON `{"nombre": "Ana", "edad": 20}` a Python, ¿qué tipo de dato se obtiene?$t$)
) AS v(codigo, tema_orden, titulo, texto);


-- 3. Opciones que son código ---------------------------------------------------

CREATE TEMP TABLE _fmt_opciones ON COMMIT DROP AS
SELECT * FROM (VALUES
  ('PY-101', 1, 'Concatenación de Texto', 1, $t$`30`$t$),
  ('PY-101', 1, 'Concatenación de Texto', 2, $t$`1020`$t$),
  ('PY-101', 1, 'Concatenación de Texto', 3, $t$`TypeError`$t$),
  ('PY-101', 1, 'Concatenación de Texto', 4, $t$`"30"`$t$),
  ('PY-101', 1, 'Retorno de la función input()', 1, $t$`<class 'int'>`$t$),
  ('PY-101', 1, 'Retorno de la función input()', 2, $t$`<class 'float'>`$t$),
  ('PY-101', 1, 'Retorno de la función input()', 3, $t$`<class 'str'>`$t$),
  ('PY-101', 1, 'Retorno de la función input()', 4, $t$`<class 'bool'>`$t$),
  ('PY-101', 2, 'Agregar a una lista', 1, $t$`mi_lista.add(4)`$t$),
  ('PY-101', 2, 'Agregar a una lista', 2, $t$`mi_lista.push(4)`$t$),
  ('PY-101', 2, 'Agregar a una lista', 3, $t$`mi_lista.append(4)`$t$),
  ('PY-101', 2, 'Agregar a una lista', 4, $t$`mi_lista.insert(4)`$t$),
  ('PY-101', 2, 'Inmutabilidad de Tuplas', 1, $t$Lista `[]`$t$),
  ('PY-101', 2, 'Inmutabilidad de Tuplas', 2, $t$Diccionario `{}`$t$),
  ('PY-101', 2, 'Inmutabilidad de Tuplas', 3, $t$Tupla `()`$t$),
  ('PY-101', 2, 'Inmutabilidad de Tuplas', 4, $t$Conjunto `set()`$t$),
  ('PY-201', 1, 'Evaluación de Condiciones', 1, $t$`A`$t$),
  ('PY-201', 1, 'Evaluación de Condiciones', 2, $t$`B`$t$),
  ('PY-201', 1, 'Evaluación de Condiciones', 3, $t$`C`$t$),
  ('PY-201', 1, 'Evaluación de Condiciones', 4, $t$Error de sintaxis$t$),
  ('PY-201', 1, 'Delimitación de Bloques', 1, $t$Con llaves `{}`$t$),
  ('PY-201', 1, 'Delimitación de Bloques', 2, $t$Con palabras clave `begin`/`end`$t$),
  ('PY-201', 1, 'Delimitación de Bloques', 3, $t$Mediante indentación (sangría)$t$),
  ('PY-201', 1, 'Delimitación de Bloques', 4, $t$Con paréntesis `()`$t$),
  ('PY-201', 2, 'Interrupción de bucles', 1, $t$`stop`$t$),
  ('PY-201', 2, 'Interrupción de bucles', 2, $t$`exit`$t$),
  ('PY-201', 2, 'Interrupción de bucles', 3, $t$`break`$t$),
  ('PY-201', 2, 'Interrupción de bucles', 4, $t$`continue`$t$),
  ('PY-301', 1, 'Constructor de Clase', 1, $t$`__construct__`$t$),
  ('PY-301', 1, 'Constructor de Clase', 2, $t$`__init__`$t$),
  ('PY-301', 1, 'Constructor de Clase', 3, $t$`main()`$t$),
  ('PY-301', 1, 'Constructor de Clase', 4, $t$`create()`$t$),
  ('PY-401', 1, 'Parámetros con valor por defecto', 1, $t$`"Hola, Ana"`$t$),
  ('PY-401', 1, 'Parámetros con valor por defecto', 2, $t$`", Ana"`$t$),
  ('PY-401', 1, 'Parámetros con valor por defecto', 3, $t$`TypeError`: falta un argumento$t$),
  ('PY-401', 1, 'Parámetros con valor por defecto', 4, $t$`"Ana, Hola"`$t$),
  ('PY-401', 1, 'Retorno implícito', 1, $t$`0`$t$),
  ('PY-401', 1, 'Retorno implícito', 2, $t$`None`$t$),
  ('PY-401', 1, 'Retorno implícito', 3, $t$`False`$t$),
  ('PY-401', 1, 'Retorno implícito', 4, $t$La cadena vacía `""`$t$),
  ('PY-401', 2, 'Importar un solo nombre', 1, $t$`import sqrt from math`$t$),
  ('PY-401', 2, 'Importar un solo nombre', 2, $t$`from math import sqrt`$t$),
  ('PY-401', 2, 'Importar un solo nombre', 3, $t$`import math.sqrt`$t$),
  ('PY-401', 2, 'Importar un solo nombre', 4, $t$`include math.sqrt`$t$),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 1, $t$Lanza `KeyError`$t$),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 2, $t$`0`$t$),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 3, $t$`None`$t$),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 4, $t$`False`$t$),
  ('PY-501', 2, 'Filtrado con condición', 1, $t$`[1, 3, 5]`$t$),
  ('PY-501', 2, 'Filtrado con condición', 2, $t$`[2, 4, 6]`$t$),
  ('PY-501', 2, 'Filtrado con condición', 3, $t$`[True, False, True]`$t$),
  ('PY-501', 2, 'Filtrado con condición', 4, $t$`[2, 4, 6, 8]`$t$),
  ('PY-501', 2, 'Resultado de una comprensión', 1, $t$`[0, 2, 4, 6]`$t$),
  ('PY-501', 2, 'Resultado de una comprensión', 2, $t$`[2, 4, 6, 8]`$t$),
  ('PY-501', 2, 'Resultado de una comprensión', 3, $t$`[0, 1, 2, 3]`$t$),
  ('PY-501', 2, 'Resultado de una comprensión', 4, $t$`[8]`$t$),
  ('PY-601', 1, 'División por cero', 1, $t$`ValueError`$t$),
  ('PY-601', 1, 'División por cero', 2, $t$`ZeroDivisionError`$t$),
  ('PY-601', 1, 'División por cero', 3, $t$`ArithmeticOverflow`$t$),
  ('PY-601', 1, 'División por cero', 4, $t$`TypeError`$t$),
  ('PY-601', 2, 'Modo de apertura que no borra', 1, $t$El modo `"w"`$t$),
  ('PY-601', 2, 'Modo de apertura que no borra', 2, $t$El modo `"a"`$t$),
  ('PY-601', 2, 'Modo de apertura que no borra', 3, $t$El modo `"r"`$t$),
  ('PY-601', 2, 'Modo de apertura que no borra', 4, $t$El modo `"x"`$t$),
  ('PY-701', 1, 'Sintaxis de herencia', 1, $t$`class Perro extends Animal:`$t$),
  ('PY-701', 1, 'Sintaxis de herencia', 2, $t$`class Perro(Animal):`$t$),
  ('PY-701', 1, 'Sintaxis de herencia', 3, $t$`class Perro inherits Animal:`$t$),
  ('PY-701', 1, 'Sintaxis de herencia', 4, $t$`class Perro: Animal`$t$),
  ('PY-701', 1, 'Constructor de la clase padre', 1, $t$`parent()`$t$),
  ('PY-701', 1, 'Constructor de la clase padre', 2, $t$`super()`$t$),
  ('PY-701', 1, 'Constructor de la clase padre', 3, $t$`base()`$t$),
  ('PY-701', 1, 'Constructor de la clase padre', 4, $t$`self.__init__()`$t$),
  ('PY-701', 2, 'Método sobrescrito', 1, $t$El de `Animal`, porque es la clase padre$t$),
  ('PY-701', 2, 'Método sobrescrito', 2, $t$El de `Gato`, porque la subclase sobrescribe el método$t$),
  ('PY-701', 2, 'Método sobrescrito', 3, $t$Ambos, primero el de `Animal` y luego el de `Gato`$t$),
  ('PY-701', 2, 'Método sobrescrito', 4, $t$Ninguno: lanza un error de nombre duplicado$t$),
  ('PY-801', 1, 'Fechas y horas', 1, $t$`time_utils`$t$),
  ('PY-801', 1, 'Fechas y horas', 2, $t$`datetime`$t$),
  ('PY-801', 1, 'Fechas y horas', 3, $t$`fechas`$t$),
  ('PY-801', 1, 'Fechas y horas', 4, $t$`dateparser`$t$),
  ('PY-801', 1, 'Entero aleatorio', 1, $t$`random.random(1, 10)`$t$),
  ('PY-801', 1, 'Entero aleatorio', 2, $t$`random.randint(1, 10)`$t$),
  ('PY-801', 1, 'Entero aleatorio', 3, $t$`random.range(1, 10)`$t$),
  ('PY-801', 1, 'Entero aleatorio', 4, $t$`random.choice(1, 10)`$t$),
  ('PY-801', 2, 'De texto JSON a Python', 1, $t$`json.dumps()`$t$),
  ('PY-801', 2, 'De texto JSON a Python', 2, $t$`json.loads()`$t$),
  ('PY-801', 2, 'De texto JSON a Python', 3, $t$`json.parse()`$t$),
  ('PY-801', 2, 'De texto JSON a Python', 4, $t$`json.decode()`$t$),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 1, $t$`list`$t$),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 2, $t$`dict`$t$),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 3, $t$`tuple`$t$),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 4, $t$`str`$t$)
) AS v(codigo, tema_orden, titulo, orden, texto);


-- 4. Antes de cambiar nada, cada fila referenciada debe existir ----------------

DO $$
DECLARE
  faltan text;
BEGIN
  SELECT string_agg(format('%s módulo %s', v.codigo, v.orden), ', ') INTO faltan
  FROM _fmt_temas v
  WHERE NOT EXISTS (
    SELECT 1 FROM public.temas t JOIN public.cursos c ON c.id = t.curso_id
    WHERE c.codigo_curso = v.codigo AND t.orden = v.orden);
  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0010 abortada: no existen los módulos %.', faltan;
  END IF;

  SELECT string_agg(format('%s módulo %s «%s»', v.codigo, v.tema_orden, v.titulo), ', ') INTO faltan
  FROM (SELECT codigo, tema_orden, titulo FROM _fmt_ejercicios
        UNION SELECT codigo, tema_orden, titulo FROM _fmt_opciones) v
  WHERE NOT EXISTS (
    SELECT 1 FROM public.ejercicios e
    JOIN public.temas t ON t.id = e.tema_id
    JOIN public.cursos c ON c.id = t.curso_id
    WHERE c.codigo_curso = v.codigo AND t.orden = v.tema_orden AND e.titulo = v.titulo
      AND e.tipo <> 'evaluacion_tecnica');
  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0010 abortada: no existen los ejercicios %.', faltan;
  END IF;

  SELECT string_agg(format('%s «%s» opción %s', v.codigo, v.titulo, v.orden), ', ') INTO faltan
  FROM _fmt_opciones v
  WHERE NOT EXISTS (
    SELECT 1 FROM public.opciones_ejercicios o
    JOIN public.ejercicios e ON e.id = o.ejercicio_id
    JOIN public.temas t ON t.id = e.tema_id
    JOIN public.cursos c ON c.id = t.curso_id
    WHERE c.codigo_curso = v.codigo AND t.orden = v.tema_orden AND e.titulo = v.titulo
      AND o.orden = v.orden);
  IF faltan IS NOT NULL THEN
    RAISE EXCEPTION 'Migración 0010 abortada: no existen las opciones %.', faltan;
  END IF;
END $$;


-- 5. Cambios -----------------------------------------------------------------

UPDATE public.temas t
SET descripcion = v.texto
FROM _fmt_temas v
JOIN public.cursos c ON c.codigo_curso = v.codigo
WHERE t.curso_id = c.id AND t.orden = v.orden;

UPDATE public.ejercicios e
SET consigna = v.texto
FROM _fmt_ejercicios v
JOIN public.cursos c ON c.codigo_curso = v.codigo
JOIN public.temas t ON t.curso_id = c.id AND t.orden = v.tema_orden
WHERE e.tema_id = t.id AND e.titulo = v.titulo AND e.tipo <> 'evaluacion_tecnica';

UPDATE public.opciones_ejercicios o
SET texto_opcion = v.texto
FROM _fmt_opciones v
JOIN public.cursos c ON c.codigo_curso = v.codigo
JOIN public.temas t ON t.curso_id = c.id AND t.orden = v.tema_orden
JOIN public.ejercicios e ON e.tema_id = t.id AND e.titulo = v.titulo AND e.tipo <> 'evaluacion_tecnica'
WHERE o.ejercicio_id = e.id AND o.orden = v.orden;

COMMIT;
