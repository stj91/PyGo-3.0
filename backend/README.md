# PyGo — Backend Django

Backend de PyGo en Django con estilo funcional. Sustituye por completo al
anterior backend Node/Express y mantiene el mismo contrato HTTP, así que el
frontend React funciona sin ningún cambio.

## Puesta en marcha

```bash
cd backend
pip install -r requirements.txt
python3 manage.py runserver          # escucha en 127.0.0.1:5000
```

La configuración se lee de `backend/.env`; usa `.env.example` como plantilla.
Las variables del entorno real tienen prioridad sobre el fichero.

No hay migraciones ni `manage.py migrate`: los datos viven en Supabase y se
consultan por su API REST.

## Estilo: programación funcional

- **Vistas como funciones**, sin `class`-based views ni DRF. El decorador
  `@endpoint("POST")` aporta lo transversal (método permitido, serialización,
  traducción de errores) para que ninguna vista repita `try/except`.
- **Lógica de negocio en funciones puras**: `nivel_por_aciertos`, `corregir`,
  `calificar`, `configuracion_ui`, `combinar_avance`, `tema_interfaz`... Se
  prueban sin red ni base de datos.
- **Efectos aislados** en los módulos `repository`, y una sola función con E/S
  real (`core/supabase._request`).
- **Datos inmutables**: se devuelven diccionarios nuevos (`{**curso, ...}`), no
  se mutan los argumentos.
- **Utilidades componibles** en `core/functional.py` (`pipe`, `compose`,
  `index_by`, `percentage`...).
- Las únicas clases son las excepciones (en Python no hay alternativa); la
  traducción a HTTP sí son funciones puras (`error_payload`, `error_status`).

## Estructura

```
core/                     plomería compartida
  functional.py           pipe, compose, index_by, percentage...
  env.py                  lectura de .env sin dependencias
  errors.py               jerarquía de errores + traducción pura a HTTP
  http.py                 @endpoint, parse_json_body, require_fields
  auth.py                 require_user / require_self (verificación de token)
  supabase.py             cliente REST funcional (sólo stdlib)
features/<dominio>/
  repository.py           acceso a datos (efectos)
  service.py              reglas puras + orquestación
  views.py                HTTP
pygo/                     settings, urls, wsgi, asgi
```

Capas equivalentes a las del refactor Java-like de `auth`: `views` ->
`service` -> `repository`, con `errors` compartido.

## Endpoints

| Método | Ruta | Autenticación |
|---|---|---|
| POST | `/api/auth/registro` | pública |
| POST | `/api/auth/login` | pública |
| GET | `/api/cursos` | pública (sin `usuario_id`) |
| GET | `/api/cursos?usuario_id=X` | token, y debe ser X |
| GET | `/api/cursos/<id>` | pública |
| GET | `/api/lecciones/<id>` | pública |
| GET | `/api/cursos/lecciones/<id>` | pública (alias) |
| POST | `/api/cold-start/evaluar` | token, y debe ser `usuario_id` |
| POST | `/api/evaluaciones/evaluar-modulo` | token, y debe ser `usuario_id` |
| GET | `/api/adaptativo/estado/<id>` | token, y debe ser `<id>` |
| PUT | `/api/usuarios/configuracion/<id>` | token, y debe ser `<id>` |
| GET | `/health` | pública |

## Autenticación

El backend Express **no autenticaba ningún endpoint**: cualquiera podía leer o
sobrescribir los datos de otra persona pasando su `usuario_id`, y además con la
service-role key, que ignora las políticas RLS de Supabase. Aquí:

- `require_user` valida el `Authorization: Bearer <token>` **contra Supabase**
  (`GET /auth/v1/user`). No se inventa criptografía ni se acepta un token por
  estar presente. Si no se puede verificar, se deniega.
- `require_self` comprueba además que el usuario autenticado sea el dueño del
  recurso (autorización a nivel de acción).
- La validación se memoiza `AUTH_CACHE_SECONDS` (60 por defecto) para no añadir
  una llamada de red por petición. Súbelo o bájalo según cuánto quieras tardar
  en notar una revocación; `0` desactiva la caché.

El contenido del catálogo y de las lecciones se sirve sin sesión, igual que
antes (el frontend no protege esas rutas y cae a datos mock si fallan). Con
`PYGO_REQUIRE_AUTH_FOR_CONTENT=true` también exige token.

El servidor escucha **sólo en 127.0.0.1** y `ALLOWED_HOSTS` sólo admite
loopback. Exponerlo a la red es un cambio deliberado de esas dos cosas.

## Diferencias respecto al esquema real de Supabase

Al portar se comprobó que varios endpoints del backend Node consultaban tablas
y columnas **que no existen**, por lo que fallaban siempre. Aquí están
alineados con el esquema real (`cursos -> temas -> ejercicios ->
opciones_ejercicios`):

| El código Node esperaba | Realidad | Qué hace este backend |
|---|---|---|
| tabla `lecciones` | no existe | `/api/lecciones/<id>` resuelve contra `temas`, la unidad de contenido real |
| `temas.bloqueado`, `temas.lecciones` | no existen | se devuelven `descripcion` y `ejercicios` |
| `ejercicios.enunciado`, `.codigo_base` | son `titulo`, `tipo`, `consigna` | se devuelven los reales |
| `opciones_ejercicios.retroalimentacion` | no existe | mensajes genéricos («¡Correcto!» / «Respuesta incorrecta.») |
| `usuario_preferencias.modo_oscuro` | es el enum `tema_interfaz` (`modo_claro`/`modo_oscuro`) | se traduce el booleano del frontend |
| `usuario_preferencias.dificultad_adaptativa` | no existe | se ignora y se informa en `ignorados` |
| `intentos_ejercicios.tema_id`, `.puntaje_obtenido`, `.requiere_refuerzo` | la tabla es por ejercicio | una fila por ejercicio, con el tiempo total repartido |

`usuario_temas` y `usuario_cursos` tienen `id` serial como clave primaria y sin
índice único sobre `(usuario_id, tema_id)` / `(usuario_id, curso_id)`, así que
el `upsert` del SDK Node insertaba una fila nueva en cada evaluación. Aquí se
usa `upsert_where`, que busca la fila antes de decidir. **No es atómico**: para
cerrarlo del todo conviene añadir en Supabase

```sql
create unique index on usuario_temas  (usuario_id, tema_id);
create unique index on usuario_cursos (usuario_id, curso_id);
```

y entonces `upsert(..., on_conflict=...)` basta.

## Nota sobre `/api/adaptativo/estado/<id>`

Devuelve `{success, configuracion:{...}}`, el contrato original. El
`UserContext` del frontend lee en cambio `res.nivel_asignado`,
`res.opciones_visibles`, `res.porcentaje_avance_global` y
`res.requiere_refuerzo`, que este endpoint nunca ha devuelto: esa
sincronización no hace nada desde antes de la reescritura. Se ha mantenido el
contrato para no cambiar nada por sorpresa.
