-- 0003_cursos_adicionales.sql
--
-- Cinco cursos nuevos que continúan el itinerario de PY-101..PY-301:
--
--   PY-401  Funciones y Modularidad
--   PY-501  Colecciones Avanzadas y Comprensiones
--   PY-601  Manejo de Errores y Archivos
--   PY-701  Herencia y Polimorfismo
--   PY-801  Librerías y Datos Externos
--
-- Replica el molde de los cursos existentes: 2 temas por curso, 2 ejercicios por
-- tema (tipo ejercicio_practico) y 4 opciones por ejercicio con exactamente una
-- correcta. Total: 5 cursos, 10 temas, 20 ejercicios, 80 opciones.
--
-- A diferencia de 0002, esta migración NO fija ids: resuelve las claves ajenas
-- por clave natural (codigo_curso -> temas.orden -> ejercicios.titulo), así que
-- da el mismo resultado sobre la base actual (donde las identidades siguen en 3,
-- 5, 10 y 40) y sobre una recreada desde cero.
--
-- Es idempotente: cada INSERT lleva su guarda, de modo que volver a aplicarla no
-- duplica nada.

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;


-- 1. Cursos ------------------------------------------------------------------

INSERT INTO public.cursos (codigo_curso, titulo, descripcion)
VALUES
  ('PY-401', 'Funciones y Modularidad',
   'Escribe código reutilizable con funciones: parámetros, valores de retorno, alcance de variables y organización en módulos.'),
  ('PY-501', 'Colecciones Avanzadas y Comprensiones',
   'Organiza datos con diccionarios y conjuntos, y transforma colecciones en una sola línea con comprensiones de listas.'),
  ('PY-601', 'Manejo de Errores y Archivos',
   'Escribe programas que no se detienen ante lo inesperado: captura excepciones con try/except y lee o escribe ficheros de forma segura.'),
  ('PY-701', 'Herencia y Polimorfismo',
   'Reutiliza y especializa clases mediante herencia, sobrescritura de métodos y polimorfismo aplicados al diseño orientado a objetos.'),
  ('PY-801', 'Librerías y Datos Externos',
   'Conecta tus programas con el mundo: módulos de la librería estándar, datos en formato JSON y consumo de APIs.')
ON CONFLICT (codigo_curso) DO NOTHING;


-- 2. Temas -------------------------------------------------------------------

INSERT INTO public.temas (curso_id, orden, titulo, descripcion)
SELECT c.id, v.orden, v.titulo, v.descripcion
FROM (VALUES
  ('PY-401', 1, 'Definición y Parámetros',
   'Las funciones se declaran con def y pueden recibir parámetros con valores por defecto. La sentencia return devuelve un resultado; sin ella la función devuelve None.'),
  ('PY-401', 2, 'Alcance y Módulos',
   'Una variable asignada dentro de una función es local y no existe fuera de ella. Con import se reutiliza código de otros módulos, y from modulo import nombre trae solo una parte.'),

  ('PY-501', 1, 'Diccionarios y Conjuntos',
   'Un diccionario {} guarda pares clave-valor y se consulta por clave, no por posición. Un conjunto set() no admite elementos repetidos ni conserva el orden de inserción.'),
  ('PY-501', 2, 'Comprensión de Listas',
   'Una comprensión con la forma [expresion for elemento in secuencia if condicion] construye una lista nueva recorriendo otra, y sustituye al bucle for con append.'),

  ('PY-601', 1, 'Excepciones con try / except',
   'El bloque try contiene el código que puede fallar y except captura el error indicado. El bloque finally se ejecuta siempre, haya ocurrido una excepción o no.'),
  ('PY-601', 2, 'Lectura y Escritura de Ficheros',
   'La función open() abre un fichero en modo "r" para leer, "w" para sobrescribir y "a" para añadir al final. Usar with open(...) as f cierra el fichero automáticamente.'),

  ('PY-701', 1, 'Herencia entre Clases',
   'Una subclase declarada como class Hija(Padre) hereda los atributos y métodos de la clase padre. La llamada super().__init__() invoca el constructor heredado.'),
  ('PY-701', 2, 'Sobrescritura y Polimorfismo',
   'Sobrescribir un método es volver a definirlo en la subclase con el mismo nombre. El polimorfismo permite tratar objetos de clases distintas a través de la misma interfaz.'),

  ('PY-801', 1, 'La Librería Estándar',
   'Python incluye módulos listos para usar: datetime para fechas y horas, random para valores aleatorios, os para el sistema de ficheros y json para intercambio de datos.'),
  ('PY-801', 2, 'JSON y Consumo de APIs',
   'JSON es el formato estándar para intercambiar datos entre cliente y servidor. json.loads() convierte texto JSON en estructuras de Python y json.dumps() hace lo contrario.')
) AS v(codigo, orden, titulo, descripcion)
JOIN public.cursos c ON c.codigo_curso = v.codigo
WHERE NOT EXISTS (
  SELECT 1 FROM public.temas t WHERE t.curso_id = c.id AND t.orden = v.orden
);


