# ConvoKit — Documento de Producto (PRD)

**Fábrica de entregables a partir de convocatorias de ayudas públicas**

| Versión | Fecha | Estado |
|---|---|---|
| 2.1 | Junio 2026 | Borrador para validación |

**Cambios respecto a v2.0:** las salidas 6 y 7 exportan también JSON estructurado (perfil de convocatoria y árbol de documentos), pensados para alimentar la App de Memorias (segunda app). Nota en CLAUDE.md sobre la integración entre ambas apps.

---

## 1. Contexto y problema que resuelve

Innóvate 4.0 produce, por cada convocatoria relevante que abre, un conjunto fijo de documentos y piezas de comunicación de manera manual: guía interna para el consultor, ficha comercial para el cliente de Ruta i40, post de LinkedIn, artículo SEO para el blog, landing page, set de prompts para redactar la memoria de solicitud y lista de documentación requerida al cliente.

Este trabajo se repite íntegramente con cada nueva convocatoria. La materia prima es siempre la misma: los documentos oficiales de la convocatoria (bases reguladoras, convocatoria del ejercicio, plantilla de memoria, anexos, resoluciones anteriores). El tiempo dedicado a transformar esos documentos en piezas accionables no se dedica a producción directa de memorias ni a los clientes.

ConvoKit automatiza ese proceso. El usuario sube los documentos oficiales de la convocatoria, selecciona los entregables que necesita y el sistema los genera en segundos, listos para usar o con mínima revisión. El histórico queda guardado: volver a una convocatoria procesada anteriormente no requiere volver a subir nada.

> Este PRD está redactado para ser entregado directamente a Claude Code como instrucciones de implementación. Cada sección es accionable y contiene el nivel de detalle necesario para ejecutarla sin ambigüedad.

---

## 2. Objetivo y alcance del MVP

### 2.1 Objetivo

Construir una aplicación web interna (uso exclusivo del equipo de Innóvate 4.0) que, a partir de documentos oficiales de convocatoria en múltiples formatos, genere los siete tipos de entregables definidos mediante llamadas a la API de Claude, con histórico persistente de convocatorias procesadas.

### 2.2 Alcance del MVP

El MVP debe cubrir:

- Subida de documentos en múltiples formatos (PDF, DOCX, XLSX, TXT) sin límite de número de archivos, con etiquetado por tipo.
- Extracción de texto mediante librerías locales (sin consumo de tokens).
- Histórico persistente de convocatorias procesadas: cada convocatoria tiene su propia entrada y sus entregables almacenados.
- Generación de los siete entregables mediante Claude API.
- Visualización, copia y descarga de cada resultado.
- Interfaz web desplegada con URL pública en Vercel.
- Backend desplegado en Railway.

Queda fuera del MVP:

- Integración con WordPress para publicación directa (fase 2).
- Autenticación de usuarios.
- Cruce con perfil de cliente para personalizar entregables por empresa.
- Integración con BDNS o eInforma.

---

## 3. Usuarios y contexto de uso

Usuario único: el equipo interno de Innóvate 4.0. No hay clientes finales en esta fase. La app es una herramienta de producción interna.

| Atributo | Descripción |
|---|---|
| Perfil | Consultor no técnico. Conoce las convocatorias pero no escribe código. |
| Frecuencia | 2 a 6 veces al mes (aproximadamente 10 convocatorias/mes en uso real). Puede procesar dos convocatorias simultáneamente el mismo día. |
| Dispositivo | Ordenador de escritorio o portátil, navegador Chrome o Edge. |
| Expectativa | Subir los documentos de la convocatoria, elegir qué piezas necesita y recibirlas sin fricción. Poder volver a una convocatoria anterior sin repetir el proceso. |

---

## 4. Menú de salidas (siete entregables)

Todas las salidas parten del mismo conjunto de documentos subidos. El usuario puede generar todas o solo las que necesite. Los resultados se almacenan en el histórico de la convocatoria y pueden regenerarse individualmente en cualquier momento.

