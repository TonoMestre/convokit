# CLAUDE.md — ConvoKit

## Qué es este proyecto

ConvoKit es una aplicación web interna de Innóvate 4.0 (consultora de ayudas públicas).
A partir de los documentos oficiales de una convocatoria de ayudas (bases reguladoras,
convocatoria del ejercicio, plantilla de memoria, anexos), genera SEIS entregables
mediante la API de Claude:

1. Guía interna del consultor
2. Ficha comercial para el cliente (.md para Claude design)
3. Landing page (HTML completo desplegable, con la marca Innóvate 4.0)
4. Set de prompts para la memoria (+ JSON)
5. Lista de documentación + correo al cliente (+ JSON)
6. Evaluador de encaje (HTML interactivo desplegable)

Uso exclusivamente interno. Sin clientes finales. Sin autenticación en el MVP.

NOTA: en versiones anteriores del PRD existían dos salidas más (post de LinkedIn y
artículo WordPress). Se han ELIMINADO. El contenido editorial de marca se produce fuera
de ConvoKit, en el flujo editorial propio de Innóvate 4.0, para no arriesgar invención de
datos o experiencia en piezas firmadas públicamente. La guía del consultor (salida 1)
aporta los datos verificados que alimentan ese contenido editorial externo.

## Lee esto antes de cada cambio

Este fichero es la fuente de verdad. Léelo antes de tocar nada. El PRD completo
(docs/ConvoKit_PRD_v2.2.md) tiene el detalle de cada requisito; este fichero es el resumen
operativo.

## Arquitectura

- Monorepo con dos carpetas: /frontend y /backend
- Frontend: React + Vite + Tailwind CSS. Navegación por estado de componente (AppContext),
  sin React Router. Despliegue en Vercel.
- Backend: Python 3.11 + FastAPI. Despliegue en Railway con volumen montado para persistir
  el fichero SQLite.
- Base de datos: SQLite (fichero local persistido en volumen de Railway). Sin Supabase.
- IA: Claude API. Modelo por salida (ver sección max_tokens). Un system prompt distinto
  por tipo de salida, todos en /backend/prompts.py.
- Extracción de documentos: librerías locales de Python, sin consumo de tokens.
  PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX), lectura directa (TXT).
  Lógica en /backend/extractors.py.
- Seguimiento de costes: /backend/pricing.py define modelos y precios. Cada llamada a
  Claude queda registrada en la tabla api_calls. Endpoint GET /stats devuelve gasto total.

## Módulos del backend

- `main.py` — endpoints FastAPI y lógica de generación
- `database.py` — CRUD SQLite
- `prompts.py` — todos los system prompts (nunca incrustados en endpoints)
- `extractors.py` — extracción de texto de PDF/DOCX/XLSX/TXT
- `exporters.py` — exportación de salidas 4 y 5 a JSON estructurado
- `output3_template.py` — inyección de la landing en landing_template.html
- `output6_template.py` — inyección del evaluador en evaluador_template.html
- `pricing.py` — definición de modelos y precios por token; registro en api_calls

## Reglas de código

- Todo el código en inglés: variables, funciones, clases, comentarios técnicos.
- Los textos visibles en la interfaz, en español.
- Los system prompts van en /backend/prompts.py, nunca incrustados en los endpoints.
- La lógica de SQLite va en /backend/database.py.
- La exportación a JSON de las salidas 4 y 5 va en /backend/exporters.py.
- Sin dependencias innecesarias.
- Los errores devueltos al frontend van en español, sin trazas internas. El frontend
  los muestra en un banner visible, no en consola.

## REGLA CRÍTICA: no inventar datos

Ninguna salida puede inventar datos. Todo importe, porcentaje, plazo, requisito, sector,
estadística o afirmación debe salir literalmente de los documentos de la convocatoria.

