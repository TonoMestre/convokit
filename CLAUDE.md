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
- `output3_template.py` — inyección del cuerpo de la landing en landing_template.html
  (bloque scoped, sin doctype/html/head/body) y, si procede, sustitución del marcador
  `<!--EVALUADOR_EMBED-->` por el fragmento del evaluador embebido
- `output6_template.py` — construcción del evaluador: `evaluador_core.html` (motor
  scoped bajo `.evaluador-widget`, reutilizable) envuelto en un shell HTML completo
  para la salida 6 standalone, o servido tal cual (sin shell) como fragmento embebido
  dentro de la salida 3
- `result_email.py` — construcción del HTML de los correos de resultado del evaluador
  (interno a Innóvate y al cliente), enviados vía Resend desde `/submit-evaluation`
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
- RESEND_API_KEY (envío de los correos de resultado del evaluador)
- RESEND_FROM_EMAIL (remitente de esos correos, ej. `Innóvate 4.0 <hola@innovate40.es>`)
- EVALUATOR_INTERNAL_EMAIL (bandeja que recibe el aviso interno de lead de `/submit-evaluation`)
- EVALUATOR_REPLY_TO_EMAIL (reply-to opcional de ambos correos del evaluador)
- BACKEND_URL (URL pública de este backend; la usa el HTML del evaluador para llamar a
  `/submit-evaluation` tanto en la salida 6 standalone como embebido en la salida 3)

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
- `"3"` — HTML de la landing: bloque scoped bajo `#innovate-ayuda-landing-{slug}`, sin
  doctype/html/head/body, listo para pegar en un bloque "HTML personalizado" de WordPress
- `"3_seo"` — objeto JSON: {seo_title, meta_description, slug, h1_recomendado,
  keywords_principales, faqs_sugeridas, body_html, confirmed, variant, incluir_evaluador}
- `"3_instruccion"` — instrucción libre del usuario para la landing
- `"6_cfg"` — objeto JSON de configuración del evaluador (ver "Salida 6"), compartido
  entre la salida 6 standalone y el evaluador embebido en la salida 3 para no generarlo
  (ni redactar sus preguntas) dos veces
- `"4"` — markdown set de prompts
- `"4_json"` — objeto JSON, contrato de exportación v2.0 (ver docs/contrato-convokit.md
  y la sección "Salida 4" más abajo). No es un array: la raíz es
  `{version_esquema, convocatoria, campos_empresa, apartados, datos_aplicativo}`.
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

## Salida 3 — Landing page (fragmento embebible en WordPress)

La landing NO es un documento HTML completo: es un bloque scoped pensado para pegarse
directamente en un bloque "HTML personalizado" de una página de WordPress que ya tiene
su propio `<head>`/`<body>`. Por eso nunca lleva doctype/html/head/body propios, y todo
el SEO (título, meta description, H1, keywords, FAQs) se devuelve como JSON aparte en
vez de inyectarse en un `<head>` que no existe: el consultor lo traslada a mano a
Yoast/RankMath.

### Generación
Claude devuelve la respuesta en dos bloques separados por marcadores:
```
===SEO_JSON===
{"seo_title": ..., "meta_description": ..., "slug": ..., "h1_recomendado": ...,
 "keywords_principales": [...], "faqs_sugeridas": [...]}
===LANDING_HTML===
<section class="hero">...</section>
... (8 ó 9 secciones más, según incluya evaluador embebido)
```

`output3_template.py` parsea la respuesta (`parse_landing_response`) e inyecta el cuerpo
en `landing_template.html` (`build_output_3_html`), que envuelve todo bajo
`<div id="innovate-ayuda-landing-{slug}">` con su propio `<style>` scoped (todos los
selectores prefijados con ese wrapper, sin tocar `*`/`html`/`body`/`:root`) para poder
convivir con el CSS del tema de WordPress sin colisiones. El slug no se inserta en el
HTML; el usuario lo copia manualmente a WordPress/Yoast.