| # | Salida | Formato | Descripción y destinatario |
|---|---|---|---|
| 1 | Guía interna del consultor | .md / texto | Baremo, criterios, perfil ideal del beneficiario, a quién comercializar y plan de trabajo. Destinatario: consultor de Innóvate 4.0. |
| 2 | Ficha comercial para el cliente | .md | Claves de la ayuda, recomendaciones de baremo y qué tener preparado. Formato .md listo para pegar en Claude design. Tono consultivo, sin urgencia. |
| 3 | Post de LinkedIn | texto | Publicación 800-1.100 caracteres, voz de Tono Mestre, datos concretos, sin marketing genérico. |
| 4 | Post WordPress con SEO | .md | Artículo 600-900 palabras con metadatos Yoast al inicio (título SEO, meta descripción, keyword). |
| 5 | Landing page | .md | Estructura completa de la landing en .md con instrucciones de diseño para Claude design. Especifica secciones, jerarquía, CTAs y referencias de marca. |
| 6 | Set de prompts para la memoria | .md + .json | Un prompt por sección de la memoria. Cada prompt pide al consultor la documentación necesaria antes de redactar. Nivel de detalle suficiente para que el consultor no necesite redactar nada de cero. Exporta también JSON estructurado (perfil de convocatoria). |
| 7 | Lista de documentación + correo al cliente | .md + .json + texto | Lista estructurada de documentos exigidos por la convocatoria, más correo tipo listo para enviar al cliente solicitándolos. Exporta también JSON estructurado (árbol de documentos). |

---

## 5. Formatos de archivo admitidos

El sistema admite cualquier número de archivos por convocatoria. No hay límite. Una convocatoria puede tener bases reguladoras, convocatoria del ejercicio, plantilla de memoria, anexos, resoluciones de ejercicios anteriores y otros documentos vinculados.

| Extensión | Tipo habitual | Librería de extracción | Nota |
|---|---|---|---|
| .pdf | Bases reguladoras, convocatoria, resoluciones | PyMuPDF (fitz) — extracción página a página | Si el PDF está escaneado (sin texto extraíble), mostrar aviso al usuario. |
| .docx | Plantilla de memoria, modelos de solicitud | python-docx — extracción de párrafos y tablas | Mantener el orden del documento original. |
| .xlsx | Cuenta justificativa, presupuesto, anexos numéricos | openpyxl — extracción de celdas por hoja | Incluir nombre de hoja como cabecera. Extraer solo celdas con contenido. |
| .txt | Textos simples, extractos | Lectura directa (open()) | UTF-8. Si falla, intentar latin-1. |
| Otros | Cualquier formato no listado | Rechazo con mensaje claro | Mensaje: "Formato no soportado. Sube el archivo en PDF, DOCX, XLSX o TXT." |

> Toda la extracción se realiza con librerías locales Python. No se envía el contenido de los archivos a ninguna API externa para su extracción: los tokens de Claude se usan únicamente para la generación de entregables, no para leer documentos.

Tipos de etiqueta disponibles para cada archivo subido:

- Bases reguladoras
- Convocatoria del ejercicio
- Plantilla de memoria / solicitud
- Resolución de ejercicio anterior
- Anexo o documento complementario

La etiqueta se usa en el separador de contexto (`=== BASES REGULADORAS ===`) para que el prompt de cada salida pueda identificar qué parte del contexto es más relevante.

---

## 6. Histórico de convocatorias

### 6.1 Requisito funcional

Cada convocatoria procesada queda guardada con un identificador, su nombre, la fecha de procesado, los documentos subidos y los entregables generados. El usuario puede:

- Ver la lista de convocatorias procesadas ordenada por fecha descendente.
- Abrir una convocatoria anterior y ver todos sus entregables ya generados.
- Regenerar individualmente cualquier entregable de una convocatoria anterior sin volver a subir los documentos.
- Añadir documentos nuevos a una convocatoria ya procesada y regenerar los entregables.
- Eliminar una convocatoria del histórico.

### 6.2 Implementación

- Base de datos: SQLite (fichero local en el servidor). Sin infraestructura adicional para el MVP.
- Esquema mínimo: tabla `convocatorias` (id, nombre, fecha_creacion, documentos_json, entregables_json).
- El campo `documentos_json` almacena el texto extraído de cada archivo, no el archivo binario.
- El campo `entregables_json` almacena el texto generado para cada salida, indexado por número de salida.
- Al Railway reiniciarse, el fichero SQLite persiste si está en un volumen montado. Claude Code debe configurar el path del fichero como variable de entorno DB_PATH y montar un volumen en Railway para persistencia real.

