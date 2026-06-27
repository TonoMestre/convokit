# CLAUDE.md — ConvoKit

## Qué es este proyecto

ConvoKit es una aplicación web interna de Innóvate 4.0 (consultora de ayudas públicas).
A partir de los documentos oficiales de una convocatoria de ayudas (bases reguladoras,
convocatoria del ejercicio, plantilla de memoria, anexos), genera CINCO entregables
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
- IA: Claude API, modelo claude-sonnet-4-6. Un system prompt distinto por tipo de salida,
  todos en /backend/prompts.py.
- Extracción de documentos: librerías locales de Python, sin consumo de tokens.
  PyMuPDF (PDF), python-docx (DOCX), openpyxl (XLSX), lectura directa (TXT).

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
Cada archivo se etiqueta por tipo: bases reguladoras, convocatoria del ejercicio,
plantilla de memoria, resolución de ejercicio anterior, anexo o documento complementario.
PDF escaneado (sin texto extraíble): mostrar aviso, no intentar OCR.

## Histórico de convocatorias

Cada convocatoria es una entrada independiente en SQLite con su nombre, fecha, documentos
(texto extraído) y entregables generados. Dos convocatorias procesadas el mismo día
coexisten sin pisarse. El usuario puede volver a cualquier convocatoria anterior sin
volver a subir archivos.

## max_tokens por salida

- Salida 1 (guía del consultor): 8192 (es extensa, incluye baremo completo).
- Salida 4 (set de prompts): 8192 (un prompt por sección de la memoria).
- Salidas 2, 3 y 5: 4096.

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

## Orden de implementación

Seguir este orden. Validar cada paso antes de seguir al siguiente.

1. Scaffold: estructura de carpetas, CLAUDE.md, .env.example, README.md. [HECHO]
2. Backend: database.py con esquema SQLite y CRUD básico. [HECHO]
3. Backend: endpoint de subida con extracción de PDF (PyMuPDF). Test con INPYME 2026.
4. Backend: añadir extracción DOCX y XLSX al endpoint de subida.
5. Backend: endpoint de generación con llamada a Claude API para la Salida 1. Test extremo a extremo.
6. Frontend: layout base (panel histórico + área principal) y flujo de nueva convocatoria.
7. Frontend: visualización de entregables, copiar y descargar.
8. Backend: implementar salidas 2 a 5, una a una, validando cada prompt con INPYME 2026.
8 bis. Backend: exporters.py, exportación de salidas 4 y 5 a JSON.
9. Frontend: histórico y carga de convocatorias anteriores.
10. Despliegue: backend en Railway (con volumen), frontend en Vercel.
11. Test completo con INPYME 2026 y ajuste de prompts.

## Marca Innóvate 4.0 (para la interfaz y las salidas con diseño)

- Colores: azul #1d254c, rojo #c50339, blanco #FFFFFF, negro #000000. Sin otros colores.
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