### Evaluador embebido (flag `incluir_evaluador`)
La convocatoria puede pedir que el evaluador de encaje (salida 6) se embeba dentro de
la propia landing, en vez de (o además de) generarse como página standalone:
- El frontend expone un checkbox en la fila de generación de la salida 3
  (`EntregablePanel.jsx`) que fija `incluir_evaluador` en la petición de generación.
- `main.py` inyecta una línea `INCLUIR_EVALUADOR: SI/NO` en el prompt de usuario.
  Si es `SI`, el prompt de Claude añade un CTA temprano en el hero
  (`.btn-outline-light`, nunca `.btn-outline` sobre el fondo navy del hero — sería
  texto navy sobre navy, invisible) que enlaza a `#evaluador-embebido`, y deja el
  literal `<!--EVALUADOR_EMBED-->` en el punto donde debe ir el evaluador.
- `_get_existing_cfg` reutiliza el CFG ya guardado en `3_seo`/`6_cfg` si existe; si no,
  `_generate_evaluador_cfg` genera uno nuevo (mismo prompt que usa la salida 6) y lo
  persiste en `6_cfg` para que la salida 6 standalone, si se genera después, lo reutilice
  sin volver a redactar las mismas preguntas.
- `output3_template.build_output_3_html` sustituye `<!--EVALUADOR_EMBED-->` por
  `output6_template.build_output_6_embed_fragment(cfg)` — el mismo motor que la salida 6,
  pero sin el shell standalone. Si no hay `cfg` o no aparece el marcador, no hace nada.
- `3_seo.incluir_evaluador` persiste la decisión para reflejarla en el panel al recargar.

### Estructura de secciones (orden fijo: 9 sin evaluador, 10 con evaluador)
1. `section.hero` — hero con gancho, H1, descriptor (.hero-sub), cuerpo, botón(es).
   Si `incluir_evaluador`, un segundo botón `.btn-outline-light` hacia `#evaluador-embebido`.
2. `section.bloque` — beneficios (lista o grid de cards)
3. `section.bloque` — elegibilidad (quién puede pedir)
4. `section.bloque` — qué financia
5. `section.bloque` — importe y condiciones (con .destacado)
6. `section.bloque` — cómo trabajamos
7. `section.cta.cta-primary` — CTA principal (navy)
8. `section.cta.cta-secondary` — CTA secundario (crema)
9. `[EVALUADOR EMBEBIDO]` — solo si `incluir_evaluador`; marcador `<!--EVALUADOR_EMBED-->`
9/10. `section.bloque#contacto` — formulario de contacto, con checkbox de consentimiento
   (`.field-check`) enlazando política de privacidad y aviso legal (ver memoria
   `evaluador-privacidad-legal`)

El H1 del hero es SOLO el nombre de la convocatoria (ej. "INPYME"). El descriptor
va en `.hero-sub`, separado. Nunca unir nombre y descriptor con guion ni dash.

### Reglas de diseño equilibrado
Grids de tarjetas siempre en columnas fijas (nunca `auto-fit`, para no producir un
reparto 3+1 con un número de cards no múltiplo de las columnas); listas con
`list-style:none!important` + reset de `::marker` (para no doblar el marcador con el
bullet propio del tema de WordPress); bloques de dos columnas con `align-items:stretch`
para que texto y panel visual queden a la misma altura. Ver memoria
`landing-diseno-equilibrio` para el detalle y el porqué de cada regla.

### Variantes de color (A y B)
Las variantes solo modifican `background-color` mediante una clase CSS en el wrapper
(`{{WRAPPER_SELECTOR}}.variante-a` / `.variante-b`). El `body_html` almacenado en
`3_seo.body_html` no se toca entre variantes.

- `variante-a`: elegibilidad (nth-child 3) y importe (5) en crema.
- `variante-b`: hero en crema (texto navy), qué-financia (4) en crema,
  importe (5) en navy con textos blancos.

