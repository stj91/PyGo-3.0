export const mockCursos = [
  {
    id: 'fundamentos-python',
    titulo: 'Fundamentos de Python',
    descripcion: 'Aprende las bases esenciales del lenguaje: variables, sintaxis, operaciones aritméticas y manipulaciones de tipos de datos.',
    nivel: 'Principiante',
    progreso: 60,
    modulos: [
      {
        id: 'mod-1',
        titulo: 'Módulo 1: Sintaxis y Variables',
        lecciones: [
          {
            id: 'lec-1-1',
            titulo: 'Variables y Operaciones Básicas',
            duracion: '15 min',
            estado: 'Completado',
            teoria: {
              introduccion: 'En Python, una variable es un contenedor para almacenar valores de datos. No requiere declaración explícita de tipo.',
              explicacion: 'Puedes asignar valores utilizando el operador igual (=). Python infiere automáticamente el tipo de dato según el contenido.',
              codigoEjemplo: '# Declaración de variables\nnombre = "Estudiante"\nedad = 20\nprecio = 49.99\n\n# Imprimir en consola\nprint(nombre)\nprint(type(edad))'
            },
            ejercicio: {
              consigna: '¿Cuál es la salida de ejecutar el siguiente bloque de código en Python?',
              codigo: 'a = "10"\nb = "20"\nprint(a + b)',
              opciones: [
                '30',
                '1020',
                'TypeError',
                '"30"'
              ],
              respuestaCorrecta: 1,
              explicacionRespuesta: 'Debido a que a y b son cadenas de texto (strings), el operador + realiza una concatenación y no una suma aritmética.'
            }
          },
          {
            id: 'lec-1-2',
            titulo: 'Entrada y Salida de Datos',
            duracion: '20 min',
            estado: 'En Curso',
            teoria: {
              introduccion: 'La función input() permite recibir datos ingresados por el usuario desde la terminal, devolviendo siempre una cadena de texto.',
              explicacion: 'Si necesitas trabajar con números, debes convertir la entrada usando int() o float().',
              codigoEjemplo: 'edad = input("Ingresa tu edad: ")\nedad_numero = int(edad)\nprint(f"El próximo año tendrás {edad_numero + 1} años")'
            },
            ejercicio: {
              consigna: 'Si un usuario ingresa el valor "5" en la función input(), ¿qué tipo de dato retorna la llamada?',
              codigo: 'valor = input("Introduce un número: ")',
              opciones: [
                '<class "int">',
                '<class "float">',
                '<class "str">',
                '<class "bool">'
              ],
              respuestaCorrecta: 2,
              explicacionRespuesta: 'La función input() en Python 3 siempre retorna una cadena de texto (str), independientemente de lo que el usuario escriba.'
            }
          }
        ]
      },
      {
        id: 'mod-2',
        titulo: 'Módulo 2: Tipos de Datos Compuestos',
        lecciones: [
          {
            id: 'lec-2-1',
            titulo: 'Listas y Tuplas',
            duracion: '25 min',
            estado: 'Bloqueado',
            teoria: {
              introduccion: 'Las listas son colecciones ordenadas y mutables. Las tuplas son ordenadas pero inmutables.',
              explicacion: 'Utiliza corchetes [] para listas y paréntesis () para tuplas.',
              codigoEjemplo: 'frutas = ["manzana", "banana", "cereza"]\ncoordenadas = (10.4, 20.8)'
            },
            ejercicio: {
              consigna: '¿Qué método se utiliza para agregar un elemento al final de una lista existente?',
              codigo: 'mi_lista = [1, 2, 3]',
              opciones: [
                'mi_lista.add(4)',
                'mi_lista.push(4)',
                'mi_lista.append(4)',
                'mi_lista.insert(4)'
              ],
              respuestaCorrecta: 2,
              explicacionRespuesta: 'El método .append() agrega un elemento al final de la lista en Python.'
            }
          }
        ]
      }
    ]
  },
  {
    id: 'estructuras-control',
    titulo: 'Estructuras de Control',
    descripcion: 'Domina la toma de decisiones con bloques condicionales (if/else) y la repetición de tareas mediante bucles (for/while).',
    nivel: 'Intermedio',
    progreso: 20,
    modulos: [
      {
        id: 'mod-3',
        titulo: 'Módulo 1: Condicionales if / else',
        lecciones: [
          {
            id: 'lec-3-1',
            titulo: 'Evaluación de Condiciones',
            duracion: '20 min',
            estado: 'En Curso',
            teoria: {
              introduccion: 'Las sentencias condicionales permiten ejecutar bloques de código específicos según el cumplimiento de expresiones booleanas.',
              explicacion: 'Python utiliza la sangría (indentación) obligatoria para delimitar el bloque de código de cada condición.',
              codigoEjemplo: 'nota = 85\nif nota >= 90:\n    print("Excelente")\nelif nota >= 70:\n    print("Aprobado")\nelse:\n    print("Reprobado")'
            },
            ejercicio: {
              consigna: '¿Qué resultado imprime el siguiente bloque condicional?',
              codigo: 'x = 5\ny = 10\nif x > 3 and y < 8:\n    print("Condición A")\nelif x == 5 or y == 5:\n    print("Condición B")\nelse:\n    print("Condición C")',
              opciones: [
                'Condición A',
                'Condición B',
                'Condición C',
                'Error de Sintaxis'
              ],
              respuestaCorrecta: 1,
              explicacionRespuesta: 'La primera condición evalúa a False porque y < 8 es falso. La segunda evaluación evalúa a True porque x == 5 es verdadero.'
            }
          }
        ]
      },
      {
        id: 'mod-4',
        titulo: 'Módulo 2: Bucles e Iteraciones',
        lecciones: [
          {
            id: 'lec-4-1',
            titulo: 'Bucle for y la función range()',
            duracion: '30 min',
            estado: 'Bloqueado',
            teoria: {
              introduccion: 'El bucle for se utiliza para iterar sobre una secuencia (lista, tupla, diccionario, conjunto o cadena).',
              explicacion: 'range(inicio, fin, paso) genera una secuencia de números enteros omitiendo el número límite superior.',
              codigoEjemplo: 'for i in range(1, 4):\n    print(f"Número: {i}")'
            },
            ejercicio: {
              consigna: '¿Cuántas veces se imprimirá el texto en la terminal?',
              codigo: 'for k in range(0, 5, 2):\n    print("Iteración")',
              opciones: [
                '5 veces',
                '3 veces',
                '2 veces',
                '4 veces'
              ],
              respuestaCorrecta: 1,
              explicacionRespuesta: 'range(0, 5, 2) genera los valores 0, 2 y 4, por lo que el bucle se ejecuta exactamente 3 veces.'
            }
          }
        ]
      }
    ]
  },
  {
    id: 'poo',
    titulo: 'Programación Orientada a Objetos',
    descripcion: 'Diseña software modular y reutilizable creando clases, objetos, métodos, encapsulamiento y herencia en Python.',
    nivel: 'Avanzado',
    progreso: 0,
    modulos: [
      {
        id: 'mod-5',
        titulo: 'Módulo 1: Clases y Objetos',
        lecciones: [
          {
            id: 'lec-5-1',
            titulo: 'Definición de Clases y el método __init__',
            duracion: '35 min',
            estado: 'Bloqueado',
            teoria: {
              introduccion: 'Las clases sirven como plantillas para crear objetos. El método __init__ es el constructor que inicializa los atributos del objeto.',
              explicacion: 'El parámetro self hace referencia a la instancia actual de la clase.',
              codigoEjemplo: 'class Estudiante:\n    def __init__(self, nombre, carrera):\n        self.nombre = nombre\n        self.carrera = carrera\n\ne1 = Estudiante("Ana", "Computación")\nprint(e1.nombre)'
            },
            ejercicio: {
              consigna: '¿Cuál es el propósito del parámetro "self" en los métodos de una clase en Python?',
              codigo: 'class Vehiculo:\n    def encender(self):\n        print("Motor encendido")',
              opciones: [
                'Es una palabra reservada opcional que puede omitirse',
                'Representa la instancia del objeto que llama al método',
                'Indica que el método es privado y no se puede heredar',
                'Convierte la función en un método estático de clase'
              ],
              respuestaCorrecta: 1,
              explicacionRespuesta: 'self referencia explícitamente a la instancia específica sobre la cual se invoca el método.'
            }
          }
        ]
      }
    ]
  }
];