> Si en fase 2 se quiere migrar a Supabase (por coherencia con el stack de Radar i40), la migración es trivial: SQLite y Supabase tienen el mismo modelo relacional. Diseñar el esquema ya pensando en esa migración.

### 6.3 Flujo en la interfaz

- Panel izquierdo o superior: lista de convocatorias del histórico con nombre y fecha.
- Al hacer clic en una convocatoria del histórico, se carga su contexto y sus entregables ya generados.
- Botón "Nueva convocatoria" abre el flujo de subida de archivos limpio, sin perder las convocatorias anteriores.
- Dos convocatorias abiertas el mismo día coexisten en el histórico como entradas independientes.

---

## 7. Stack técnico

| Capa | Tecnología y justificación |
|---|---|
| Frontend | React (Vite) + Tailwind CSS. Navegación por estado de componente (AppContext), sin React Router. Desplegado en Vercel. URL pública asignada por Vercel. |
| Backend | Python 3.11 + FastAPI. Desplegado en Railway con volumen montado para persistir el fichero SQLite. |
| Extracción PDF | PyMuPDF (fitz). Local, sin tokens. Si el PDF no tiene texto, aviso al usuario. |
| Extracción DOCX | python-docx. Local, sin tokens. Extrae párrafos y tablas en orden. |
| Extracción XLSX | openpyxl. Local, sin tokens. Extrae celdas con contenido por hoja. |
| Base de datos | SQLite (fichero local persistido en Railway volume). Sin servidor adicional. |
| IA | Claude API — claude-sonnet-4-6. Un prompt del sistema distinto por tipo de salida. ANTHROPIC_API_KEY como variable de entorno. |
| Control de versiones | GitHub. Repositorio: convokit. URL de Vercel por defecto. |

---

## 8. Arquitectura del sistema

### 8.1 Flujo de una convocatoria nueva

- El usuario pulsa "Nueva convocatoria" e introduce el nombre de la convocatoria.
- Sube uno o varios archivos (PDF, DOCX, XLSX, TXT), asignando a cada uno su tipo de etiqueta.
- El backend extrae el texto de cada archivo con la librería local correspondiente y lo combina en un contexto compuesto.
- El contexto y los metadatos se guardan en SQLite como nueva entrada del histórico.
- El usuario selecciona qué entregables quiere generar (checkboxes, uno o varios a la vez).
- Para cada entregable seleccionado, el backend llama a Claude API con el prompt específico y el contexto.
- El resultado se muestra en pantalla, se puede copiar y descargar, y se guarda en el histórico.

### 8.2 Flujo de una convocatoria del histórico

- El usuario selecciona la convocatoria en el panel de histórico.
- Se carga el contexto almacenado y los entregables ya generados.
- El usuario puede ver cualquier entregable anterior, regenerar uno concreto o añadir documentos nuevos.

### 8.3 Endpoints del backend

| Endpoint | Método | Descripción |
|---|---|---|
| /convocatorias | POST | Crea una nueva convocatoria en el histórico. Recibe nombre. Devuelve convocatoria_id. |
| /convocatorias/{id}/upload | POST | Sube uno o varios archivos a una convocatoria. Extrae texto, combina contexto, actualiza SQLite. Devuelve el contexto extraído. |
| /convocatorias/{id}/generate | POST | Genera uno o varios entregables (output_types: lista de 1-7). Guarda en SQLite. Devuelve textos generados. |
| /convocatorias | GET | Lista todas las convocatorias del histórico (id, nombre, fecha, entregables disponibles). |
| /convocatorias/{id} | GET | Devuelve el detalle de una convocatoria: contexto, metadatos y entregables generados. |
| /convocatorias/{id} | DELETE | Elimina una convocatoria y sus entregables del histórico. |
| /health | GET | Health check. |

---

## 9. Requisitos de la interfaz (Frontend)

### 9.1 Layout general

- Panel lateral izquierdo: lista del histórico de convocatorias con nombre y fecha. Botón "Nueva convocatoria" en la parte superior.
- Área principal derecha: estado actual (subida de archivos, generación de entregables o detalle de una convocatoria del histórico).
- La interfaz nunca sustituye una convocatoria activa por otra: cada una es una entrada independiente en el histórico.