La función `build_output_3_html(body_html, slug, variant, cfg=None)` en
`output3_template.py` acepta `variant="A"` o `"B"` (default `"A"`).
`VALID_VARIANTS = {"A", "B"}`. La variante C fue eliminada.

### Parámetro `modo`
El prompt de salida 3 recibe el campo `modo` de la convocatoria:
- `ABIERTA` — plazo de solicitud activo.
- `ANTICIPADA` — plazo no abierto aún; el copy del CTA cambia en consecuencia.

### Endpoints específicos
- `POST /landing/seo` — confirma los campos SEO (seo_title, meta_description, slug,
  h1_recomendado, keywords_principales, faqs_sugeridas) y los persiste en
  `3_seo.confirmed = true`.
- `POST /landing/variant` — cambia la variante guardada en `3_seo.variant` y
  regenera el HTML completo con la nueva clase sin volver a llamar a Claude.

## Salida 6 — Evaluador de encaje

### Motor compartido: `evaluador_core.html` + `output6_template.py`
El evaluador es un único motor HTML/CSS/JS (`backend/evaluador_core.html`), scoped bajo
`.evaluador-widget` (mismo criterio que la landing: ningún selector toca `*`/`html`/
`body`/`:root`, para poder embeberse sin colisión dentro de la salida 3). `output6_template.py`
lo usa de dos formas:
- `build_output_6_html(config)` — el core envuelto en un shell HTML completo
  (doctype/html/head/body) para la salida 6 standalone.
- `build_output_6_embed_fragment(config)` — el core sin shell, para insertarlo en el
  punto `<!--EVALUADOR_EMBED-->` de la salida 3.

Claude solo genera el objeto de configuración CFG (`OUTPUT_6_CONFIG_PROMPT`):
`titulo_corto`, `organismo`, `strip`, `elegibilidad`, `baremo`, `grupos_baremo`,
`puntos_max_total`, `inversion`, `datos_proyecto` (preguntas de cualificación no
puntuables, `tipo` ∈ seleccion/texto_libre/numero/fecha), `textos`. El motor (HTML/CSS/JS)
nunca lo escribe Claude; así la marca y la lógica de gating nunca dependen de que el
modelo reescriba código. `datos_proyecto`, si no está vacío, se muestra en su propia
pantalla (`renderProyecto`) entre los bloques de baremo y el paso de contacto: `seleccion`
como botones tipo `.opcion` (no puntuables, no bloqueantes), `texto_libre`/`numero`/`fecha`
como campos de formulario simples. Las respuestas se guardan en `STATE.respuestas` con
`puntos: 0` para que `calcularScore` las ignore sin necesidad de un caso especial.

### Envío de resultado: gating real, sin fire-and-forget
El resultado del evaluador (elegible o no) NUNCA se muestra hasta que el backend confirma
el envío del correo al cliente. El flujo en el motor (`onContactoSubmit`,
`enviarLeadBloqueo`) es: validar → deshabilitar botón ("Enviando...") → `await` la llamada
a `POST /submit-evaluation` → solo si la respuesta indica éxito se llama a
`renderResultado()`; si falla, se reactiva el botón y se muestra el error, sin revelar el
resultado.

`POST /submit-evaluation` (`main.py`) valida el honeypot y los campos obligatorios, y
envía DOS correos vía Resend (`result_email.py`): uno interno a
`EVALUATOR_INTERNAL_EMAIL` (best-effort, un fallo no bloquea) y uno al cliente
(`lead.email`, éste sí bloqueante — su éxito es lo que gatea `renderResultado`).

### Honeypot antispam
Campo oculto (`.hp-field`, `position:absolute;left:-9999px;opacity:0;pointer-events:none`)
validado en cliente y en servidor. Si viene relleno, no se envía nada pero se responde
como si hubiera ido bien (para no delatar el filtro a un bot).

