# Contrato de salida ConvoKit → MemorAI (Salida 4)

Versión propuesta: `2.5` · Julio 2026

> Cambios 2.4 → 2.5, tras comparar los md internos de ConvoKit con su JSON
> para dos convocatorias distintas (DIGITALIZA-CV e INNOVA-CV/INNOVATeiC-CV):
> la mayoría de los datos que debían ir en `campos_proyecto` no se duplican
> en la conversión md → JSON, sino que **ya se piden dos o más veces en el
> propio md**, apartado a apartado (ejemplos reales: auditor + ROAC pedido
> en dos apartados distintos en ambas convocatorias; autocartera/socios/
> administradores pedidos en un apartado y repetidos íntegros en otro;
> Pacto Verde Europeo pedido hasta tres veces). Se añade una nota explícita
> exigiendo ese control también en la fase de redacción del md, no solo en
> la conversión. Además, se detectó un patrón nuevo — un apartado de
> resumen cuyos bloques de contenido se vuelven a redactar, en detalle y
> puntuados, en varios apartados posteriores — que no encajaba en ninguna
> regla existente; se añade la regla 16 y el checklist punto 14 para
> cubrirlo. Por último, se confirmó con un caso real (S3-CV en INNOVA-CV)
> que el conversor también puede introducir duplicados aunque el md de
> origen llegue limpio, así que la deduplicación en la conversión sigue
> siendo obligatoria con independencia del estado del md de entrada.
>
> Cambios 2.3 → 2.4, tras comparar el md interno de ConvoKit con su JSON
> para la misma convocatoria (INNOVA-CV): el md contiene un bloque "QUÉ
> BUSCA EL EVALUADOR" por apartado que se perdía íntegro en la conversión.
> Se añade el campo opcional `contexto_evaluador` en cada apartado para
> conservarlo. La comparación también confirmó que la pérdida del apartado
> B.5.5 ocurrió en el conversor md → JSON (el md lo tenía completo) y que
> los placeholders "[PEGA AQUÍ...]" nacen en la redacción del md, no en la
> conversión.
>
> Cambios 2.2 → 2.3, tras contrastar el tercer JSON real (INNOVA-CV /
> INNOVATeiC-CV) contra la memoria oficial en Word: faltaba un apartado
> completo (B.5.5, "Adquisición de activos materiales" — confirmado por
> nombre en el propio texto de B.5.2 de la memoria oficial), varios
> `prompt` contenían placeholders literales de "pega aquí" pensados para un
> copiado manual que MemorAI no hace, `campos_proyecto` seguía vacío pese a
> tener candidatos claros (grado de innovación, entorno/prioridad S3-CV,
> ubicación, fechas de proyecto, auditor+ROAC pedidos dos veces cada uno), y
> la lista de documentación obligatoria de la convocatoria (certificado
> CNAE, ficha PROPER, recibo SS, declaración DNSH...) no tenía dónde encajar
> porque no está ligada a ningún apartado concreto. Se prohíben los
> placeholders de copiar-pegar en `prompt`, se añade `documentos_convocatoria[]`
> y se refuerza la checklist para exigir un contraste apartado a apartado
> contra el índice de la memoria oficial.
>
> Cambios 2.0 → 2.1, tras revisar el primer JSON real (INPYME 2026):
> solo apartados hoja (sin bloque padre duplicado), nuevo bloque
> `parametros_convocatoria` con valor incluido, bloque `tres_ofertas`
> estructurado, `datos_aplicativo` restringido a lo que rellena el
> consultor, ids solo ASCII y prompts sin instrucciones conversacionales.
>
> Cambios 2.1 → 2.2, tras revisar el segundo JSON real (EMPYME 2026): la
> regla 1bis se cumplió, pero `parametros_convocatoria` llegó vacío mientras
> `datos_aplicativo` seguía cargado de constantes de la convocatoria (mismo
> fallo de 2.0, no corregido). Se añade un **test decisivo** para esa
> frontera, se prohíben cifras incrustadas en labels sin su parámetro
> correspondiente, se añade el catálogo `campos_proyecto[]` para datos de
> proyecto repetidos entre apartados (caso real: "sector en auge" pedido tres
> veces en la misma convocatoria) y una **checklist de autorrevisión**
> obligatoria antes de entregar cualquier JSON.

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
(inversión industrial, INPYME, EMPYME, INNOVA-CV/INNOVATeiC-CV,
DIGITALIZA-CV...) son ilustrativos, no plantilla: cada uno documenta un
fallo real detectado en un JSON concreto para explicar el porqué de una
regla, pero la regla en sí debe leerse en genérico y aplicarse igual a una
convocatoria de I+D+i, de empleo, de internacionalización o de cualquier
otro tipo, aunque no se haya visto un ejemplo real de ese tipo todavía.
Ningún nombre de campo, id sugerido ni número citado en un "caso real" es
obligatorio replicarlo tal cual en otra convocatoria: lo obligatorio es el
mecanismo (usar el mismo id cuando el dato se repite, mover constantes a
`parametros_convocatoria`, contrastar el índice de apartados contra la
memoria oficial, no repetir bloques de contenido entre apartados...), no el
ejemplo concreto. Los tipos de input y los flags reflejan la estructura de
MemorAI (perfil de empresa reutilizable, cuenta justificativa, cálculo de
rentabilidad), no la de ninguna convocatoria concreta. Para convocatorias
que no encajen en algún concepto, el contrato prevé escape explícito:

- Sin baremo por puntos → `puntos_max: null`.
- Sin distinción mínimo/completo → todos los inputs con `nivel: "minimo"`.
- Sin inversión (empleo, internacionalización...) → `usa_tabla_inversiones: false`.
- Sin análisis de rentabilidad → `requiere_calculo_rentabilidad: false`.
- Tipo de ayuda no contemplado → `tipo_ayuda: "otro"` (nunca forzar la categoría
  más parecida).

ConvoKit nunca debe omitir un apartado ni inventar estructura para cumplir el
esquema: si algo no aplica, se usa el valor de escape correspondiente.

### Contenido mínimo: fallar en voz alta, nunca entregar una cáscara vacía

Los valores de escape existen para bloques concretos que de verdad no
aplican, **no para vaciar el JSON entero**. Todo JSON entregado debe cumplir
un mínimo de viabilidad:

- `convocatoria.nombre`, `anio`, `organismo` y `fecha_generacion` siempre
  informados — no existe convocatoria sin nombre.
- `apartados[]` con al menos un apartado — una convocatoria sin ningún
  contenido de memoria que redactar no necesita la Salida 4.

Si ConvoKit no puede extraer ese mínimo (bases ilegibles, memoria no
encontrada, error de procesamiento), debe **detenerse y reportar el error
con su causa**, nunca emitir un JSON esquemáticamente válido pero vacío.
Un esqueleto vacío es el peor resultado posible: parece un éxito, se
importa sin ruido y el fallo se descubre tarde. Caso real: se recibió un
JSON v2.2 con todos los bloques en valor de escape a la vez (nombre `""`,
año `null`, cero apartados, cero campos) — inservible pero silencioso.
MemorAI rechaza estos JSON en la subida.

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
  "campos_proyecto": [ ... ],
  "apartados": [ ... ],
  "tres_ofertas": { ... },
  "parametros_convocatoria": [ ... ],
  "documentos_convocatoria": [ ... ],
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

## Catálogo de campos de proyecto (`campos_proyecto[]`)

Mismo mecanismo que `campos_empresa`, pero para datos **específicos de este
expediente** (no reutilizables con otro cliente) que aun así se piden en más
de un sitio dentro de la misma convocatoria: en varios apartados, o en un
apartado y también en `datos_aplicativo`.

Caso real que motiva esto: en EMPYME 2026 el "sector de actividad en auge"
se pedía como `texto_libre` en el apartado C.1, otra vez como `texto_libre`
en C.2, y una tercera vez como `seleccion` en `datos_aplicativo`. El
consultor habría tenido que teclear el mismo dato tres veces.