### 9.2 Flujo de nueva convocatoria

- Input de texto para el nombre de la convocatoria (obligatorio antes de subir archivos).
- Zona de carga por drag and drop o clic. Acepta PDF, DOCX, XLSX, TXT. Sin límite de archivos.
- Por cada archivo subido: nombre del archivo, selector de tipo (etiqueta), botón para eliminar.
- Botón "Procesar documentos" que extrae el texto y habilita el selector de entregables.
- Selector de entregables: checkboxes para cada una de las siete salidas.
- Botón "Generar seleccionados". Deshabilitado si no hay entregables marcados.
- Indicador de progreso individual por entregable mientras se genera.

### 9.3 Visualización de entregables

- Cada entregable generado aparece en un panel desplegable con su nombre.
- Botón "Copiar" en cada panel.
- Botón "Descargar" en cada panel: .md para todas las salidas textuales, .txt para el post de LinkedIn.
- Botón "Regenerar" en cada panel: regenera solo ese entregable sin tocar los demás.
- Las salidas 6 y 7 tienen dos botones de descarga: ".md" (legible) y ".json" (estructurado).

### 9.4 Estilo visual (marca Innóvate 4.0)

- Colores: azul #1d254c (principal, fondos de cabecera, texto de énfasis), rojo #c50339 (acentos, CTAs, separadores), blanco #FFFFFF (fondos), negro #000000 (texto de cuerpo).
- Tipografía: Roboto Slab (Google Fonts) para títulos H1 y H2. Inter para cuerpo y UI. Ambas disponibles via CDN.
- Border-radius: 0px en todos los elementos interactivos (botones, inputs, paneles, cards).
- Sin colores adicionales fuera de la paleta de marca.
- Sin animaciones decorativas. Interfaz funcional y limpia.
- Responsive básico: funcional desde 1280px. No es prioritario para móvil en el MVP.

---

## 10. Requisitos del backend (FastAPI)

### 10.1 Extracción de texto por formato

- PDF: PyMuPDF (fitz), página a página. Si no hay texto extraíble (PDF escaneado), devolver error con mensaje: "Este PDF parece estar escaneado. Por favor, aporta la versión digital."
- DOCX: python-docx. Extraer párrafos en orden. Las tablas se extraen como texto tabulado (columnas separadas por " | ", filas por salto de línea).
- XLSX: openpyxl. Por cada hoja: cabecera `=== HOJA: [nombre] ===` seguida de las celdas con contenido. Ignorar celdas vacías.
- TXT: lectura directa UTF-8. Fallback a latin-1 si falla.
- Formato no soportado: error con mensaje "Formato no soportado. Sube el archivo en PDF, DOCX, XLSX o TXT."

### 10.2 Construcción del contexto compuesto

- Cada archivo extraído se prefija con su etiqueta: `=== BASES REGULADORAS ===`, `=== CONVOCATORIA ===`, etc.
- Los archivos se concatenan en el orden en que fueron subidos.
- Si el contexto total supera 150.000 palabras, truncar priorizando en este orden: bases reguladoras, convocatoria del ejercicio, plantilla de memoria, resoluciones anteriores, anexos.
- El contexto compuesto se almacena en SQLite al procesar los archivos.

### 10.3 Llamada a la API de Claude

- Modelo: claude-sonnet-4-6.
- max_tokens: 4096 para salidas 1-5 y 7. max_tokens: 8192 para salida 6 (set de prompts).
- Cada tipo de salida tiene su propio system prompt en /backend/prompts.py.
- En caso de error de Claude API: devolver error claro al frontend, en español, sin exponer la traza interna.
- Timeout de la llamada: 120 segundos. Si supera el límite, error claro al usuario.

---

## 11. Instrucciones por tipo de salida (prompts)

> Los system prompts completos se escriben en /backend/prompts.py. Esta sección define qué debe contener cada uno, no el texto literal. Claude Code debe escribir los prompts aplicando estas instrucciones.

### Salida 1 — Guía interna del consultor