### Scroll al cambiar de paso: nunca `window.scrollTo`
El motor compartido (`evaluador_core.html`) se embebe como fragmento DOM inline en la
salida 3 (sin iframe: `build_output_6_embed_fragment` inserta el HTML directamente en el
documento de la landing). Por eso `renderScreen` nunca usa `window.scrollTo`, que
desplazaría TODA la página contenedora a `y=0` y perdería el evaluador de la vista —
usa `scrollWidgetToTop()`, que llama a `.evaluador-widget.scrollIntoView({block:"start"})`
para desplazar solo lo necesario y dejar la cabecera del widget arriba del viewport, tanto
si el motor ocupa la página entera (standalone) como si está a mitad de una landing.

Si en el futuro el motor se sirve dentro de un `<iframe>` (por ejemplo, la salida 6
standalone incrustada en otra página mediante `<iframe src="...">`), `scrollIntoView`
ejecutado dentro del iframe solo afecta a su scroll interno; ese caso necesitaría un
puente `postMessage` hacia la página contenedora — no implementado actualmente en
`evaluador_core.html` (sí existe, como referencia, en el demo ad-hoc
`static_demo/inpyme-evaluador.html`, que es una herramienta distinta y no comparte motor).

## Salida 4 — Set de prompts (arquitectura multi-llamada, contrato v2.0)

El JSON de exportación de la salida 4 (`4_json`) sigue el contrato `docs/contrato-convokit.md`
(versión `2.0`), pensado para que la App de Memorias lo importe sin post-proceso de IA ni
revisión manual. La raíz es un OBJETO, no un array:

```json
{
  "version_esquema": "2.0",
  "convocatoria": {"nombre", "anio", "organismo", "tipo_ayuda", "fecha_generacion"},
  "campos_empresa": [{"id", "nombre", "descripcion", "formato"}],
  "apartados": [{
    "codigo", "nombre", "puntos_max", "prompt",
    "requiere_calculo_rentabilidad", "usa_tabla_inversiones",
    "inputs": [{"id", "label", "tipo", "nivel", "ayuda"?, "ref_campo_empresa"?}],
    "documentos_requeridos": [{"nombre", "fuente"}]
  }],
  "datos_aplicativo": [{"id", "label", "tipo_dato", "ambito", "obligatorio", "opciones"?}]
}
```

`apartados` contiene SOLO contenido narrativo real de la memoria (lo que el consultor
redacta). Cualquier exigencia de las bases o del formulario telemático que se resuelva con
un valor puntual (URL, número, sí/no, fecha, selección) va en `datos_aplicativo`, nunca
como apartado: `datos_aplicativo` no genera prompt ni se envía a Claude para redactar.

Vocabularios cerrados: `inputs[].tipo` ∈ `texto_libre | dato_empresa | inversion |
rentabilidad | documento`; `inputs[].nivel` ∈ `minimo | completo`; `documentos_requeridos[].fuente`
∈ `cliente | perfil_estrategico | generado`; `campos_empresa[].formato` ∈ `texto |
tabla_historica | numero`; `datos_aplicativo[].tipo_dato` ∈ `texto_corto | numero | booleano
| fecha | url | seleccion`; `datos_aplicativo[].ambito` ∈ `empresa | proyecto`;
`convocatoria.tipo_ayuda` ∈ `inversion_productiva | digitalizacion | idi |
internacionalizacion | medioambiente_energia | empleo | otro`.

La generación es multi-paso para evitar truncación con convocatorias largas (INPYME tiene
23 secciones, ~60 K caracteres de markdown) y para poder deduplicar semánticamente entre
apartados, algo que una sola llamada sobre el markdown completo no puede hacer bien.
Todo el pipeline vive en `_generate_output_4` (`backend/main.py`):

