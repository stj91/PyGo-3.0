# Migraciones SQL

Migraciones numeradas que se aplican con `python3 manage.py migrar_sql`. No son
migraciones de Django: el proyecto no usa el ORM (`DATABASES = {}`), así que
`makemigrations` no tendría modelos de los que partir. El runner vive en
`core/migraciones.py` y delega la ejecución en `psql`.

## Uso

```bash
cd backend
python3 manage.py migrar_sql --listar     # estado de cada migración
python3 manage.py migrar_sql --simular    # qué se aplicaría, sin tocar nada
python3 manage.py migrar_sql              # aplica lo pendiente, en orden
```

La conexión se lee de `backend/.env` (`SUPABASE_DB_HOST`, `SUPABASE_DB_USER`...).
La contraseña se pide por teclado si `SUPABASE_DB_PASSWORD` está vacía, que es
como viene: `.env` se versiona en este proyecto y ahí no debe quedar.

**Usa el pooler**, no `db.<ref>.supabase.co`. Ese host solo publica registro
AAAA (IPv6) y desde una red sin IPv6 la conexión da timeout sin llegar a
autenticarse. El host correcto está en el dashboard, en
*Project Settings → Database → Connection string → Session pooler*, y el usuario
es `postgres.<project-ref>`, no `postgres`.

## Estado actual

| Migración | Contenido | Cómo se aplicó |
|---|---|---|
| `0001_esquema_base.sql` | 13 tablas y 5 enums: el esquema tal como estaba el 2026-11-11 | **sellada** |
| `0002_cursos_iniciales.sql` | los 3 cursos creados a mano en el dashboard (PY-101..PY-301) | **sellada** |
| `0003_cursos_adicionales.sql` | 5 cursos nuevos (PY-401..PY-801), 10 temas, 20 ejercicios, 80 opciones | ejecutada |
| `0004_carreras_centros.sql` | catálogos `carreras` (30) y `centros` (17), claves ajenas en `usuarios` y relleno de los existentes | ejecutada |

## Sellar en lugar de ejecutar

`0001` y `0002` describen cosas que **ya existían** antes de que hubiera
migraciones. Ejecutarlas contra la base de datos actual falla, y debe fallar:
`create table public.cursos (...)` sobre una tabla que ya está ahí da
`42P07: relation already exists`.

Por eso se registraron con `--sellar`, que anota la fila en `schema_migrations`
sin ejecutar el fichero:

```bash
python3 manage.py migrar_sql --sellar 0001
python3 manage.py migrar_sql --sellar 0002
```

Es el mismo mecanismo que `migrate --fake` en Django, `baseline` en Flyway o
`supabase migration repair --status applied`. En la tabla de control quedan con
`sellada = true` para que se sepa que su SQL nunca corrió aquí.

Su utilidad es recrear la base **desde cero** en otro sitio —una rama de
Supabase, un Postgres local, la máquina de otra persona— ejecutando `0001`,
`0002` y `0003` en orden. Sin `0002`, una base recreada tendría los cursos
PY-401..PY-801 sin los PY-101..PY-301 delante.

## Convenciones al añadir una migración

1. Nombre `NNNN_descripcion_en_snake_case.sql`, con `NNNN` consecutivo. El
   runner ignora cualquier `.sql` que no encaje con ese patrón.
2. Envuelve los cambios en `BEGIN; ... COMMIT;`. El runner ejecuta con
   `ON_ERROR_STOP=1`, así que un error a mitad aborta el fichero entero.
3. Hazla idempotente (`ON CONFLICT DO NOTHING`, `WHERE NOT EXISTS`). Es lo que
   permite reaplicarla sin duplicar datos si algo quedó a medias.
4. Para las claves ajenas, resuelve por **clave natural** en vez de fijar ids.
   `0003` busca el curso por `codigo_curso` y el tema por `(curso_id, orden)`,
   de modo que funciona igual sobre la base actual y sobre una recreada, donde
   las identidades empiezan en otro número.
5. Si añades contenido, comprueba la forma al final. `0003` aborta la
   transacción si algún ejercicio nuevo no acaba con 4 opciones y exactamente 1
   correcta: mejor no aplicar nada que dejar un ejercicio sin respuesta válida.

**No edites una migración ya aplicada.** El runner guarda un checksum de cada
fichero y avisa (`MODIFICADA TRAS APLICARSE`) cuando el contenido ya no coincide
con lo que se ejecutó, porque a partir de ese momento el repo y la base de datos
han divergido en silencio. Para cambiar algo, añade una migración nueva.
