# Contrato de salida ConvoKit → MemorAI (Salida 4)

Versión propuesta: `2.1` · Julio 2026

> Cambios 2.0 → 2.1, tras revisar el primer JSON real (INPYME 2026):
> solo apartados hoja (sin bloque padre duplicado), nuevo bloque
> `parametros_convocatoria` con valor incluido, bloque `tres_ofertas`
> estructurado, `datos_aplicativo` restringido a lo que rellena el
> consultor, ids solo ASCII y prompts sin instrucciones conversacionales.

Este documento define el formato que ConvoKit debe producir para que MemorAI
pueda importar una convocatoria sin post-procesado con IA ni revisión manual.
Está pensado para copiarse en el CLAUDE.md (o documentación equivalente) del
proyecto ConvoKit.

## Motivación

El formato actual (array plano de apartados) obliga a MemorAI a:

- Teclear a mano nombre, año y organismo al subir el JSON (no vienen en el archivo).
- Indexar apartados por posición porque los códigos llegan repetidos; el
  emparejamiento sección↔apartado por código puede asignar el prompt equivocado.
- Filtrar placeholders ("no aplica", "ya incluido", "ver otro apartado"...) en
  `documentos_requeridos`.
- Hacer una llamada a Claude para deduplicar semánticamente los campos de
  empresa que llegan con nombres distintos en cada apartado, más una pantalla
  de confirmación del admin.
- Hacer otra llamada a Claude para clasificar cada input (texto libre, dato de
  empresa, inversión, rentabilidad, documento, duplicado).
- Generar apartados de memoria (con `prompt` de redacción) a partir de
  exigencias que en realidad vienen del formulario telemático o de las bases,
  no del documento de memoria: cosas como la URL de la web, el número de
  empleados a contratar o si son indefinidos son un dato de valor único, no
  contenido narrativo. Confirmado con un caso real (convocatoria EMPYME): la
  memoria acreditativa oficial solo pide 2-3 puntos redactables, y el resto de
  exigencias de las bases hoy llegan a MemorAI como apartados con `prompt`,
  generando borradores de párrafo para lo que debería ser un campo de
  formulario.

Todo eso es información que ConvoKit ya tiene al generar el apartado.

## Ámbito: cualquier convocatoria

Este contrato es **agnóstico del tipo de ayuda**. Los ejemplos que aparecen
(inversión industrial) son ilustrativos, no plantilla. Los tipos de input y los
flags reflejan la estructura de MemorAI (perfil de empresa reutilizable, cuenta
justificativa, cálculo de rentabilidad), no la de ninguna convocatoria concreta.
Para convocatorias que no encajen en algún concepto, el contrato prevé escape
explícito:

- Sin baremo por puntos → `puntos_max: null`.
- Sin distinción mínimo/completo → todos los inputs con `nivel: "minimo"`.
- Sin inversión (empleo, internacionalización...) → `usa_tabla_inversiones: false`.
- Sin análisis de rentabilidad → `requiere_calculo_rentabilidad: false`.
- Tipo de ayuda no contemplado → `tipo_ayuda: "otro"` (nunca forzar la categoría
  más parecida).

ConvoKit nunca debe omitir un apartado ni inventar estructura para cumplir el
esquema: si algo no aplica, se usa el valor de escape correspondiente.

## Estructura raíz

La raíz es un **objeto**, no un array:

```json
{
  "version_esquema": "2.0",
  "convocatoria": {
    "nombre": "Ayudas a la inversión industrial CV 2026",
    "anio": 2026,
    "organismo": "IVACE",
    "tipo_ayuda": "inversion_productiva",
    "fecha_generacion": "2026-07-06"
  },
  "campos_empresa": [ ... ],
  "apartados": [ ... ],
  "tres_ofertas": { ... },
  "parametros_convocatoria": [ ... ],
  "datos_aplicativo": [ ... ]
}
```

- `version_esquema`: obligatorio. Permite a MemorAI aceptar formatos antiguos
  y validar los nuevos.
- `tipo_ayuda`: uno de `inversion_productiva | digitalizacion | idi |
  internacionalizacion | medioambiente_energia | empleo | otro`. MemorAI lo usa
  para ajustar el registro de redacción.

## Catálogo de campos de empresa (`campos_empresa`)

Lista única, a nivel de convocatoria, de los datos de empresa que se pedirán al
cliente. Los apartados **referencian estos campos por `id`**, nunca redefinen
el nombre.