- Extraer y estructurar: nombre completo de la convocatoria, organismo, normativa aplicable, CNAE y tamaño de empresa elegibles, tipo de proyecto financiable, porcentaje y horquilla de ayuda, todos los criterios de baremo con su peso exacto (si figura en las bases), documentación exigida.
- Sección "Perfil ideal del beneficiario": descripción de la empresa con más probabilidad de concesión, basada en el baremo.
- Sección "A quién comercializar": qué clientes de Ruta i40 encajan y por qué. Concreto, no genérico.
- Sección "Plan de trabajo": hitos desde la firma del encargo hasta la presentación, con indicación de qué documentación debe aportar el cliente en cada hito.
- Sección "Alertas de cumplimiento": requisitos habilitantes que el cliente debe tener antes de presentar (plan de igualdad, EVSR, estar al corriente AEAT/SS, etc.).
- Tono: técnico, preciso, uso interno. Sin adornos.
- Formato: markdown con secciones H2 y H3.

### Salida 2 — Ficha comercial para el cliente (.md para Claude design)

- Explicar la convocatoria en lenguaje accesible para un gerente de pyme no especializado.
- Destacar: a quién va dirigida, qué financia, cuánto puede llegar a subvencionar y en qué plazos.
- Sección "Cómo maximizar tu puntuación": recomendaciones concretas basadas en el baremo.
- Sección "Qué necesitas tener preparado": los documentos y requisitos previos más comunes.
- Sin fechas de cierre de plazo ni urgencia. Tono consultivo.
- Sin anglicismos ni lenguaje de marketing genérico.
- Markdown limpio con jerarquía clara (H1, H2, bullets, destacados). No generar frontmatter de marca ni CSS: el diseño visual lo aplica Claude design después, que ya tiene el design system de Innóvate 4.0.

### Salida 3 — Post de LinkedIn

- Entre 800 y 1.100 caracteres totales (contar el post completo incluyendo hashtags).
- Primera persona, voz de Tono Mestre (CEO Innóvate 4.0), tono de autoridad consultiva.
- Primera línea impactante. No empezar por "Hoy", "Acaba de", "Ha salido", "Me complace".
- Cuerpo: qué es la convocatoria, a quién interesa, dato concreto relevante (importe, porcentaje, CNAE).
- Cierre conversacional con llamada a la acción suave. Sin urgencia artificial.
- Sin em dashes. Sin bullet points en el texto del post.
- Máximo 3 hashtags al final, específicos y relevantes.
- Tono: datos verificables, sin adjetivos vacíos, frases cortas.

### Salida 4 — Post WordPress con SEO (.md)

- Al inicio del fichero, bloque de metadatos Yoast separado del cuerpo del artículo: título SEO (≤60 caracteres), meta descripción (≤155 caracteres), keyword principal.
- Estructura: H1, introducción 80-100 palabras, varios H2 con contenido, conclusión con CTA.
- Longitud del artículo: entre 600 y 900 palabras.
- Términos de búsqueda relacionados distribuidos de forma natural.
- Tono: mismo que LinkedIn pero más extenso y estructurado. Técnico, sin relleno.

### Salida 5 — Landing page (.md para Claude design)

- Estructura explícita en markdown: sección por sección, con indicación del tipo de elemento (hero, cards, CTA, formulario).
- Secciones mínimas: cabecera con logo, hero (nombre de la convocatoria + descripción breve + CTA), a quién va dirigida, qué financia, cómo trabajamos (referencia a Ruta i40), CTA final.
- Para cada sección, indicar: texto de contenido, jerarquía tipográfica, tipo de CTA si aplica.
- Markdown limpio y detallado. No generar frontmatter de marca ni CSS: el diseño visual lo aplica Claude design después, que ya tiene el design system de Innóvate 4.0.

### Salida 6 — Set de prompts para la memoria (alta exigencia)

Esta salida es la más crítica operativamente. El objetivo es que el consultor pueda redactar la memoria técnica de un cliente de Ruta i40 sin necesidad de escribir nada de cero, solo aportando la información específica de la empresa que cada prompt solicita.

