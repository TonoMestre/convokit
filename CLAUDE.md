# CLAUDE.md — ConvoKit

## Qué es este proyecto

ConvoKit es una aplicación web interna de Innóvate 4.0 (consultora de ayudas públicas).
A partir de los documentos oficiales de una convocatoria de ayudas (bases reguladoras,
convocatoria del ejercicio, plantilla de memoria, anexos), genera siete entregables
mediante la API de Claude: guía del consultor, ficha comercial, post de LinkedIn,
artículo SEO, landing page, set de prompts para la memoria, y lista de documentación +
correo al cliente.

Uso exclusivamente interno. Sin clientes finales. Sin autenticación en el MVP.

## Lee esto antes de cada cambio

Este fichero es la fuente de verdad. Léelo antes de tocar nada. El PRD completo
(ConvoKit_PRD_v2.1) tiene el detalle de cada requisito; este fichero es el resumen
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
- La exportación a JSON de las salidas 6 y 7 va en /backend/exporters.py.
- Sin dependencias innecesarias.
- Los errores devueltos al frontend van en español, sin trazas internas. El frontend
  los muestra en un banner visible, no en consola.

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

## Las dos apps (importante)

ConvoKit es la primera de dos aplicaciones. La segunda (App de Memorias) redacta memorias
técnicas y cuentas justificativas a partir de los datos reales de cada empresa.

Las salidas 6 y 7 exportan JSON estructurado precisamente para alimentar la App de Memorias:
- Salida 6 produce el perfil de convocatoria (secciones, baremo, inputs).
- Salida 7 produce el árbol de documentos.

El esquema de campos de ambos JSON (sección 12 del PRD) no debe modificarse sin coordinarlo
con el modelo de datos de la App de Memorias, porque esa app lo consume directamente.

La integración en el MVP es manual: se descarga el JSON de ConvoKit y se carga en la App de
Memorias. No se construye conexión automática entre ambas apps en esta fase.

## Orden de implementación

Seguir este orden. Validar cada paso antes de seguir al siguiente.

1. Scaffold: estructura de carpetas, CLAUDE.md, .env.example, README.md.
2. Backend: database.py con esquema SQLite y CRUD básico.
3. Backend: endpoint de subida con extracción de PDF (PyMuPDF). Test con INPYME 2026.
4. Backend: añadir extracción DOCX y XLSX al endpoint de subida.
5. Backend: endpoint de generación con llamada a Claude API para la Salida 1. Test extremo a extremo.
6. Frontend: layout base (panel histórico + área principal) y flujo de nueva convocatoria.
7. Frontend: visualización de entregables, copiar y descargar.
8. Backend: implementar salidas 2 a 7, una a una, validando cada prompt con INPYME 2026.
8 bis. Backend: exporters.py, exportación de salidas 6 y 7 a JSON.
9. Frontend: histórico y carga de convocatorias anteriores.
10. Despliegue: backend en Railway (con volumen), frontend en Vercel.
11. Test completo con INPYME 2026 y ajuste de prompts.

## Marca Innóvate 4.0 (para la interfaz y las salidas con diseño)

- Colores: azul #1d254c, rojo #c50339, blanco #FFFFFF, negro #000000. Sin otros colores.
- Tipografía: Roboto Slab (títulos), Inter (cuerpo y UI). Ambas desde Google Fonts.
- Border-radius: 0px en todos los elementos.
- Las salidas 2 (ficha comercial) y 5 (landing) salen en .md limpio con jerarquía clara
  (H1, H2, bullets, destacados). El diseño visual lo aplica Claude design después; no generar
  frontmatter de marca ni CSS en esas salidas.