```json
{
  "id": "datos-economicos",
  "nombre": "Datos económicos de la empresa (últimos 3 ejercicios)",
  "descripcion": "Facturación, EBITDA y resultado. Se usará en A.1 y A.3.",
  "formato": "texto"
}
```

- `id`: slug kebab-case estable dentro de la convocatoria. **Regla de oro: si
  dos apartados necesitan el mismo dato, usan el mismo `id`.** Prohibido crear
  "datos-economicos" y "cifras-economicas" como campos separados.
- `formato`: `texto | tabla_historica | numero`. Para `tabla_historica`,
  añadir `variables` (lista) y `num_anios` sugeridos.

## Apartados (`apartados[]`)

```json
{
  "codigo": "A.3",
  "nombre": "Viabilidad económica del proyecto",
  "puntos_max": 15,
  "prompt": "Redacta el apartado de viabilidad económica...",
  "inputs": [
    {
      "id": "descripcion-mejora-productiva",
      "label": "Descripción de la mejora productiva esperada",
      "tipo": "texto_libre",
      "nivel": "minimo",
      "ayuda": "2-4 frases sobre qué cuello de botella resuelve la inversión"
    },
    {
      "id": "rentabilidad",
      "label": "Cálculo de rentabilidad (VAN, TIR, payback)",
      "tipo": "rentabilidad",
      "nivel": "completo"
    },
    {
      "id": "datos-economicos",
      "label": "Datos económicos de la empresa",
      "tipo": "dato_empresa",
      "ref_campo_empresa": "datos-economicos",
      "nivel": "minimo"
    }
  ],
  "documentos_requeridos": [
    { "nombre": "Plano de planta con la nueva línea", "fuente": "cliente" }
  ],
  "requiere_calculo_rentabilidad": true,
  "usa_tabla_inversiones": true
}
```

### Reglas obligatorias

1. **`codigo` único** en todo el array. Es el identificador de emparejamiento
   entre sección y apartado en MemorAI. Si la convocatoria oficial repite
   numeración, desambiguar con sufijo (`B.2-tecnica`, `B.2-economica`).
1bis. **Solo apartados hoja, nunca bloque padre + hijos a la vez.** Si la
   memoria oficial estructura un bloque en subapartados (I → I.A, I.B, I.C),
   ConvoKit emite **solo los subapartados** (I.A, I.B, I.C), cada uno con su
   prompt. Prohibido emitir además un apartado `I` con un prompt que redacte
   el bloque completo: MemorAI crearía secciones duplicadas y el consultor
   redactaría todo dos veces. El bloque padre solo se emite cuando no tiene
   subapartados propios. Si MemorAI necesita el título del bloque para el
   Word, lo deduce del prefijo del código.
2. **`prompt` no vacío** y autocontenido: no debe referirse a "el apartado
   anterior" ni depender de contexto que MemorAI no envía.
3. **Cada input va tipado** con `tipo`:
   - `texto_libre`: dato específico del proyecto que redacta el consultor.
   - `dato_empresa`: dato general de la empresa → obligatorio
     `ref_campo_empresa` apuntando a un `id` de `campos_empresa`.
   - `inversion`: lo cubre la cuenta justificativa del expediente (tabla única
     de partidas). No pedir tablas de inversión como texto libre.
   - `rentabilidad`: lo cubre el cálculo estructurado (VAN/TIR/payback).
   - `documento`: el consultor adjunta un archivo.
4. **`nivel`**: `minimo` (imprescindible para generar borrador) o `completo`
   (necesario para optar a la puntuación máxima). Todo input `minimo` está
   implícitamente incluido en el modo completo. Sustituye a las listas
   paralelas `inputs_minimos` / `inputs_puntuacion_completa`.
5. **Sin duplicados dentro del apartado**: dos inputs que piden lo mismo con
   otras palabras se fusionan en origen. Si el formulario oficial los separa,
   se emite uno solo y se explica en `ayuda`.
6. **Sin placeholders**: si un documento o input no aplica, **se omite la
   entrada**. Prohibidos valores tipo "no aplica", "ya incluido", "ver otro
   apartado", "ya las tienes", "n/a".
7. **`documentos_requeridos`** solo contiene documentos reales, con
   `fuente` ∈ `cliente | perfil_estrategico | generado`. Nada de datos de
   empresa camuflados aquí (eso va como input `dato_empresa`).