- Generar un prompt para cada sección o apartado que exigen las bases reguladoras. Si las bases tienen 8 apartados en la memoria, hay 8 prompts.
- Cada prompt debe seguir esta estructura fija:
  - **SECCIÓN:** nombre exacto del apartado según las bases.
  - **QUÉ BUSCA EL EVALUADOR:** criterios de baremo que se puntúan en este apartado, con el peso si figura.
  - **QUÉ DEBES APORTAR ANTES DE GENERAR:** lista de documentos o datos que el consultor debe tener a mano para que el prompt funcione correctamente. Ejemplos: "Adjunta la última auditoría energética o certificado ISO 50001", "Aporta el presupuesto de la inversión en formato PDF o Excel", "Incluye el organigrama de la empresa o una descripción del equipo directivo". Si para escribir bien el apartado es necesario adjuntar un documento, pedirlo explícitamente.
  - **INSTRUCCIÓN A CLAUDE:** texto del prompt que el consultor copiará en Claude para generar el borrador de ese apartado. Debe pedir a Claude que use los datos aportados, que maximice la puntuación en los criterios del baremo y que indique qué información adicional necesitaría si algún campo queda sin cubrir.
- Los prompts deben estar en bloques de código markdown para fácil copia.
- El nivel de detalle debe ser suficiente para que el consultor no necesite redactar nada de cero: solo aportar los datos que el prompt solicita.
- Si las bases no especifican el baremo de un apartado, indicarlo explícitamente ("baremo no especificado en bases; redactar con máximo detalle y evidencias documentales").

### Salida 7 — Lista de documentación + correo tipo al cliente

- Primera parte: lista estructurada de todos los documentos que el cliente debe aportar para la solicitud, extraída directamente de las bases reguladoras. Organizada por categoría (documentación de la empresa, del proyecto, económico-financiera, técnica, etc.).
- Para cada documento: nombre del documento, si es obligatorio u opcional, si hay modelo oficial en las bases (indicar "sí, usar el Anexo X" o "no, formato libre"), y si exige alguna vigencia o fecha de emisión.
- Segunda parte: correo tipo listo para enviar al cliente, con tono cercano y directo (marca Innóvate 4.0). El correo debe:
  - Presentar la convocatoria en una frase.
  - Explicar por qué necesitan esa documentación ahora y no cuando se abra la convocatoria.
  - Incluir la lista de documentos de forma clara y accionable (con bullets).
  - Indicar el plazo orientativo para aportar la documentación (dejar un campo [FECHA] para que el consultor rellene).
  - Cerrar con los datos de contacto del consultor (campos [NOMBRE CONSULTOR] y [EMAIL CONSULTOR]).
- El correo no debe sonar a lista burocrática: debe transmitir que se trabaja con antelación para llegar en mejor posición.

---

## 12. Exportación estructurada (JSON) e integración con la App de Memorias

Las salidas 6 y 7 generan, además del markdown legible, una versión en JSON estructurado. El JSON contiene exactamente la misma información, etiquetada por campos para que una segunda aplicación pueda leerla sin intervención humana.

> Contexto: Innóvate 4.0 va a construir una segunda aplicación (App de Memorias) que redacta memorias técnicas y rellena cuentas justificativas a partir de los datos reales de cada empresa. Esa app necesita, por cada convocatoria, un perfil de convocatoria (secciones, baremo, inputs) y un árbol de documentos. El JSON de las salidas 6 y 7 de ConvoKit es precisamente ese input. La conexión en el MVP es manual: se descarga el JSON de ConvoKit y se carga en la App de Memorias.

### 12.1 JSON de la salida 6 — perfil de convocatoria

Estructura: un array de secciones. Cada sección con los campos siguientes:

- `codigo`: identificador de la sección según las bases (ej. "II.C").
- `nombre`: nombre del apartado.
- `puntos_max`: puntuación máxima de la sección (número, o "excluyente" si es puerta de entrada).
- `inputs_minimos`: array de strings con lo imprescindible para redactar algo con sentido.
- `inputs_puntuacion_completa`: array de strings con lo necesario para maximizar la puntuación.
- `documentos_requeridos`: array de strings con los documentos que el consultor debe aportar.
- `prompt`: el texto del prompt de redacción de esa sección (el mismo que va en el .md).

Ejemplo de un elemento del array:

```json
{
  "codigo": "II.C",
  "nombre": "Descripción técnica",
  "puntos_max": 40,
  "inputs_minimos": ["ficha técnica", "proforma por activo"],
  "inputs_puntuacion_completa": ["diagrama de flujo", "plano de distribución"],
  "documentos_requeridos": ["ficha técnica activo", "proforma"],
  "prompt": "..."
}
```

### 12.2 JSON de la salida 7 — árbol de documentos

Estructura: un array de documentos. Cada documento con los campos siguientes:

- `documento`: nombre del documento exigido.
- `obligatorio`: booleano (true si es obligatorio, false si es opcional o suma puntos).
- `modelo_oficial`: string ("Anexo X" si existe modelo en las bases, "formato libre" si no).
- `ambito`: string ("empresa", "expediente" o "activo"), para indicar a qué nivel pertenece el documento.
- `vigencia`: string con el requisito de fecha o vigencia si lo hay, o null.

> El campo `ambito` replica la lógica del árbol de documentos de la App de Memorias (empresa / expediente / activo). Generarlo ya en ConvoKit ahorra clasificarlo después a mano.

### 12.3 Implicación para la interfaz

- Las salidas 6 y 7 tienen dos botones de descarga: "Descargar .md" (legible) y "Descargar .json" (estructurado).
- El resto de salidas (1-5) mantienen un solo botón de descarga en su formato correspondiente.
- El JSON también se almacena en el histórico de la convocatoria, junto al markdown.

### 12.4 Nota obligatoria en CLAUDE.md

Claude Code debe incluir en el CLAUDE.md del repositorio una nota explícita con este contenido:

- ConvoKit es la primera de dos aplicaciones. La segunda (App de Memorias) redacta memorias y cuentas justificativas a partir de los datos de cada empresa.
- Las salidas 6 y 7 exportan JSON estructurado precisamente para alimentar la App de Memorias: la salida 6 produce el perfil de convocatoria (secciones, baremo, inputs); la salida 7 produce el árbol de documentos.
- El esquema de campos de ambos JSON (definido en la sección 12 del PRD) no debe modificarse sin coordinarlo con el modelo de datos de la App de Memorias, porque esa app lo consume directamente.
- La integración en el MVP es manual (descarga e importación de fichero). No se construye conexión automática entre ambas apps en esta fase.

---

## 13. Instrucciones específicas para Claude Code

### 13.1 Lectura previa obligatoria

Claude Code debe leer CLAUDE.md en la raíz del repositorio antes de cualquier cambio. Ese fichero es la fuente de verdad del proyecto: arquitectura, variables de entorno, orden de implementación y decisiones tomadas.

### 13.2 Estructura del repositorio

- Monorepo con dos carpetas: /frontend (React + Vite) y /backend (Python + FastAPI).
- CLAUDE.md en la raíz con el resumen del proyecto, arquitectura, variables de entorno y orden de implementación.
- /backend/prompts.py con todos los system prompts, uno por tipo de salida, en un diccionario indexado por número.
- .env.example en /frontend y /backend con todas las variables de entorno necesarias sin valores.
- /backend/database.py con toda la lógica de SQLite (creación de tablas, CRUD de convocatorias y entregables).
- /backend/exporters.py con la lógica de exportación de las salidas 6 y 7 a JSON estructurado, según el esquema de la sección 12.

### 13.3 Reglas de código

- Todo el código en inglés (variables, funciones, clases, comentarios técnicos).
- Textos visibles en la interfaz, en español.
- Comentarios explicativos en prompts.py y en database.py.
- Sin dependencias innecesarias.
- Errores devueltos al frontend: en español, sin trazas internas.

### 13.4 Control de versiones

- Hacer commit tras cada paso completado y funcional. No acumular cambios sin commit.
- Mensajes de commit en inglés (feat:, fix:, refactor:, docs:).
- Nunca subir .env ni claves al repositorio.

### 13.5 Orden de implementación

- Paso 1: Scaffold — estructura de carpetas, CLAUDE.md, .env.example, README.md.
- Paso 2: Backend — database.py con esquema SQLite y CRUD básico.
- Paso 3: Backend — endpoint POST /convocatorias/{id}/upload con extracción de PDF (PyMuPDF). Test con las bases de INPYME 2026.
- Paso 4: Backend — añadir extracción DOCX (python-docx) y XLSX (openpyxl) al mismo endpoint.
- Paso 5: Backend — endpoint POST /convocatorias/{id}/generate con llamada a Claude API para Salida 1. Test extremo a extremo con INPYME 2026.
- Paso 6: Frontend — layout base (panel lateral histórico + área principal). Flujo de nueva convocatoria con subida de archivos.
- Paso 7: Frontend — visualización de entregables, copiar y descargar.
- Paso 8: Backend — implementar las salidas 2 a 7, una a una, validando cada prompt con INPYME 2026.
- Paso 8 bis: Backend — exporters.py: exportación de las salidas 6 y 7 a JSON estructurado según el esquema de la sección 12.
- Paso 9: Frontend — integrar visualización del histórico y carga de convocatorias anteriores.
- Paso 10: Despliegue — backend en Railway (con volumen para SQLite), frontend en Vercel.
- Paso 11: Test completo con INPYME 2026. Ajuste de prompts si el output no es satisfactorio.