```json
{
  "id": "sector-auge",
  "nombre": "Sector de actividad en auge de la convocatoria",
  "descripcion": "Uno de los doce sectores listados en las bases, o justificación si no encaja en ninguno. Se usa en C.1, C.2 y en el formulario telemático.",
  "formato": "texto"
}
```

- **Regla de oro, igual que en `campos_empresa`**: un mismo dato de proyecto
  usado en más de un sitio de la convocatoria se define **una vez** aquí y se
  referencia desde donde haga falta. Nunca se redefine con otro `id` o como
  `texto_libre` suelto en cada apartado.
- Los apartados lo referencian con un input `tipo: "dato_proyecto"` y
  `ref_campo_proyecto` (ver regla 3 más abajo).
- Si el mismo dato también hace falta en el formulario telemático, la
  entrada de `datos_aplicativo` lo referencia con `ref_campo_proyecto` en
  vez de redefinir `id`/`label` (ver sección de `datos_aplicativo`).
- No usar `campos_proyecto` para lo que solo aparece una vez en toda la
  convocatoria: eso sigue siendo un input `texto_libre` normal dentro del
  apartado, o una entrada normal de `datos_aplicativo`.

### El origen de la duplicación no está solo en la conversión a JSON

Comprobado con dos convocatorias distintas: la mayoría de los casos en que
`campos_proyecto` debía usarse y no se usó no son un fallo del paso de
conversión md → JSON, sino que **el propio md ya pide el mismo dato o el
mismo bloque de contenido en más de un apartado**, antes de que exista
ningún JSON. Esto significa que la corrección no puede limitarse al
conversor: durante la redacción del md, apartado a apartado, ConvoKit debe
mantener un registro por convocatoria de qué datos y qué bloques de
contenido ya se han pedido en un apartado anterior, y contrastarlo antes de
redactar el siguiente. Si un apartado posterior pide un dato ya registrado,
no debe volver a pedirlo desde cero: debe quedar marcado como el mismo dato
subyacente para que la conversión a JSON lo unifique con un único `id`.

Dicho esto, la deduplicación en la conversión a JSON sigue siendo
obligatoria en todo caso, incluso cuando el md de origen ya llega sin
duplicados: un conversor que no aplique activamente esta regla puede
introducir duplicados nuevos que no estaban en el md (caso real: un dato
pedido una sola vez en el md apareció triplicado en `datos_aplicativo` del
JSON).

## Apartados (`apartados[]`)