Prohibido en cualquier salida:
- Inventar cifras, porcentajes o estadísticas que no estén en las bases.
- Inventar experiencia personal o casos ("el X% de las solicitudes que he visto", "en mi
  experiencia", "lo que noto es"). Esto fue el motivo de eliminar las salidas editoriales.
- Afirmar cualquier cosa que no se pueda trazar a los documentos aportados.

Si un dato no está en el documento, no se incluye. Esta regla aplica con especial fuerza a
la salida 3 (landing), que es contenido público de marca.

## Variables de entorno

Backend (.env en /backend):
- ANTHROPIC_API_KEY
- DB_PATH (ruta del fichero SQLite; en Railway apunta al volumen montado)

Frontend (.env en /frontend):
- VITE_API_URL (URL del backend desplegado en Railway)

Nunca subir ficheros .env al repositorio. Mantener .env.example en cada carpeta con las
variables sin valores.

## Control de versiones

- Hacer commit tras cada paso completado y funcional. No acumular cambios sin commit.
- Mensajes de commit en inglés: feat:, fix:, refactor:, docs:.
- Nunca subir .env ni claves.

## Formatos de archivo admitidos

Sin límite de número de archivos por convocatoria. Tipos: PDF, DOCX, XLSX, TXT.
Cada archivo se etiqueta por tipo:
- `bases` — bases reguladoras
- `convocatoria` — convocatoria del ejercicio
- `memoria` — plantilla de memoria
- `resolucion` — resolución de ejercicio anterior
- `correccion` — corrección de errores de la convocatoria
- `guia_convocante` — guía publicada por el organismo convocante
- `adenda` — adenda o modificación posterior
- `anexo` — anexo
- `complementario` — documento complementario

PDF escaneado (sin texto extraíble): mostrar aviso, no intentar OCR.

## Esquema de base de datos

Tres tablas en SQLite:

### convocatorias
- `id` INTEGER PRIMARY KEY
- `nombre` TEXT
- `fecha_creacion` TEXT (ISO 8601)
- `documentos_json` TEXT (JSON array de {nombre, tipo, texto_extraido, paginas, advertencia_ocr})
- `entregables_json` TEXT (JSON dict; ver claves abajo)

Claves de `entregables_json`:
- `"1"` — markdown guía consultor
- `"2"` — markdown ficha comercial
- `"3"` — HTML completo landing (con plantilla y marca aplicada)
- `"3_seo"` — objeto JSON: {seo_title, meta_description, slug, body_html, confirmed, variant}
- `"3_instruccion"` — instrucción libre del usuario para la landing
- `"4"` — markdown set de prompts
- `"4_json"` — JSON array de secciones (ver esquema en PRD sección 12)
- `"4_instruccion"` — instrucción libre del usuario
- `"5"` — markdown lista de documentación + correo
- `"5_json"` — JSON array de documentos (ver esquema en PRD sección 12)
- `"6"` — HTML completo evaluador de encaje

### api_calls
- `id`, `convocatoria_id`, `output_key`, `model`, `input_tokens`, `output_tokens`,
  `cost_usd`, `created_at`

### generation_jobs
- `id`, `convocatoria_id`, `output_key`, `status` (pending/running/done/error),
  `error_msg`, `created_at`, `updated_at`

## Generación asíncrona

Los endpoints de generación lenta (salidas 1, 4, 6) usan generación asíncrona:
- `POST /generate/async` — crea un job en `generation_jobs` y lanza un hilo daemon.
- `GET /jobs/{job_id}` — polling de estado desde el frontend.
- `POST /generate` — síncrono (usado para salidas rápidas 2, 3, 5).
- `POST /generate/stream` — streaming SSE (salida 1 principalmente).

## max_tokens y modelos por salida

| Salida   | Descripción                  | Modelo  | max_tokens           |
|----------|------------------------------|---------|----------------------|
| 1        | Guía del consultor           | Sonnet  | 8192                 |
| 2        | Ficha comercial              | Haiku   | 4096                 |
| 3        | Landing page                 | Haiku   | 6000                 |
| 4        | Set de prompts (markdown)    | Sonnet  | 8192 por sección     |
| 4_json   | Extracción JSON por sección  | Haiku   | 4096 por sección     |
| 5        | Documentación + correo       | Haiku   | 4096                 |
| 6        | Evaluador de encaje          | Sonnet  | 4096                 |

`pricing.MODELS` define los IDs reales: `"sonnet"` = `claude-sonnet-4-6`,
`"haiku"` = `claude-haiku-4-5-20251001`.

## Salida 3 — Landing page

### Generación
Claude devuelve la respuesta en dos bloques separados por marcadores:
```
===SEO_JSON===
{"seo_title": ..., "meta_description": ..., "slug": ...}
===LANDING_HTML===
<section class="hero">...</section>
... (8 secciones más)
```

`output3_template.py` parsea la respuesta, inyecta el cuerpo en `landing_template.html`
y devuelve el HTML completo. El slug no se inserta en el HTML; el usuario lo copia
manualmente a WordPress/Yoast.

### Estructura de secciones (orden fijo, siempre 9)
1. `section.hero` — hero con gancho, H1, descriptor (.hero-sub), cuerpo, botón
2. `section.bloque` — beneficios (lista o grid de cards)
3. `section.bloque` — elegibilidad (quién puede pedir)
4. `section.bloque` — qué financia
5. `section.bloque` — importe y condiciones (con .destacado)
6. `section.bloque` — cómo trabajamos
7. `section.cta.cta-primary` — CTA principal (navy)
8. `section.cta.cta-secondary` — CTA secundario (crema)
9. `section.bloque#contacto` — formulario de contacto

El H1 del hero es SOLO el nombre de la convocatoria (ej. "INPYME"). El descriptor
va en `.hero-sub`, separado. Nunca unir nombre y descriptor con guion ni dash.

### Variantes de color (A y B)
Las variantes solo modifican `background-color` mediante clases CSS en `<body>`.
El `body_html` almacenado en `3_seo.body_html` no se toca entre variantes.

- `body.variante-a`: elegibilidad (nth-child 3) y importe (5) en crema.
- `body.variante-b`: hero en crema (texto navy), qué-financia (4) en crema,
  importe (5) en navy con textos blancos.

La función `build_output_3_html(body_html, seo_title, meta_description, variant)`
en `output3_template.py` acepta `variant="A"` o `"B"` (default `"A"`).
`VALID_VARIANTS = {"A", "B"}`. La variante C fue eliminada.

### Parámetro `modo`
El prompt de salida 3 recibe el campo `modo` de la convocatoria:
- `ABIERTA` — plazo de solicitud activo.
- `ANTICIPADA` — plazo no abierto aún; el copy del CTA cambia en consecuencia.

### Endpoints específicos
- `POST /landing/seo` — confirma los campos SEO (seo_title, meta_description, slug)
  y los persiste en `3_seo.confirmed = true`.
- `POST /landing/variant` — cambia la variante guardada en `3_seo.variant` y
  regenera el HTML completo con la nueva clase sin volver a llamar a Claude.

## Salida 4 — Set de prompts (arquitectura multi-llamada)

La generación de la salida 4 es multi-paso para evitar truncación con convocatorias
largas (INPYME tiene 23 secciones, ~60 K caracteres de markdown):

1. **Extractor de secciones** (`OUTPUT_4_SECTION_EXTRACTOR`): Claude lee los documentos
   y devuelve la lista de secciones de memoria con su título y número.
2. **Generación por sección**: para cada sección, una llamada a Sonnet genera el bloque
   markdown (max_tokens = 8192).
3. **Extracción JSON por sección** (`OUTPUT_4_JSON_EXTRACTOR`): inmediatamente después
   de generar el markdown de cada sección, una llamada a Haiku extrae el objeto JSON
   de esa sección (max_tokens = 4096). Esto evita enviar 60 K chars en una sola llamada.

El JSON final (`4_json`) es un array con un objeto por sección. Los campos
`inputs_minimos` e `inputs_puntuacion_completa` deben ser siempre strings en lenguaje
natural (ej. "Descripción detallada del proyecto"), nunca snake_case ni camelCase.

## Las dos apps (importante)

ConvoKit es la primera de dos aplicaciones. La segunda (App de Memorias) redacta memorias
técnicas y cuentas justificativas a partir de los datos reales de cada empresa.

Las salidas 4 y 5 exportan JSON estructurado precisamente para alimentar la App de Memorias:
- Salida 4 produce el perfil de convocatoria (secciones, baremo, inputs).
- Salida 5 produce el árbol de documentos.

El esquema de campos de ambos JSON (sección 12 del PRD) no debe modificarse sin coordinarlo
con el modelo de datos de la App de Memorias, porque esa app lo consume directamente.

La integración en el MVP es manual: se descarga el JSON de ConvoKit y se carga en la App de
Memorias. No se construye conexión automática entre ambas apps en esta fase.

## Histórico de convocatorias

Cada convocatoria es una entrada independiente en SQLite con su nombre, fecha, documentos
(texto extraído) y entregables generados. Dos convocatorias procesadas el mismo día
coexisten sin pisarse. El usuario puede volver a cualquier convocatoria anterior sin
volver a subir archivos.

## Orden de implementación

1. Scaffold: estructura de carpetas, CLAUDE.md, .env.example, README.md. [HECHO]
2. Backend: database.py con esquema SQLite y CRUD básico. [HECHO]
3. Backend: endpoint de subida con extracción de PDF (PyMuPDF). Test con INPYME 2026. [HECHO]
4. Backend: añadir extracción DOCX y XLSX al endpoint de subida. [HECHO]
5. Backend: endpoint de generación con llamada a Claude API para la Salida 1. Test extremo a extremo. [HECHO]
6. Frontend: layout base (panel histórico + área principal) y flujo de nueva convocatoria. [HECHO]
7. Frontend: visualización de entregables, copiar y descargar. [HECHO]
8. Backend: implementar salidas 2 a 6, una a una, validando cada prompt con INPYME 2026. [HECHO]
8 bis. Backend: exporters.py, exportación de salidas 4 y 5 a JSON. [HECHO]
9. Frontend: histórico y carga de convocatorias anteriores. [HECHO]
10. Despliegue: backend en Railway (con volumen), frontend en Vercel.
11. Test completo con INPYME 2026 y ajuste de prompts.

## Marca Innóvate 4.0 (para la interfaz y las salidas con diseño)

- Colores: azul #1d254c, rojo #c50339, blanco #FFFFFF, negro #000000. Sin otros colores.
  Variable CSS adicional: `--cream: #F2EBD8` (usado en landing y evaluador).
- Tipografía: Roboto Slab (títulos), Inter (cuerpo y UI). Ambas desde Google Fonts.
- Border-radius: 0px en todos los elementos.
- La salida 2 (ficha comercial) sale en .md limpio con jerarquía clara (H1, H2, bullets,
  destacados). El diseño visual lo aplica Claude design después, que ya tiene el design
  system de Innóvate 4.0; no generar frontmatter de marca ni CSS en esa salida.
- La salida 3 (landing) y la salida 6 (evaluador) salen como HTML completo y autocontenido,
  con la marca Innóvate 4.0 ya aplicada, listo para subir a innovate40.es como subcarpeta.
  Ambas usan el mismo patrón: Claude genera solo el contenido variable (cuerpo HTML en la
  salida 3, objeto CFG JSON en la salida 6) y el backend lo inyecta en una plantilla
  estática (backend/landing_template.html y backend/evaluador_template.html) que contiene
  el CSS de marca, la cabecera con logo y el pie. Así la marca nunca depende de que Claude
  reescriba el CSS. El logo se incrusta en base64 para que la vista previa en iframe
  (srcDoc) funcione.