-- 3. Ejercicios --------------------------------------------------------------

INSERT INTO public.ejercicios (tema_id, titulo, tipo, consigna)
SELECT t.id, v.titulo, 'ejercicio_practico'::public.tipo_ejercicio, v.consigna
FROM (VALUES
  -- PY-401
  ('PY-401', 1, 'Retorno implícito',
   '¿Qué valor devuelve una función que termina sin ejecutar ninguna sentencia return?'),
  ('PY-401', 1, 'Parámetros con valor por defecto',
   'Dada def saludar(nombre, saludo="Hola"): return saludo + ", " + nombre, ¿qué devuelve la llamada saludar("Ana")?'),
  ('PY-401', 2, 'Alcance de una variable local',
   'Si una variable se asigna dentro de una función, ¿desde dónde se puede leer?'),
  ('PY-401', 2, 'Importar un solo nombre',
   '¿Qué sentencia importa únicamente la función sqrt del módulo math?'),

  -- PY-501
  ('PY-501', 1, 'Acceso seguro a un diccionario',
   '¿Qué devuelve la expresión {"a": 1}.get("b", 0) cuando la clave "b" no existe?'),
  ('PY-501', 1, 'Eliminación de duplicados',
   '¿Cuántos elementos tiene el conjunto set([1, 2, 2, 3, 3, 3])?'),
  ('PY-501', 2, 'Resultado de una comprensión',
   '¿Qué lista produce la comprensión [n * 2 for n in range(4)]?'),
  ('PY-501', 2, 'Filtrado con condición',
   '¿Qué lista produce la comprensión [n for n in [1, 2, 3, 4, 5, 6] if n % 2 == 0]?'),

  -- PY-601
  ('PY-601', 1, 'División por cero',
   '¿Qué excepción lanza Python al ejecutar la operación 10 / 0?'),
  ('PY-601', 1, 'El bloque finally',
   '¿Cuándo se ejecuta el bloque finally de una estructura try/except?'),
  ('PY-601', 2, 'Modo de apertura que no borra',
   '¿Qué modo de open() añade texto al final de un fichero sin borrar su contenido?'),
  ('PY-601', 2, 'Cierre automático con with',
   '¿Cuál es la ventaja de usar with open("datos.txt") as f en lugar de f = open("datos.txt")?'),

  -- PY-701
  ('PY-701', 1, 'Sintaxis de herencia',
   '¿Cómo se declara una clase Perro que hereda de la clase Animal?'),
  ('PY-701', 1, 'Constructor de la clase padre',
   '¿Qué función se usa dentro de una subclase para invocar el método __init__ de su clase padre?'),
  ('PY-701', 2, 'Método sobrescrito',
   'Si Animal define el método hablar() y Gato(Animal) también lo define, ¿qué método ejecuta la llamada Gato().hablar()?'),
  ('PY-701', 2, 'Concepto de polimorfismo',
   '¿Qué describe el polimorfismo en programación orientada a objetos?'),

  -- PY-801
  ('PY-801', 1, 'Fechas y horas',
   '¿Qué módulo de la librería estándar se usa para trabajar con fechas y horas?'),
  ('PY-801', 1, 'Entero aleatorio',
   '¿Qué función del módulo random devuelve un entero aleatorio entre 1 y 10, ambos incluidos?'),
  ('PY-801', 2, 'De texto JSON a Python',
   '¿Qué función convierte una cadena con formato JSON en un diccionario de Python?'),
  ('PY-801', 2, 'Equivalente de un objeto JSON',
   'Al convertir el JSON {"nombre": "Ana", "edad": 20} a Python, ¿qué tipo de dato se obtiene?')
) AS v(codigo, tema_orden, titulo, consigna)
JOIN public.cursos c ON c.codigo_curso = v.codigo
JOIN public.temas  t ON t.curso_id = c.id AND t.orden = v.tema_orden
WHERE NOT EXISTS (
  SELECT 1 FROM public.ejercicios e WHERE e.tema_id = t.id AND e.titulo = v.titulo
);


-- 4. Opciones ----------------------------------------------------------------