1. **Metadatos + secciones** (`SECTION_EXTRACTOR_PROMPT`): una llamada lee los documentos
   completos y devuelve `{convocatoria: {...}, secciones: [...]}`.
2. **Generación por sección** (`SECTION_PROMPT_SYSTEM`): para cada sección, una llamada a
   Sonnet genera el bloque markdown (max_tokens = 8192), con dos flags explícitos
   (`Requiere cálculo de rentabilidad` / `Usa tabla de inversiones`) y los datos a aportar
   repartidos en tres bloques (datos generales de empresa / imprescindible / mejora
   puntuación) en vez de listas libres.
3. **Extracción JSON por sección** (`OUTPUT_4_JSON_EXTRACTOR`): inmediatamente después de
   generar el markdown de cada sección, una llamada a Haiku extrae el objeto JSON tipado
   de ese apartado (max_tokens = 4096). Esto evita enviar 60 K chars en una sola llamada.
   Los `ref_campo_empresa` que produce esta llamada son IDs provisionales por apartado.
4. **Desambiguación de códigos** (Python, sin llamada a Claude): si dos apartados comparten
   `codigo`, se añade un sufijo numérico (`-2`, `-3`...) para garantizar unicidad.
5. **Consolidación de `campos_empresa`** (`OUTPUT_4_CAMPOS_EMPRESA_CONSOLIDATOR`): una
   llamada a Haiku recibe todas las propuestas de `dato_empresa` de todos los apartados y
   devuelve el catálogo deduplicado más un remapeo que `main.py` aplica in place a los
   `ref_campo_empresa` de cada apartado. Esto resuelve que "datos económicos" en un
   apartado y "cifras financieras" en otro apunten al mismo campo aunque se hayan
   generado en llamadas aisladas.
6. **Extracción de `datos_aplicativo`** (`OUTPUT_4_DATOS_APLICATIVO_EXTRACTOR`): una
   llamada a Haiku sobre el contexto completo (no solo la plantilla de memoria) identifica
   los datos de formulario/aplicativo, evitando duplicar lo que ya está en `campos_empresa`.

`exporters.export_output_4` normaliza el objeto final antes de servirlo: fuerza los
vocabularios cerrados, descarta placeholders de la lista negra ("no aplica", "ya
incluido", "ver otro apartado"...) y elimina `ref_campo_empresa` huérfanos.

## Las dos apps (importante)

ConvoKit es la primera de dos aplicaciones. La segunda (App de Memorias) redacta memorias
técnicas y cuentas justificativas a partir de los datos reales de cada empresa.

Las salidas 4 y 5 exportan JSON estructurado precisamente para alimentar la App de Memorias:
- Salida 4 produce el perfil de convocatoria (contrato `docs/contrato-convokit.md` v2.0:
  convocatoria, campos_empresa, apartados, datos_aplicativo).
- Salida 5 produce el árbol de documentos (esquema en PRD sección 12).

El esquema de ambos JSON no debe modificarse sin coordinarlo con el modelo de datos de la
App de Memorias, porque esa app lo consume directamente. Cualquier cambio de contrato para
la salida 4 se documenta primero en `docs/contrato-convokit.md`.

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
- La salida 3 (landing) es un fragmento HTML scoped listo para pegar en un bloque "HTML
  personalizado" de WordPress (ver "Salida 3" arriba); la salida 6 (evaluador) sale como
  HTML completo y autocontenido para alojar en innovate40.es como subcarpeta, o embebido
  dentro de la propia salida 3. Ambas usan el mismo patrón: Claude genera solo el
  contenido variable (cuerpo HTML en la salida 3, objeto CFG JSON en la salida 6) y el
  backend lo inyecta en una plantilla estática (backend/landing_template.html,
  backend/evaluador_core.html) que contiene el CSS de marca, la cabecera con logo y el
  pie. Así la marca nunca depende de que Claude reescriba el CSS. El logo se incrusta en
  base64 para que la vista previa en iframe (srcDoc) funcione.