```json
{
  "codigo": "A.3",
  "nombre": "Viabilidad económica del proyecto",
  "puntos_max": 15,
  "contexto_evaluador": "El evaluador comprueba que la rentabilidad esté justificada con al menos una ratio y su método, que las fuentes de financiación estén desglosadas y que el payback tenga cálculo explícito. Umbral mínimo del bloque: 15 puntos.",
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
   - `texto_libre`: dato específico del proyecto que redacta el consultor y
     que **solo se pide una vez** en toda la convocatoria.
   - `dato_empresa`: dato general de la empresa → obligatorio
     `ref_campo_empresa` apuntando a un `id` de `campos_empresa`.
   - `dato_proyecto`: dato específico del proyecto que se repite en más de
     un sitio de la convocatoria → obligatorio `ref_campo_proyecto`
     apuntando a un `id` de `campos_proyecto`.
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
13. **Prohibidos los placeholders de "pega aquí" dentro del `prompt`.** Nunca
    escribir cosas como `[PEGA AQUÍ: opción de innovación seleccionada...]`
    o `[ADJUNTA O PEGA AQUÍ: listado de empleados...]` en el texto del
    `prompt`. MemorAI no copia nada a mano dentro del prompt: los datos del
    proyecto se envían aparte, en un bloque separado que MemorAI construye
    automáticamente a partir de `inputs[]`. Un `prompt` con estos
    placeholders llega a Claude sin resolver y contamina el borrador. El
    `prompt` debe poder leerse y ejecutarse tal cual, dando por hecho que los
    datos de `inputs[]` llegarán en un bloque aparte, nunca insertados en su
    interior.
14. **Cada apartado narrativo real de la memoria oficial tiene su entrada en
    `apartados[]`, sin excepción**, aunque no puntúe y aunque su contenido
    parezca solo tabular o de verificación (ver checklist, punto 10).
15. **`contexto_evaluador` (opcional, recomendado)**: campo de texto por
    apartado con lo que el evaluador comprueba en él — criterios de
    puntuación, condiciones de elegibilidad del gasto, advertencias de la
    convocatoria ("no computará si no está argumentado...", umbrales). Si
    el proceso interno de ConvoKit ya genera este análisis (bloque "QUÉ
    BUSCA EL EVALUADOR" o equivalente), se vuelca aquí tal cual en lugar de
    descartarse. MemorAI lo muestra al consultor como guía junto a la
    sección; **no** se envía a Claude (lo que Claude necesita saber del
    evaluador debe estar en el `prompt`).
16. **Un apartado de resumen o presentación no debe duplicar en bloque el
    contenido de apartados posteriores que lo desarrollan en detalle y con
    su propia puntuación.** Caso real: un apartado sin puntuación propia
    incluía, entre otros, un bloque de "impacto económico" y un bloque de
    "alineación con el Pacto Verde Europeo"; ambos volvían a aparecer,
    desarrollados en mucho más detalle y puntuados, como apartados
    independientes más adelante en la misma memoria. El apartado de resumen
    debe emitirse **sin los bloques que un apartado posterior desarrolla ya
    en detalle** — conservando solo el contenido que no se repite en
    ningún otro sitio — en vez de pedir la misma redacción dos veces. No es
    el mismo caso que la regla 1bis (bloque padre + hijos con numeración
    jerárquica compartida): aquí los apartados no comparten prefijo de
    código, así que hay que detectarlo por contenido, no por numeración.

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

### Test decisivo: `parametros_convocatoria` vs. `datos_aplicativo`

Esta frontera ha fallado dos veces seguidas (INPYME y EMPYME): cosas que son
constantes de las bases se han seguido colando en `datos_aplicativo` en vez
de `parametros_convocatoria`, incluso con el campo ya presente en el
esquema. Aplicar siempre esta pregunta, dato por dato, antes de decidir
dónde va:

> **¿Este valor es el mismo para cualquier empresa que presente esta
> convocatoria, o cada solicitante declara el suyo?**
> - Mismo valor para todos → `parametros_convocatoria`, con el valor.
> - Cada solicitante aporta uno distinto → `datos_aplicativo`, sin valor.

Ejemplos reales mal clasificados en el JSON de EMPYME 2026 que deben ir en
`parametros_convocatoria` (ConvoKit ya conoce el valor al leer las bases,
es el mismo para las 200 empresas que se presenten):
`limite-maximo-subvencion-beneficiario`, `limite-minimis-tres-anos`,
`salario-bruto-maximo-mensual`, `fecha-publicacion-convocatoria`,
`url-tramite-telematico`, `plazo-subsanacion-dias`, `plazo-resolucion-meses`,
`extension-maxima-proyecto-hojas`, `tamanio-fuente-proyecto`,
`validez-certificados-meses`, `periodo-conservacion-documentos-anos`,
`periodo-subvencionable-inicio`, `periodo-subvencionable-fin`,
`plazo-presentacion-inicio`, `plazo-presentacion-fin`.

Frente a esto, `importe-subvencion-solicitado` o
`numero-empleados-contratados` sí son `datos_aplicativo` correctos: cada
empresa solicita un importe distinto y contrata un número distinto de
personas.

**Prohibido incrustar cifras de las bases dentro de un `label`** (p. ej.
`"Porcentaje de subvención solicitado (máximo 70%)"`). Si hay un tope, ese
tope va como su propio parámetro en `parametros_convocatoria`
(`limite-porcentaje-subvencion: 70`); el `label` del dato que sí varía por
solicitante se queda sin el número (`"Porcentaje de subvención solicitado"`).

Si `parametros_convocatoria` se entrega vacío (`[]`) en una convocatoria que
tiene plazos, límites o topes en las bases —prácticamente siempre los
tiene—, es señal de que no se ha aplicado este test y el JSON se devolverá.

## Documentación general de la convocatoria (`documentos_convocatoria[]`)

Documentos que hay que adjuntar a **toda** solicitud de esta convocatoria,
con independencia de cualquier apartado concreto de la memoria: certificados
de organismos oficiales, fichas de alta en plataformas de la administración,
declaraciones responsables normalizadas. No encajan en `documentos_requeridos`
(que es por apartado) ni son un dato que rellena el consultor
(`datos_aplicativo`): son papeles a reunir y adjuntar, iguales para
cualquier expediente de esta convocatoria.

Caso real que motiva esto (INNOVA-CV / INNOVATeiC-CV): la memoria oficial
exige, para cualquier solicitud, el certificado de situación en el censo de
actividades económicas (AEAT), la ficha de alta en PROPER, el recibo de
liquidación de cotizaciones de la Seguridad Social (para acreditar mínimo de
empleados), la declaración DNSH y la declaración de cumplimiento de la Ley
contra la morosidad. Ninguno de estos documentos estaba en ningún apartado
del JSON: se perdían por completo.

```json
{
  "nombre": "Certificado de situación en el censo de actividades económicas (AEAT)",
  "fuente": "cliente",
  "obligatorio": true,
  "nota": "Debe constar al menos un CNAE admitido según el anexo de la convocatoria"
}
```

- `fuente`: mismo vocabulario que `documentos_requeridos`
  (`cliente | perfil_estrategico | generado`).
- `obligatorio`: booleano. Si depende de una condición ("si procede", "si
  tiene Plan de Igualdad"), `obligatorio: false` y la condición va en `nota`.
- `nota`: opcional, condición o matiz de las bases.
- Si alguna de estas condiciones coincide con un parámetro de
  `parametros_convocatoria` (p. ej. un mínimo de empleados en nómina que
  también limita elegibilidad), referenciarlo en `nota`, no duplicar el
  número.

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
- Si el dato ya está definido en `campos_proyecto` porque también se pide en
  algún apartado, la entrada aquí lleva `ref_campo_proyecto` en vez de
  `label`/`tipo_dato` propios — no se redefine dos veces.
- **Nunca generan un apartado ni un `prompt`**: MemorAI los presenta como un
  panel de captura de datos (checklist), no los envía a Claude para redactar,
  y no forman parte de las secciones exportadas al Word de la memoria — sirven
  de referencia al consultor para rellenar el formulario telemático de la
  convocatoria por su cuenta.
- Si un dato aparece tanto en la memoria narrativa como en el formulario
  (ej. la razón social encabeza la memoria y también el formulario), va como
  `dato_empresa` (o `dato_proyecto`) referenciado desde el apartado **y no**
  se duplica en `datos_aplicativo`.
- **Nunca es una constante de las bases.** Antes de añadir una entrada aquí,
  aplicar el test decisivo de la sección anterior: si el valor es el mismo
  para cualquier solicitante, es `parametros_convocatoria`, no esto.

## Checklist de autorrevisión (obligatoria antes de entregar el JSON)

ConvoKit debe repasar esta lista sobre su propio JSON antes de darlo por
bueno. Cada punto corresponde a un fallo real ya detectado en una entrega
anterior — repetirlo significa que el JSON se devuelve.

1. ¿Algún apartado con subapartados propios aparece también como bloque
   agregado (padre + hijos a la vez)? → dejar solo las hojas.
2. ¿Algún input `texto_libre` pide un dato que ya existe en `campos_empresa`
   con otro nombre? → convertir a `dato_empresa` + `ref_campo_empresa`.
3. ¿Algún dato de proyecto (no de empresa) se pide en más de un apartado, o
   en un apartado y también en `datos_aplicativo`, con `id`/`label`
   distintos cada vez? → moverlo a `campos_proyecto` y referenciarlo con
   `dato_proyecto` / `ref_campo_proyecto`.
4. Por cada entrada de `datos_aplicativo`: aplicar el test decisivo
   (¿mismo valor para cualquier solicitante?). Si la respuesta es sí, no
   debería estar aquí sino en `parametros_convocatoria`.
5. Si `parametros_convocatoria` queda vacío, confirmar explícitamente que
   las bases no contienen ningún plazo, límite, umbral o intensidad de
   ayuda — algo muy raro. Si existen y se dejaron fuera, añadirlos.
6. ¿Algún `label` lleva una cifra de las bases incrustada entre paréntesis
   (`"máximo X"`, `"hasta Y%"`)? → esa cifra sale del label y entra como su
   propio parámetro en `parametros_convocatoria`.
7. ¿Algún `id` lleva tilde o eñe? → pasar a ASCII.
8. ¿Algún `prompt` da por hecho que puede pedir algo "antes de continuar" o
   esperar respuesta del consultor? → sustituir por `[DATO PENDIENTE: ...]`.
9. `tres_ofertas` y `campos_proyecto`/`parametros_convocatoria`: presentes
   siempre, aunque sea con el valor de escape (`umbral: null`, arrays
   vacíos si de verdad no aplican tras el punto 5).
10. **Contrastar el índice de `apartados[]` contra el índice de la memoria
    oficial, epígrafe por epígrafe.** Si la memoria tiene un B.5.5 y el JSON
    salta de B.5.4 a B.5.6, falta un apartado. Esto aplica también a
    apartados que parezcan "solo tabla" o "solo verificación": si tienen su
    propio encabezado en la memoria oficial, tienen su propia entrada en
    `apartados[]`.
11. ¿Algún `prompt` contiene un placeholder de "pega aquí" o "adjunta aquí"
    pensado para copiar información a mano? → eliminarlo; los datos van en
    `inputs[]`, nunca incrustados en el texto del `prompt`.
12. ¿Hay documentos que la convocatoria exige para cualquier solicitud
    (certificados oficiales, fichas de alta en plataformas, declaraciones
    responsables normalizadas) que no están ligados a ningún apartado
    concreto? → van en `documentos_convocatoria`, no se pierden.
13. **Contenido mínimo**: ¿`convocatoria.nombre` informado y `apartados[]`
    con al menos una entrada? Si no, algo ha fallado en la extracción:
    detenerse y reportar la causa, nunca entregar el esqueleto vacío.
14. **¿Algún apartado sin puntuación propia funciona como resumen y
    contiene bloques que luego se redactan en detalle, con su propia
    puntuación, en uno o varios apartados posteriores?** → retirar del
    apartado de resumen los bloques que se repiten en otro sitio (regla
    16). Este contraste hay que hacerlo por contenido, no solo por
    numeración: no lo detecta el mismo chequeo que el punto 1.

## Validación

MemorAI rechazará en la subida (HTTP 400 con detalle) los JSON `2.x` que
incumplan: raíz no-objeto, `version_esquema` ausente,
`convocatoria.nombre` vacío o `apartados[]` vacío (esqueleto sin
contenido), códigos repetidos,
apartado padre emitido junto a sus subapartados, `ref_campo_empresa` o
`ref_campo_proyecto` huérfano, tipos de input fuera del vocabulario
(incluido `dato_proyecto` sin `ref_campo_proyecto`), `tres_ofertas` ausente o
con `umbral` no numérico (salvo `null`), parámetros de
`parametros_convocatoria` sin `valor`, entradas de `documentos_convocatoria`
sin `nombre`/`fuente`/`obligatorio`, `tipo_dato`/`ambito` de
`datos_aplicativo` fuera del vocabulario, `opciones` ausente en un dato
`seleccion`, un `prompt` que contenga las cadenas `PEGA AQUÍ` o `ADJUNTA
AQUÍ` (u otro placeholder de copiar-pegar), o placeholders de la lista
negra. El formato `1.x` (array plano) seguirá aceptándose con el pipeline
actual de deduplicación y clasificación durante la transición.