8. **Flags por apartado**: `requiere_calculo_rentabilidad` y
   `usa_tabla_inversiones` (boolean) los marca ConvoKit al analizar las bases;
   hoy los marca el admin a mano.
9. **Placeholders de imagen** dentro del `prompt` siempre con la forma exacta
   `[IMAGEN: nombre-descriptivo]`.
10. **Formato del archivo**: UTF-8, JSON puro sin envolver en ```` ```json ````,
    `puntos_max` numérico o `null` (nunca "15 puntos" como string).
11. **Ids solo ASCII**: kebab-case sin acentos ni eñes
    (`experiencia-minima-anios`, no `experiencia-minima-años`).
12. **Prompts para generación en un solo disparo**: MemorAI envía el prompt a
    Claude una única vez, sin conversación. Prohibidas instrucciones del tipo
    "solicítalo antes de continuar" o "pide al consultor que aporte X". La
    única vía para dato ausente es el marcador `[DATO PENDIENTE: descripción]`
    en el lugar del texto donde correspondería.

## Distinción memoria vs. formulario/aplicativo (crítico)

Una convocatoria mezcla siempre dos tipos de exigencia distintos, y ConvoKit es
el único que puede diferenciarlos porque es quien procesa las bases completas
(memoria, formularios, anexos):

- **Contenido de memoria**: lo que pide el documento narrativo de la memoria
  técnica/acreditativa (normalmente un anexo Word separado, identificable
  porque describe apartados a desarrollar en prosa: "describa...", "justifique...",
  "indique la misión, visión y valores..."). Esto y solo esto va en `apartados[]`.
- **Datos de aplicativo**: cualquier exigencia de las bases o del formulario
  telemático que se resuelve con un valor puntual, no con redacción: una URL,
  un número, un sí/no, una fecha, una selección de una lista cerrada. Ejemplos
  reales: "URL de la web", "número de empleados a contratar", "los contratos
  serán indefinidos (sí/no)", NIF, razón social.

**Regla de decisión para ConvoKit**: si la respuesta esperada es una frase o
párrafo → apartado de memoria. Si la respuesta esperada es un dato que un
consultor tecleraría en una casilla de un formulario → `datos_aplicativo`,
nunca un apartado. Ante la duda, un input que empieza por "indicar", "número
de", "fecha de", "sí/no" o pide un dato ya identificativo de la empresa casi
siempre es un dato de aplicativo, no redacción.

## Regla de las tres ofertas (`tres_ofertas`)

Objeto obligatorio a nivel raíz. ConvoKit lo extrae de las bases (o de la Ley
38/2003 art. 31.3 si las bases remiten a ella). MemorAI lo usa para avisar al
consultor, partida a partida, cuando un gasto exige presentar tres
presupuestos comparativos.

```json
{
  "tres_ofertas": {
    "umbral": 15000,
    "exencion_gasto_antes_resolucion": true,
    "condiciones_exencion": "Las bases eximen de las tres ofertas cuando el gasto se ha ejecutado y facturado antes de la resolución de concesión; en ese caso se aporta la factura de la inversión realizada."
  }
}
```

- `umbral`: importe en euros (por proveedor y concepto) a partir del cual se
  exigen tres ofertas. Numérico, nunca string.
- `exencion_gasto_antes_resolucion`: booleano. `true` si la convocatoria
  permite no aportar las tres ofertas cuando el gasto se realiza antes de la
  resolución de la ayuda (p. ej. admitiendo la factura de la inversión ya
  ejecutada). **ConvoKit debe pronunciarse siempre**: si las bases no dicen
  nada, `false`.
- `condiciones_exencion`: texto con las condiciones exactas de las bases
  (cuándo aplica, qué documento sustituye a las ofertas). Cadena vacía si
  `exencion_gasto_antes_resolucion` es `false`.
- Si la convocatoria no exige tres ofertas en ningún caso: `umbral: null`.

## Parámetros de convocatoria (`parametros_convocatoria[]`)

Constantes que ConvoKit lee de las bases: plazos, límites, umbrales,
intensidades de ayuda. **Llevan siempre el valor incluido** — es información
de las bases, no algo que el consultor deba teclear. MemorAI los importa como
datos internos: los que corresponden a límites cuantitativos generan avisos
automáticos (nunca bloqueos) sobre el expediente o la partida afectada; el
resto se muestra como ficha informativa de solo lectura de la convocatoria.

```json
{
  "id": "limite-ingenieria-porcentaje",
  "label": "Límite máximo de ingeniería sobre el presupuesto subvencionable",
  "valor": 10,
  "unidad": "%",
  "nota": "Con tope adicional absoluto, ver limite-ingenieria-euros"
}
```

- `valor`: número, booleano, fecha ISO (`"2026-11-30"`) o texto corto, según
  el parámetro. **Nunca se omite**: un parámetro sin valor no aporta nada.
- `unidad`: `"%" | "EUR" | "años" | "meses" | "días" | "empleados"`... u
  omitida si no aplica.
- `nota`: opcional, matices de las bases que el número no captura.
- Parámetros que MemorAI usa como límite con aviso automático (usar estos
  ids exactos cuando existan en la convocatoria): `presupuesto-minimo`,
  `limite-ingenieria-porcentaje`, `limite-ingenieria-euros`,
  `limite-auditoria`, `puesta-funcionamiento-inicio`, `plazo-justificacion`,
  `intensidad-ayuda`, `limite-maximo-ayuda`. El resto (dotación, umbrales
  pyme, plazo de resolución, puntuación mínima, plazos de presentación...)
  se admite con id libre y queda como ficha informativa.
- Lo que antes iba en `datos_aplicativo` siendo en realidad un parámetro de
  las bases (límite de minimis, dotación presupuestaria, umbrales pyme...)
  va aquí, con su valor.

### Datos de aplicativo (`datos_aplicativo[]`)

Solo datos que **el consultor teclea por expediente** en el formulario
telemático y que ConvoKit no puede conocer (URL de la web del cliente,
empleados a contratar, municipio de la inversión...). Nunca constantes de
las bases: esas van en `parametros_convocatoria` con su valor.

```json
{
  "id": "empleados-a-contratar",
  "label": "Número de empleados a contratar con esta ayuda",
  "tipo_dato": "numero",
  "ambito": "proyecto",
  "obligatorio": true
},
{
  "id": "web-empresa",
  "label": "URL de la web de la empresa",
  "tipo_dato": "url",
  "ambito": "empresa",
  "obligatorio": false
},
{
  "id": "contratos-indefinidos",
  "label": "Los contratos generados serán indefinidos",
  "tipo_dato": "booleano",
  "ambito": "proyecto",
  "obligatorio": true
}
```

- `tipo_dato`: `texto_corto | numero | booleano | fecha | url | seleccion`.
  Para `seleccion`, añadir `opciones: [string]` con la lista cerrada.
- `ambito`: `empresa` (reutilizable entre expedientes futuros del mismo
  cliente, igual que `campos_empresa`, ej. la URL de la web) o `proyecto`
  (específico de este expediente, ej. empleados a contratar con esta ayuda
  concreta). Si un dato de ámbito `empresa` coincide semánticamente con uno
  del catálogo `campos_empresa` de otra convocatoria previa del mismo tipo,
  ConvoKit debe usar el mismo `id` cuando sea razonable.
- **Nunca generan un apartado ni un `prompt`**: MemorAI los presenta como un
  panel de captura de datos (checklist), no los envía a Claude para redactar,
  y no forman parte de las secciones exportadas al Word de la memoria — sirven
  de referencia al consultor para rellenar el formulario telemático de la
  convocatoria por su cuenta.
- Si un dato aparece tanto en la memoria narrativa como en el formulario
  (ej. la razón social encabeza la memoria y también el formulario), va como
  `dato_empresa` referenciado desde el apartado **y no** se duplica en
  `datos_aplicativo`.

## Validación

MemorAI rechazará en la subida (HTTP 400 con detalle) los JSON `2.x` que
incumplan: raíz no-objeto, `version_esquema` ausente, códigos repetidos,
apartado padre emitido junto a sus subapartados, `ref_campo_empresa`
huérfano, tipos de input fuera del vocabulario, `tres_ofertas` ausente o con
`umbral` no numérico (salvo `null`), parámetros de `parametros_convocatoria`
sin `valor`, `tipo_dato`/`ambito` de `datos_aplicativo` fuera del
vocabulario, `opciones` ausente en un dato `seleccion`, o placeholders de la
lista negra. El formato `1.x` (array plano) seguirá aceptándose con el
pipeline actual de deduplicación y clasificación durante la transición.
