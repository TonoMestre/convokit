# Análisis de causa raíz — los 2 gaps globales del pase real

Fase B de la auditoría posterior a `REAL CONVOKIT KNOWLEDGE PACK PASS`
(ver `00_MANIFEST.md`). Solo investigación — nada de lo aquí descrito se ha
implementado.

## 1. `tres_ofertas`

**Regla normativa real y dónde aparece**: existe literalmente en
`CONVOCATORIA INPYME 2026_firmado.pdf` (etiqueta `convocatoria` en
convokit.db, convocatoria histórica id 8), cláusula (k) de las obligaciones
del beneficiario:

> "Cuando el importe de adquisición de un activo o servicio supere las
> cuantías establecidas en la legislación vigente de contratación para el
> contrato menor, la empresa beneficiaria deberá disponer de al menos tres
> ofertas de diferentes proveedores [...] No obstante [...] no será
> necesario disponer de tres ofertas diferentes cuando el gasto se hubiere
> contratado con anterioridad a la fecha de publicación de la resolución de
> concesión [...]"

Esto matiza el supuesto inicial del encargo: el umbral no es una cifra
literal en INPYME, sino una remisión a la legislación de contratación
pública ("contrato menor"), y hay una segunda excepción (mercado
insuficiente) que tampoco está modelada hoy.

**Dominio semántico**: es una **obligación de justificación de gasto /
procedimiento de contratación del beneficiario**, no un criterio de
evaluación del baremo. Vive en la sección de obligaciones de las bases, no
en el Anexo II de criterios.

**¿Lo puede modelar Application Knowledge hoy?** No. El esquema de
`application_knowledge_entities` (migración 0053) tiene `entity_type`
cerrado a `evaluation_block | evaluation_criterion | evaluation_subcriterion`
— solo modela el baremo. ConvoKit sí anticipa este tipo de regla en su
propio vocabulario más amplio (`procedural_rule`, `cost_rule` en
`ENTITY_TYPES`, y `build_ficha_from_pack` ya busca explícitamente una
entidad `entity_id=="tres-ofertas"` o `entity_type=="procedural_rule"` con
"oferta" en el label) — pero el lado de i40 nunca la extrae porque el
catálogo de Application Knowledge para INPYME (los `inpyme2026-block-*.v1.json`)
nunca declaró ese slot. **No es un fallo de extracción ni del adaptador
`export.py`: es una regla fuera del alcance que el catálogo actual declara**
— Application Knowledge, en su versión actual, solo modela baremo.

**¿Es funcionalmente inerte el valor de escape?** No. `tres_ofertas:
{umbral: null, exencion_gasto_antes_resolucion: false, condiciones_exencion: ""}`
pasa la validación del contrato v2.5 (null es válido), pero es
**semánticamente incorrecto** para INPYME: la convocatoria SÍ impone la
regla. Según `docs/contrato-convokit.md`, MemorAI usa este campo para avisar
al consultor partida a partida cuando hacen falta tres ofertas comparativas
— ese aviso se pierde en silencio para una obligación de cumplimiento real
con consecuencia económica (gasto no subvencionable si falta la
justificación). Vale la pena resolverlo, no es cosmético.

**Cambio mínimo (no implementado)**: ampliar el catálogo de Application
Knowledge de INPYME con un nuevo `entity_type` (o extender el existente) que
cubra reglas procedimentales/de coste, no solo baremo — decisión de alcance
del dominio Application Knowledge, no un bug puntual.

## 2. `convocatoria_metadata.tipo_ayuda`

**Qué espera ConvoKit**: un valor del vocabulario cerrado
`inversion_productiva | digitalizacion | idi | internacionalizacion |
medioambiente_energia | empleo | otro` (`docs/contrato-convokit.md`,
`exporters.py`, `prompts.py`) a nivel de convocatoria.

**Derivación razonable para INPYME**: el propio título completo de la
convocatoria ("Ayudas para apoyar las inversiones para la
reindustrialización... de las pymes de diversos sectores industriales")
mapea limpiamente a `inversion_productiva`.

**¿Existe ya en i40 en otro campo?** No. Consulta read-only completa
(`SELECT *`) sobre la fila de `public.analyses` de INPYME 2026: columnas
`id, organization_id, title, public_body, call_year, mode, status,
created_by, created_at, updated_at, corpus_status,
current_evaluation_run_id, current_analysis_run_id` — ninguna es una
taxonomía de tipo de ayuda (`mode` es un flag de momento de evaluación,
`ex_ante`, no de tipo de ayuda). Búsqueda en todo el repo de i40 de
`tipo_ayuda|call_type|aid_type|grant_type|tipo_convocatoria`: cero
resultados.

**¿Falta solo en el exportador o falta en origen?** Falta en origen: i40 no
almacena esta clasificación en ningún sitio todavía. `to_convokit_pack`
solo puebla `nombre/anio/organismo` porque es lo único que existe en
`analyses`; no es una omisión del adaptador.

**¿Provoca pérdida funcional real o es solo un fallback inerte?** Es
prácticamente inerte. Ningún condicional de ConvoKit bifurca sobre
`tipo_ayuda` (grep confirmado, cero resultados); solo se valida contra el
vocabulario cerrado en el exportador. Según CLAUDE.md, MemorAI lo usa para
"ajustar el registro de redacción" — degradación de calidad cosmética, no
un aviso de cumplimiento perdido como en el caso anterior.

**Cambio mínimo (no implementado)**: añadir una columna/clasificación de
tipo de ayuda a `public.analyses` (o a los metadatos de convocatoria de i40)
y poblarla en `to_convokit_pack`; o, más barato a corto plazo, que ConvoKit
lo derive determinísticamente del título de la convocatoria con una regla
simple cuando el Knowledge Pack no lo traiga — evaluable solo cuando haya
una segunda convocatoria real que confirme si el patrón por título
generaliza.

## Priorización relativa

`tres_ofertas` > `tipo_ayuda`: el primero pierde un aviso de cumplimiento
con consecuencia económica real para el cliente; el segundo solo degrada el
registro de redacción. Ver `00_MANIFEST.md`/roadmap en el informe de la
sesión para la clasificación P0/P1/P2 completa.