INSERT INTO public.opciones_ejercicios (ejercicio_id, orden, texto_opcion, es_correcta)
SELECT e.id, v.orden, v.texto_opcion, v.es_correcta
FROM (VALUES
  -- PY-401 / tema 1
  ('PY-401', 1, 'Retorno implícito', 1, '0', false),
  ('PY-401', 1, 'Retorno implícito', 2, 'None', true),
  ('PY-401', 1, 'Retorno implícito', 3, 'False', false),
  ('PY-401', 1, 'Retorno implícito', 4, 'La cadena vacía ""', false),

  ('PY-401', 1, 'Parámetros con valor por defecto', 1, '"Hola, Ana"', true),
  ('PY-401', 1, 'Parámetros con valor por defecto', 2, '", Ana"', false),
  ('PY-401', 1, 'Parámetros con valor por defecto', 3, 'TypeError: falta un argumento', false),
  ('PY-401', 1, 'Parámetros con valor por defecto', 4, '"Ana, Hola"', false),

  -- PY-401 / tema 2
  ('PY-401', 2, 'Alcance de una variable local', 1, 'Desde cualquier parte del programa', false),
  ('PY-401', 2, 'Alcance de una variable local', 2, 'Solo dentro de esa función (ámbito local)', true),
  ('PY-401', 2, 'Alcance de una variable local', 3, 'Desde cualquier otra función del mismo fichero', false),
  ('PY-401', 2, 'Alcance de una variable local', 4, 'Desde el módulo que la importa', false),

  ('PY-401', 2, 'Importar un solo nombre', 1, 'import sqrt from math', false),
  ('PY-401', 2, 'Importar un solo nombre', 2, 'from math import sqrt', true),
  ('PY-401', 2, 'Importar un solo nombre', 3, 'import math.sqrt', false),
  ('PY-401', 2, 'Importar un solo nombre', 4, 'include math.sqrt', false),

  -- PY-501 / tema 1
  ('PY-501', 1, 'Acceso seguro a un diccionario', 1, 'Lanza KeyError', false),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 2, '0', true),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 3, 'None', false),
  ('PY-501', 1, 'Acceso seguro a un diccionario', 4, 'False', false),

  ('PY-501', 1, 'Eliminación de duplicados', 1, '6', false),
  ('PY-501', 1, 'Eliminación de duplicados', 2, '3', true),
  ('PY-501', 1, 'Eliminación de duplicados', 3, '2', false),
  ('PY-501', 1, 'Eliminación de duplicados', 4, '1', false),

  -- PY-501 / tema 2
  ('PY-501', 2, 'Resultado de una comprensión', 1, '[0, 2, 4, 6]', true),
  ('PY-501', 2, 'Resultado de una comprensión', 2, '[2, 4, 6, 8]', false),
  ('PY-501', 2, 'Resultado de una comprensión', 3, '[0, 1, 2, 3]', false),
  ('PY-501', 2, 'Resultado de una comprensión', 4, '[8]', false),

  ('PY-501', 2, 'Filtrado con condición', 1, '[1, 3, 5]', false),
  ('PY-501', 2, 'Filtrado con condición', 2, '[2, 4, 6]', true),
  ('PY-501', 2, 'Filtrado con condición', 3, '[True, False, True]', false),
  ('PY-501', 2, 'Filtrado con condición', 4, '[2, 4, 6, 8]', false),

  -- PY-601 / tema 1
  ('PY-601', 1, 'División por cero', 1, 'ValueError', false),
  ('PY-601', 1, 'División por cero', 2, 'ZeroDivisionError', true),
  ('PY-601', 1, 'División por cero', 3, 'ArithmeticOverflow', false),
  ('PY-601', 1, 'División por cero', 4, 'TypeError', false),

  ('PY-601', 1, 'El bloque finally', 1, 'Solo si no hubo ninguna excepción', false),
  ('PY-601', 1, 'El bloque finally', 2, 'Siempre, haya ocurrido una excepción o no', true),
  ('PY-601', 1, 'El bloque finally', 3, 'Solo si la excepción se capturó en un except', false),
  ('PY-601', 1, 'El bloque finally', 4, 'Solo cuando la excepción no fue capturada', false),

  -- PY-601 / tema 2
  ('PY-601', 2, 'Modo de apertura que no borra', 1, 'El modo "w"', false),
  ('PY-601', 2, 'Modo de apertura que no borra', 2, 'El modo "a"', true),
  ('PY-601', 2, 'Modo de apertura que no borra', 3, 'El modo "r"', false),
  ('PY-601', 2, 'Modo de apertura que no borra', 4, 'El modo "x"', false),

  ('PY-601', 2, 'Cierre automático con with', 1, 'Lee el fichero más rápido', false),
  ('PY-601', 2, 'Cierre automático con with', 2, 'Cierra el fichero automáticamente al salir del bloque', true),
  ('PY-601', 2, 'Cierre automático con with', 3, 'Permite abrir el fichero sin tener permisos', false),
  ('PY-601', 2, 'Cierre automático con with', 4, 'Convierte el contenido en una lista de líneas', false),

  -- PY-701 / tema 1
  ('PY-701', 1, 'Sintaxis de herencia', 1, 'class Perro extends Animal:', false),
  ('PY-701', 1, 'Sintaxis de herencia', 2, 'class Perro(Animal):', true),
  ('PY-701', 1, 'Sintaxis de herencia', 3, 'class Perro inherits Animal:', false),
  ('PY-701', 1, 'Sintaxis de herencia', 4, 'class Perro: Animal', false),

  ('PY-701', 1, 'Constructor de la clase padre', 1, 'parent()', false),
  ('PY-701', 1, 'Constructor de la clase padre', 2, 'super()', true),
  ('PY-701', 1, 'Constructor de la clase padre', 3, 'base()', false),
  ('PY-701', 1, 'Constructor de la clase padre', 4, 'self.__init__()', false),

  -- PY-701 / tema 2
  ('PY-701', 2, 'Método sobrescrito', 1, 'El de Animal, porque es la clase padre', false),
  ('PY-701', 2, 'Método sobrescrito', 2, 'El de Gato, porque la subclase sobrescribe el método', true),
  ('PY-701', 2, 'Método sobrescrito', 3, 'Ambos, primero el de Animal y luego el de Gato', false),
  ('PY-701', 2, 'Método sobrescrito', 4, 'Ninguno: lanza un error de nombre duplicado', false),

  ('PY-701', 2, 'Concepto de polimorfismo', 1, 'Que una clase pueda tener varios constructores', false),
  ('PY-701', 2, 'Concepto de polimorfismo', 2, 'Que objetos de clases distintas respondan al mismo método de forma propia', true),
  ('PY-701', 2, 'Concepto de polimorfismo', 3, 'Que los atributos cambien de tipo en tiempo de ejecución', false),
  ('PY-701', 2, 'Concepto de polimorfismo', 4, 'Que una clase herede de varias clases a la vez', false),

  -- PY-801 / tema 1
  ('PY-801', 1, 'Fechas y horas', 1, 'time_utils', false),
  ('PY-801', 1, 'Fechas y horas', 2, 'datetime', true),
  ('PY-801', 1, 'Fechas y horas', 3, 'fechas', false),
  ('PY-801', 1, 'Fechas y horas', 4, 'dateparser', false),

  ('PY-801', 1, 'Entero aleatorio', 1, 'random.random(1, 10)', false),
  ('PY-801', 1, 'Entero aleatorio', 2, 'random.randint(1, 10)', true),
  ('PY-801', 1, 'Entero aleatorio', 3, 'random.range(1, 10)', false),
  ('PY-801', 1, 'Entero aleatorio', 4, 'random.choice(1, 10)', false),

  -- PY-801 / tema 2
  ('PY-801', 2, 'De texto JSON a Python', 1, 'json.dumps()', false),
  ('PY-801', 2, 'De texto JSON a Python', 2, 'json.loads()', true),
  ('PY-801', 2, 'De texto JSON a Python', 3, 'json.parse()', false),
  ('PY-801', 2, 'De texto JSON a Python', 4, 'json.decode()', false),

  ('PY-801', 2, 'Equivalente de un objeto JSON', 1, 'list', false),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 2, 'dict', true),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 3, 'tuple', false),
  ('PY-801', 2, 'Equivalente de un objeto JSON', 4, 'str', false)
) AS v(codigo, tema_orden, ejercicio_titulo, orden, texto_opcion, es_correcta)
JOIN public.cursos     c ON c.codigo_curso = v.codigo
JOIN public.temas      t ON t.curso_id = c.id AND t.orden = v.tema_orden
JOIN public.ejercicios e ON e.tema_id = t.id AND e.titulo = v.ejercicio_titulo
WHERE NOT EXISTS (
  SELECT 1 FROM public.opciones_ejercicios o
  WHERE o.ejercicio_id = e.id AND o.orden = v.orden
);


-- 5. Comprobación ------------------------------------------------------------
-- Cada ejercicio nuevo debe tener exactamente 4 opciones y 1 correcta. Si no,
-- se aborta la transacción: es mejor no aplicar nada que dejar un ejercicio
-- imposible de responder.

DO $$
DECLARE
  malos integer;
BEGIN
  SELECT count(*) INTO malos
  FROM public.ejercicios e
  JOIN public.temas  t ON t.id = e.tema_id
  JOIN public.cursos c ON c.id = t.curso_id
  WHERE c.codigo_curso IN ('PY-401', 'PY-501', 'PY-601', 'PY-701', 'PY-801')
    AND (
      (SELECT count(*) FROM public.opciones_ejercicios o WHERE o.ejercicio_id = e.id) <> 4
      OR
      (SELECT count(*) FROM public.opciones_ejercicios o
        WHERE o.ejercicio_id = e.id AND o.es_correcta) <> 1
    );

  IF malos > 0 THEN
    RAISE EXCEPTION
      'Migración 0003 abortada: % ejercicio(s) no tienen 4 opciones con exactamente 1 correcta.',
      malos;
  END IF;
END $$;


COMMIT;