---

## 14. Criterios de aceptación del MVP

| # | Criterio | Verificación |
|---|---|---|
| 1 | Se pueden subir PDF, DOCX y XLSX de INPYME 2026 y el sistema extrae el texto correctamente. | Manual: verificar que el contexto extraído es coherente con el contenido de los archivos. |
| 2 | Se pueden subir más de tres archivos simultáneamente. | Manual: subir 5 archivos distintos y verificar que todos se procesan. |
| 3 | Las siete salidas se generan sin error para INPYME 2026. | Manual: generar los siete entregables y verificar coherencia con las bases. |
| 4 | Cada salida se puede copiar y descargar en su formato correcto (.md o .txt). | Manual: copiar y descargar cada resultado. |
| 5 | Dos convocatorias procesadas el mismo día aparecen como entradas independientes en el histórico. | Manual: crear dos convocatorias el mismo día y verificar que ambas están en el histórico con sus entregables. |
| 6 | Al seleccionar una convocatoria del histórico se recuperan sus entregables sin volver a subir archivos. | Manual: cerrar la sesión del navegador, reabrir la app y seleccionar una convocatoria anterior. |
| 7 | Un PDF escaneado devuelve el mensaje de error correcto en español. | Manual: subir un PDF escaneado y verificar el mensaje. |
| 8 | El set de prompts (salida 6) cubre todos los apartados de la memoria de INPYME 2026 y cada prompt especifica los documentos que el consultor debe aportar. | Manual: contrastar los prompts con el índice de la plantilla de memoria de INPYME 2026. |
| 9 | El correo tipo (salida 7) es enviable directamente con mínima edición (solo rellenar campos entre corchetes). | Manual: leer el correo y evaluar si es accionable sin reescritura. |
| 10 | Las salidas 6 y 7 se descargan también en JSON con el esquema de campos de la sección 12. | Manual: descargar ambos JSON de INPYME 2026 y verificar que tienen los campos definidos y son JSON válido. |
| 11 | La app está desplegada con URL pública de Vercel y funciona desde un navegador externo. | Manual: acceder desde una red distinta a la de desarrollo. |
| 12 | El tiempo de generación de una salida individual es inferior a 90 segundos. | Manual: medir con cronómetro. |

---

## 15. Decisiones tomadas y pendientes

### 15.1 Decisiones tomadas

- Backend: Railway.
- Dominio: URL pública asignada por Vercel (sin subdominio propio en el MVP).
- Base de datos: SQLite con volumen en Railway.
- Repositorio: GitHub, convokit (github.com/TonoMestre/convokit).
- Archivo de prueba: INPYME 2026 (bases reguladoras + convocatoria + plantilla de memoria).
- Salidas 2 y 5 en formato .md para Claude design, no HTML autónomo.
- Extracción de texto: librerías locales, sin consumo de tokens.
- Salidas 6 y 7 exportan también JSON estructurado para alimentar la App de Memorias (segunda app). Integración manual en el MVP: descarga e importación de fichero.

### 15.2 Pendientes antes de arrancar

| Pendiente | Detalle |
|---|---|
| Repositorio GitHub | Creado: github.com/TonoMestre/convokit. |
| Archivos INPYME 2026 | Reunir los PDFs/DOCXs de INPYME 2026 (bases, convocatoria, plantilla de memoria) para usarlos en los tests de cada paso. |
| API key de Anthropic | Confirmar que la ANTHROPIC_API_KEY de Innóvate 4.0 tiene crédito suficiente para el desarrollo y las pruebas. |
| Cuenta Railway | Crear o confirmar la cuenta en Railway y que permite montar volúmenes para persistir SQLite. |

---

*Innóvate 4.0 · ConvoKit PRD v2.1 · Junio 2026*
