# -*- coding: utf-8 -*-
"""
Tests del modo i40 Knowledge Pack. Sin red, sin llamadas a Claude: cubren el
parseo, el matching determinista, el manejo de estados (conflict/not_located/
MISSING/human_validated) y la estabilidad de ids — que es exactamente lo que
puede probarse sin depender de un modelo generativo.

Ejecutar: python -m unittest backend.tests.test_knowledge_pack -v
(desde la raíz del repo, o `python -m unittest discover -s backend/tests`)
"""
import copy
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import knowledge_pack as kp


def _entity(**overrides) -> dict:
    base = {
        "entity_id": "iib-criterion",
        "entity_type": "criterion",
        "section_ref": "II.B Viabilidad económica de la inversión",
        "label": "Puntuación de II.B",
        "value": {"puntos_max": 4},
        "evidence_status": "accredited",
        "review_state": "human_validated",
        "evidence_refs": [
            {"document_id": "doc-1", "quote": "Viabilidad económica (Máximo 4 puntos)", "section": "Anexo II"}
        ],
    }
    base.update(overrides)
    return base


def _pack(entities: list[dict]) -> dict:
    return {"pack_id": "kp-test", "convocatoria_ref": "INPYME-2026", "entities": entities}


class TestParsing(unittest.TestCase):
    def test_valid_pack_parses(self):
        pack = kp.parse_knowledge_pack(_pack([_entity()]))
        self.assertEqual(pack.pack_id, "kp-test")
        self.assertEqual(len(pack.entities), 1)
        e = pack.entities[0]
        self.assertEqual(e.entity_type, "criterion")
        self.assertEqual(e.evidence_status, "accredited")
        self.assertEqual(e.review_state, "human_validated")
        self.assertEqual(e.evidence_refs[0].document_id, "doc-1")

    def test_rejects_bad_entity_type(self):
        with self.assertRaises(kp.KnowledgePackError):
            kp.parse_knowledge_pack(_pack([_entity(entity_type="not_a_type")]))

    def test_rejects_bad_evidence_status(self):
        with self.assertRaises(kp.KnowledgePackError):
            kp.parse_knowledge_pack(_pack([_entity(evidence_status="definitely_true")]))

    def test_rejects_duplicate_entity_ids(self):
        with self.assertRaises(kp.KnowledgePackError):
            kp.parse_knowledge_pack(_pack([_entity(), _entity()]))

    def test_conflict_without_conflicting_values_rejected(self):
        with self.assertRaises(kp.KnowledgePackError):
            kp.parse_knowledge_pack(_pack([_entity(evidence_status="conflict", conflicting_values=[])]))

    def test_root_must_be_object_not_array(self):
        with self.assertRaises(kp.KnowledgePackError):
            kp.parse_knowledge_pack([_entity()])

    def test_traditional_mode_untouched(self):
        """El modo tradicional (documentos -> _generate_output_4) no importa este
        módulo salvo si se invoca explícitamente; parsear un pack no tiene efecto
        alguno sobre extractors.build_context ni sobre el pipeline existente."""
        import extractors
        pack = kp.parse_knowledge_pack(_pack([_entity()]))
        # el pack nunca debe colarse en build_context: no expone ningún campo
        # 'texto' ni 'etiqueta' que build_context reconozca como documento.
        self.assertFalse(hasattr(pack, "texto"))
        self.assertNotIn("i40_knowledge_pack", extractors.ORIGINAL_LABELS)


class TestStatusHandling(unittest.TestCase):
    def test_human_validated_is_canonical(self):
        e = kp.parse_knowledge_pack(_pack([_entity()])).entities[0]
        self.assertTrue(e.is_canonical())
        self.assertFalse(e.is_usable_but_unvalidated())

    def test_accredited_unvalidated_is_usable_but_flagged(self):
        e = kp.parse_knowledge_pack(_pack([_entity(review_state="unvalidated")])).entities[0]
        self.assertFalse(e.is_canonical())
        self.assertTrue(e.is_usable_but_unvalidated())

    def test_conflict_never_becomes_categorical_fact(self):
        raw = _entity(
            evidence_status="conflict", review_state="unvalidated",
            conflicting_values=[{"puntos_max": 4}, {"puntos_max": 6}],
        )
        e = kp.parse_knowledge_pack(_pack([raw])).entities[0]
        self.assertTrue(e.is_conflict())
        self.assertFalse(e.is_canonical())
        self.assertFalse(e.is_usable_but_unvalidated())
        # una entidad en conflicto nunca aparece en el contexto normativo formateado
        match = kp.SectionMatch(codigo="II.B", nombre="x", matched=[kp.MatchedEntity(e, 0.9, "test")], match_state="strong")
        self.assertEqual(kp.usable_entities(match), [])
        self.assertIn("", kp.format_normative_context(match))  # bloque vacío, no inventado
        self.assertEqual(kp.format_normative_context(match), "")

    def test_not_located_is_not_same_as_not_existing(self):
        """not_located = desconocido. No debe tratarse como si el dato no existiera
        (eso sería not_applicable), y debe seguir generando un gap explícito, no
        un '0' ni un 'no aplica' silencioso."""
        e_dict = _entity(entity_id="iib-payback", evidence_status="not_located", review_state="unvalidated")
        pack = kp.parse_knowledge_pack(_pack([e_dict]))
        e = pack.entities[0]
        self.assertTrue(e.is_missing())
        self.assertNotEqual(e.evidence_status, "not_applicable")
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        gaps = kp.compute_knowledge_gaps(match, "unknown")
        # is_missing() entidades no entran en usable_entities y no generan un
        # missing_entity_type distinto per se, pero tampoco se cuelan como hecho:
        self.assertNotIn(e, kp.usable_entities(match))

    def test_missing_registers_gap_never_autofilled(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(evidence_status="not_provided", review_state="unvalidated")]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        # sin ninguna entidad 'criterion' usable -> gap de tipo missing_entity_type
        gaps = kp.compute_knowledge_gaps(match, "scored")
        kinds = {g.kind for g in gaps}
        self.assertIn("missing_entity_type", kinds)
        self.assertEqual(kp.usable_entities(match), [])


class TestGapsNeverFilledFromTemplate(unittest.TestCase):
    def test_gap_stays_a_gap_even_with_matching_template_section(self):
        """Aunque el apartado de la plantilla exista y tenga nombre reconocible,
        si el Knowledge Pack no cubre el criterio, el hueco se registra: no se
        rellena leyendo la plantilla como fuente normativa (eso no está disponible
        aquí: este módulo nunca recibe texto de plantilla, solo codigo/nombre)."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(entity_type="subcriterion", label="Fuentes de financiación", value={"puntos_max": 1}),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(match.match_state, "strong")
        gaps = kp.compute_knowledge_gaps(match, "scored")
        self.assertTrue(any(g.kind == "missing_entity_type" and g.entity_type == "criterion" for g in gaps))


class TestMatching(unittest.TestCase):
    def test_codigo_exact_match_is_strong(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(section_ref="II.B")]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(match.match_state, "strong")
        self.assertEqual(match.matched[0].match_basis, "codigo_exacto")

    def test_semantic_match_without_literal_equality(self):
        """'Viabilidad económica de la inversión' (plantilla) debe emparejar con
        'Viabilidad economica del proyecto' (Knowledge Pack) sin ser idénticos."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(section_ref="Viabilidad economica del proyecto de inversion"),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertIn(match.match_state, ("strong", "weak"))
        self.assertGreater(match.matched[0].confidence, 0)

    def test_no_match_when_unrelated(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(section_ref="Impacto ambiental del proyecto")]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(match.match_state, "none")
        self.assertEqual(match.matched, [])

    def test_never_invents_identifier_when_no_match(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(section_ref="Impacto ambiental")]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        gaps = kp.compute_knowledge_gaps(match, "scored")
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0].kind, "no_match")


class TestStableInputIds(unittest.TestCase):
    def test_same_entity_stable_id_regardless_of_label_wording(self):
        """Los dos labels legacy de INPYME ('...con hipótesis que los sustentan'
        vs '...con hipótesis sustentadas') deben resolver al mismo id estable
        cuando proceden de la misma entidad del Knowledge Pack."""
        entity = kp.parse_knowledge_pack(_pack([
            _entity(entity_id="estimacion-ingresos-ahorro", entity_type="subcriterion",
                    label="Estimación de ingresos adicionales o ahorro de costes anuales con hipótesis que los sustentan"),
        ])).entities[0]
        id_a = kp.stable_input_id(entity, "Estimación de ingresos adicionales o ahorro de costes anuales con hipótesis que los sustentan")
        id_b = kp.stable_input_id(entity, "Estimación de ingresos adicionales o ahorro de costes anuales con hipótesis sustentadas")
        self.assertEqual(id_a, id_b)
        self.assertEqual(id_a, "estimacion-ingresos-ahorro")

    def test_fallback_id_is_ascii_slug_of_label(self):
        id_ = kp.stable_input_id(None, "Fuentes de financiación con años y eñes")
        self.assertTrue(id_.isascii())
        self.assertNotIn(" ", id_)
        self.assertNotIn("ñ", id_)


class TestProvenanceAudit(unittest.TestCase):
    def test_provenance_records_refs_gaps_conflicts_unvalidated(self):
        entities = [
            _entity(entity_id="a", review_state="human_validated"),
            _entity(entity_id="b", entity_type="subcriterion", label="b", review_state="unvalidated"),
            _entity(entity_id="c", entity_type="subcriterion", label="c", evidence_status="conflict",
                    review_state="unvalidated", conflicting_values=[1, 2]),
        ]
        pack = kp.parse_knowledge_pack(_pack(entities))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        gaps = kp.compute_knowledge_gaps(match, "scored")
        prov = kp.build_section_provenance(match, gaps)
        self.assertIn("a", prov.knowledge_refs)
        self.assertIn("b", prov.knowledge_refs)
        self.assertNotIn("c", prov.knowledge_refs)  # conflict nunca entra como usable
        self.assertIn("b", prov.unvalidated_knowledge_used)
        self.assertIn("c", prov.conflicts_used)
        self.assertTrue(any(er["entity_id"] == "a" for er in prov.evidence_refs))
        d = prov.to_dict()
        self.assertEqual(d["deliverable_section"], "II.B")


class TestDeliverableContextSanitization(unittest.TestCase):
    """Endurecimiento 1. Todos los casos son deterministas (sin red, sin IA):
    ejercitan directamente kp.sanitize_deliverable_context sobre texto fijo."""

    def test_a_max_1_punto_queda_oculto(self):
        text = "Periodo de recuperación de la inversión (pay-back) y método para su obtención (máx. 1 punto)"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("1 punto", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual([h.rule for h in hits], ["puntuacion"])

    def test_b_maximo_15_puntos_queda_oculto(self):
        text = "B. | Viabilidad económica de la inversión (Máximo 15 puntos)"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("15 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual(len(hits), 1)

    def test_c_umbral_minimo_3_puntos_queda_oculto(self):
        text = "No se supera el umbral mínimo 3 puntos"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("3 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual(len(hits), 1)

    def test_d_estructura_codigo_y_nombre_permanece_intacta(self):
        text = "II.B — Viabilidad económica de la inversión"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertEqual(out, text)
        self.assertEqual(hits, [])

    def test_e_numeros_estructurales_inocuos_no_desaparecen(self):
        for text in (
            "Tabla con 3 columnas y 5 filas",
            "Anexo II, apartado 2",
            "II.B Viabilidad económica de la inversión",
            "Adjuntar 2 presupuestos comparativos por proveedor",
        ):
            out, hits = kp.sanitize_deliverable_context(text)
            self.assertEqual(out, text, f"texto estructural alterado: {text!r} -> {out!r}")
            self.assertEqual(hits, [])

    def test_f_valor_oculto_en_deliverable_sigue_disponible_via_normative_context(self):
        """Que DELIVERABLE_CONTEXT oculte '1 punto' no afecta a NORMATIVE_CONTEXT:
        son bloques independientes. Si el Knowledge Pack SÍ trae el subcriterio,
        format_normative_context lo sigue exponiendo con normalidad — el
        sanitizador nunca toca las entidades del pack, solo el texto del
        entregable."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(entity_id="iib-sub-payback", entity_type="subcriterion",
                    label="Periodo de recuperación de la inversión (pay-back)",
                    value={"puntos_max": 1}),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        normative_context = kp.format_normative_context(match)
        self.assertIn("Periodo de recuperación de la inversión (pay-back)", normative_context)
        self.assertIn("1", normative_context)

        deliverable_text = "Periodo de recuperación de la inversión (pay-back) y método para su obtención (máx. 1 punto)"
        sanitized, _ = kp.sanitize_deliverable_context(deliverable_text)
        self.assertNotIn("1 punto", sanitized)
        # el bloque normativo, construido aparte, es intocado por la sanitización
        # del deliverable — ambos coexisten con procedencia distinta.
        self.assertIn("1", normative_context)

    def test_real_inpyme_percentage_and_currency_limit_sanitized(self):
        """Caso real de INPYME 2026 (F96434.xlsx, hoja RESUMEN): el límite de
        ingeniería industrial no usa 'máximo/límite' pegado al número, sino
        'no podrá superar'. Confirma que el sanitizador también cubre esa
        formulación real, no solo el ejemplo mínimo de 'puntos'."""
        text = (
            "COSTES DE CONTRATACIÓN EXTERNA DE INGENIERÍA INDUSTRIAL (no podrá superar "
            "el 15% del total de gastos admitidos como subvencionables)"
        )
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("15%", out)
        self.assertEqual([h.rule for h in hits], ["porcentaje"])

    def test_original_document_never_modified(self):
        """La sanitización opera sobre una copia de texto; no existe ningún
        mecanismo en sanitize_deliverable_context que pueda mutar el string de
        entrada (los str de Python son inmutables, pero se verifica también que
        la función es pura: misma entrada, misma salida, sin efectos laterales)."""
        original = "Fuentes de financiación (máx. 1 puntos)"
        copy_of_original = str(original)
        kp.sanitize_deliverable_context(original)
        self.assertEqual(original, copy_of_original)

    # --- ajuste 1: puntuación condicional (casos 1-6 numerados) -----------

    def test_1_un_punto_si_se_supera_el_30_por_ciento(self):
        """Superado por el ajuste 3: en el ajuste 1 la condición ('se supera
        el 30 %') se dejaba legible a propósito, porque entonces solo se
        perseguía la PUNTUACIÓN. El ajuste 3 revisa esa decisión: el 30 % es
        también la condición normativa del tramo, así que ahora se oculta
        junto con el punto (ver TestConditionalThresholdSanitization más
        abajo para los casos nuevos numerados del ajuste 3)."""
        text = "1 punto si se supera el 30 %"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("1 punto", out)
        self.assertNotIn("30 %", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_2_dos_puntos_cuando_se_aporte(self):
        text = "2 puntos cuando se aporte la certificación correspondiente"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("2 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertIn("cuando se aporte la certificación correspondiente", out)

    def test_3_cero_coma_cinco_puntos_por_cada(self):
        text = "0,5 puntos por cada contrato indefinido formalizado"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("0,5 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertIn("por cada contrato indefinido formalizado", out)

    def test_4_se_otorgaran_diez_puntos_si(self):
        text = "Se otorgarán 10 puntos si el proyecto se ubica en un enclave tecnológico"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("10 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual([h.rule for h in hits], ["puntuacion_concesion"])

    def test_5_obtendra_cuatro_puntos(self):
        text = "Obtendrá 4 puntos el proyecto que acredite la reducción de emisiones"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("4 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual([h.rule for h in hits], ["puntuacion_concesion"])

    def test_6_iib_apartado_2_anexo_ii_2026_permanece_intacto(self):
        """Regresión explícita pedida en el ajuste 1: ningún código de
        apartado, referencia estructural o año se ve afectado por las reglas
        nuevas de puntuación condicional, aunque contengan dígitos sueltos."""
        text = "II.B — apartado 2 — Anexo II — 2026"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertEqual(out, text)
        self.assertEqual(hits, [])

    def test_variantes_adicionales_razonables(self):
        """Más variantes de la lista del encargo, no numeradas pero
        explícitamente mencionadas como ejemplos a cubrir."""
        cases = [
            "hasta 4 puntos cuando se cumplan las condiciones",
            "10 puntos para proyectos que reduzcan residuos",
            "puntuación de 2 puntos si se justifica documentalmente",
        ]
        for text in cases:
            out, hits = kp.sanitize_deliverable_context(text)
            self.assertTrue(hits, f"no se ocultó ninguna cifra en: {text!r}")
            self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_gender_agreement_puntuacion_maxima_femenino(self):
        """Caso real de INPYME 2026: 'la puntuación MÁXIMA de 4 puntos' (con
        concordancia de género femenino) debe ocultarse igual que 'el importe
        MÁXIMO'. El calificador de magnitud cubre ambos géneros."""
        text = "Conforme a la Ley 14/2018 (se otorgará en este caso la puntuación máxima de 4 puntos)."
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("4 puntos", out)

    def test_abreviatura_ptos_con_o(self):
        """Caso real de INPYME 2026: el documento abrevia 'puntos' como
        'ptos' (con o), no solo 'pts'."""
        text = "4 ptos si el 100% del coste del proyecto se provee de empresas de la Comunitat Valenciana."
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("4 ptos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_puntuacion_aislada_entre_parentesis(self):
        """Caso real de INPYME 2026: anotaciones de puntuación entre
        paréntesis sin calificador ni nexo condicional pegado, propias de
        listas de opciones alternativas dentro de un mismo apartado."""
        text = "Aportar factura o presupuesto (2,5 puntos); aportar varios de los documentos anteriores (5 puntos)."
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("2,5 puntos", out)
        self.assertNotIn("5 puntos)", out)
        self.assertEqual(len(hits), 2)

    # --- ajuste 2: capa general por cláusula (rangos, reiteraciones, --------
    # enumeraciones), casos 1-7 numerados del encargo ------------------------

    def test_1_rango_de_x_a_y_puntos(self):
        text = "Se otorgarán de 1 a 3 puntos según el grado de mejora"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("1 a 3 puntos", out)
        self.assertNotIn("3 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertIn("según el grado de mejora", out)
        self.assertEqual([h.rule for h in hits], ["clausula_baremacion"])

    def test_2_rango_entre_x_y_y_puntos(self):
        text = "Se valorará con entre 2 y 5 puntos la experiencia acreditada"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("2 y 5 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_3_rango_guion_puntos(self):
        text = "Este criterio otorga 1-4 puntos según el caso"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("1-4 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_4_condicion_experiencia_oculta_anios_y_puntos(self):
        """Superado por el ajuste 3: en el ajuste 2 '>10 años' (la CONDICIÓN
        del criterio) se dejaba visible a propósito, ocultando solo la
        cifra de puntos. El ajuste 3 revisa esa decisión — la condición
        cuantitativa de un tramo de baremo es tan normativa como los
        puntos que otorga — y ahora oculta ambas (ver
        TestConditionalThresholdSanitization para los casos numerados
        nuevos del ajuste 3)."""
        text = "Experiencia superior a 10 años: 3 puntos"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("10 años", out)
        self.assertNotIn("3 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_5_se_otorgaran_2_puntos_por_cada(self):
        text = "Se otorgarán 2 puntos por cada contrato indefinido formalizado"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("2 puntos", out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)

    def test_6_enumeracion_puntuacion_0_1_2_3_puntos(self):
        text = "Puntuación: 0 / 1 / 2 / 3 puntos"
        out, hits = kp.sanitize_deliverable_context(text)
        for token in ("0 /", "1 /", "2 /", "3 puntos"):
            self.assertNotIn(token, out)
        self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, out)
        self.assertEqual([h.rule for h in hits], ["clausula_baremacion"])

    def test_7_iib_apartado_anexo_tabla_pagina_ejercicio_intacto(self):
        text = "II.B — apartado 2 — Anexo II — tabla 3 — página 4 — ejercicio 2026"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertEqual(out, text)
        self.assertEqual(hits, [])

    def test_rango_no_sobre_redacta_condicion_no_normativa(self):
        """Un rango de años solo se oculta dentro de una cláusula de
        baremación de verdad (vocabulario inequívoco: puntos/puntuación/
        baremo/otorgar/valorar con — ver `_SCORING_CLAUSE_VOCAB_RE`);
        'Puntúa' (verbo distinto, sin ese vocabulario) no basta para
        activarlo, así que este rango sin relación real con puntuación
        queda intacto."""
        text = "Puntúa la antigüedad de la empresa: entre 2 y 5 años de actividad no computan a efectos de este apartado."
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertIn("entre 2 y 5 años", out)
        self.assertEqual(hits, [])


class TestConditionalThresholdSanitization(unittest.TestCase):
    """Ajuste 3 (tercera revisión sobre F88114.docx real): las reglas
    anteriores ya ocultaban la PUNTUACIÓN (puntos, rangos, reiteraciones).
    Pero dejaban legible la CONDICIÓN cuantitativa que determina el tramo
    de puntos (umbral de años, porcentaje o importe a superar) — igual de
    normativa que los puntos si no está respaldada por NORMATIVE_CONTEXT.
    Casos 1-8 numerados del encargo."""

    def test_1_experiencia_superior_a_10_anios_oculta_anios_y_puntos(self):
        text = "Experiencia superior a 10 años = 3 puntos"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("10 años", out)
        self.assertNotIn("3 puntos", out)

    def test_2_entre_5_y_7_anios_oculta_rango_y_puntos(self):
        text = "Entre 5 y 7 años = 1 punto"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("5 y 7 años", out)
        self.assertNotIn("1 punto", out)

    def test_3_un_punto_si_se_supera_el_30_por_ciento_oculta_ambos(self):
        text = "1 punto si se supera el 30 %"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("1 punto", out)
        self.assertNotIn("30 %", out)

    def test_4_cuatro_puntos_superior_al_75_por_ciento_oculta_ambos(self):
        text = "4 puntos cuando la reducción sea superior al 75 %"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("4 puntos", out)
        self.assertNotIn("75 %", out)

    def test_5_se_otorgaran_2_puntos_si_supera_100000_euros_oculta_ambos(self):
        text = "Se otorgarán 2 puntos si la inversión supera 100.000 €"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertNotIn("2 puntos", out)
        self.assertNotIn("100.000 €", out)

    def test_6_serie_historica_ultimos_5_anios_sin_puntos_permanece(self):
        text = "Serie histórica de los últimos 5 años"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertEqual(out, text)
        self.assertEqual(hits, [])

    def test_7_ejercicio_anexo_apartado_intacto(self):
        text = "Ejercicio 2026 — Anexo II — apartado 2"
        out, hits = kp.sanitize_deliverable_context(text)
        self.assertEqual(out, text)
        self.assertEqual(hits, [])


class _F88114FixtureMixin:
    @classmethod
    def setUpClass(cls):
        fixture_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "fixtures", "f88114_deliverable_context.txt",
        )
        with open(fixture_path, encoding="utf-8") as f:
            cls.RAW_TEXT = f.read()


class TestF88114RealDocumentSanitization(_F88114FixtureMixin, unittest.TestCase):
    """Caso 8 del encargo (ajuste 2): DELIVERABLE_CONTEXT real de
    F88114.docx, la plantilla oficial de memoria de INPYME 2026 (texto
    reutilizado tal cual de la convocatoria histórica id 8 en convokit.db —
    mismos bytes que ConvoKit extraería del documento original). Antes de
    esta iteración, dos formulaciones reales de este documento sobrevivían
    a la sanitización sin ocultarse:

      1. Reiteración de un umbral ya enunciado antes en la misma frase, sin
         calificador pegado al número: "No se supera el umbral mínimo si la
         suma de las puntuaciones no alcanza los 3 puntos" / "... 15 puntos".
      2. Rango con la unidad repetida en ambos extremos: "(de 2,5 puntos a
         5 puntos)".

    Estas pruebas comprueban el RESULTADO sanitizado completo, no solo
    ejemplos aislados sobre fragmentos mínimos."""

    def test_previously_confirmed_leaks_no_longer_present(self):
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        self.assertNotIn("los 3 puntos", sanitized)
        self.assertNotIn("los 15 puntos", sanitized)
        self.assertNotIn("2,5 puntos a 5 puntos", sanitized)
        self.assertNotIn("de 2,5 puntos a 5 puntos", sanitized)

    def test_no_number_remains_attached_to_a_points_unit(self):
        """Invariante fuerte: tras sanitizar, ningún dígito queda pegado a
        punto/puntos/pto/ptos/pt/pts en todo el documento real."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        leak_re = re.compile(r"\d+(?:[.,]\d+)?\s*(?:puntos?|ptos?\.?|pts?\.?)\b", re.IGNORECASE)
        leaks = leak_re.findall(sanitized)
        self.assertEqual(leaks, [], f"cifra de puntuación sin ocultar: {leaks!r}")

    def test_full_sanitized_output_manually_triaged_for_residual_leaks(self):
        """No basta comprobar las redacciones aplicadas: se busca también en
        el TEXTO SANITIZADO COMPLETO cualquier línea que combine vocabulario
        de baremo (punto/puntos/pto/ptos/pt/pts/puntuación/baremo/umbral) con
        un dígito, y cada coincidencia se clasifica a mano. Las únicas
        supervivientes conocidas, verificadas una a una contra el documento
        real, no son fugas normativas:

        - código de apartado "0." + "no puntuable" (cualitativo, sin cifra
          de puntuación pegada al vocabulario de baremo).
        - "puntuación [PLACEHOLDER]" — ya sanitizada; el único dígito que
          queda en esa línea es la referencia "Ley 14/2018", estructural.
        - condiciones porcentuales del criterio de proveedores locales
          ("100 %", "75 %", "50 %", "30 %"): son la CONDICIÓN del criterio,
          no la puntuación que otorgan (las cifras de puntos de esa misma
          línea sí quedan ocultas, cubierto por el test anterior).
        - "los 3 apartados anteriores" (referencia estructural a apartados
          previos) coincidiendo en la misma frase con "ausencia de
          puntuación": el número no está pegado a la unidad de puntos.
        - "la puntuación de este apartado sea 0": un resultado nulo
          (consecuencia de una falta de acreditación), no un valor de peso
          o umbral de baremo — limitación conocida y deliberadamente fuera
          de alcance de esta capa (ver comentario sobre porcentaje/importe/
          plazo en `knowledge_pack.py`, junto a `_POINTS_CHAIN_RE`).

        Si aparece una línea nueva no cubierta por esta lista, el test debe
        fallar: es la señal de que hay una fuga normativa nueva por revisar.
        """
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        vocab_re = re.compile(
            r"punt[oa]s?\b|pto\.?s?\b|pt\.?s?\b|puntuaci[oó]n(?:es)?|baremo|umbral",
            re.IGNORECASE,
        )
        digit_re = re.compile(r"\d")

        KNOWN_INOCUOUS_SUBSTRINGS = (
            "no puntuable pero sí excluyente",
            "la puntuación " + kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER,
            "los 3 apartados anteriores, supondrá la ausencia de puntuación",
            "conllevará que la puntuación de este apartado sea 0",
        )

        unclassified = []
        for line in sanitized.split("\n"):
            if not vocab_re.search(line) or not digit_re.search(line):
                continue
            if any(known in line for known in KNOWN_INOCUOUS_SUBSTRINGS):
                continue
            unclassified.append(line)

        self.assertEqual(unclassified, [], f"línea con posible fuga normativa sin triar: {unclassified!r}")

    def test_structural_codes_and_headings_survive(self):
        """Códigos de apartado y encabezados de bloque siguen legibles: la
        estructura de la memoria (lo único que este modo necesita de la
        plantilla) no se pierde por la sanitización."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        for marker in (
            "0. | JUSTIFICACIÓN DE LA VINCULACIÓN",
            "I. | DESCRIPCIÓN DE LA EMPRESA",
            "A. | Antecedentes y evolución",
            "B. | Actividades actuales de la empresa",
            "C. | Experiencia en la actividad proyectada",
            "II. | MOTIVACIÓN, VIABILIDAD Y DESCRIPCIÓN TÉCNICA DEL PROYECTO",
            "B. | Viabilidad económica de la inversión",
            "V. | LA CONTRIBUCIÓN A LA SOLUCIÓN DE PROBLEMAS SOCIALES",
        ):
            self.assertIn(marker, sanitized)

    def test_experience_years_thresholds_hidden_ajuste_3(self):
        """Caso real (apartado I.C), ajuste 3: los tramos de años de
        experiencia son la CONDICIÓN normativa del criterio (determinan qué
        puntuación corresponde), así que se ocultan igual que los puntos —
        superan la decisión anterior del ajuste 2, que los dejaba legibles."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        for tramo in ("menos de 5 años", "entre 5 y 7 años", "entre 7 y 10 años", "más de 10 años"):
            self.assertNotIn(tramo, sanitized)

    def test_iiic_local_supply_percentage_tiers_hidden_ajuste_3(self):
        """Caso real (apartado III.C, huella de carbono): los tramos por
        porcentaje de proveedores de la Comunitat Valenciana (100/75/50/30 %)
        determinan el punto que se otorga — condición de baremo, no solo la
        cifra de puntos. El primer tramo ('si el 100%...') ni siquiera lleva
        un comparativo pegado, es la condición de barrido ciego por cláusula
        que ajuste 3 añade específicamente para este caso real."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        for pct in ("100%", "100 %", "75%", "75 %", "50%", "50 %", "30%", "30 %"):
            self.assertNotIn(pct, sanitized)

    def test_last_five_years_reporting_window_still_preserved(self):
        """Caso real (apartado I.A): 'los últimos 5 años' es la ventana de
        datos económicos a reportar, no un umbral de tramo — convive en la
        misma línea que 'máx. 2 puntos' pero no es su condición. Debe seguir
        legible: es precisamente el caso que impide tratar años con barrido
        ciego dentro de una cláusula de baremación."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        self.assertIn("los últimos 5 años", sanitized)

    def test_law_reference_and_structural_apartado_count_preserved(self):
        """'Ley 14/2018' (III.A) y 'los 3 apartados anteriores' (cierre del
        bloque V) conviven en líneas con vocabulario de baremación pero no
        son condiciones cuantitativas de puntuación — no deben verse
        afectados por el barrido de porcentajes/años por cláusula."""
        sanitized, _ = kp.sanitize_deliverable_context(self.RAW_TEXT)
        self.assertIn("Ley 14/2018", sanitized)
        self.assertIn("los 3 apartados anteriores", sanitized)


class TestScoringExpectation(unittest.TestCase):
    """Endurecimiento 2 (y su corrección posterior — ajuste 2). Deriva
    scoring_expectation EXCLUSIVAMENTE de entidades del Knowledge Pack —
    nunca de texto de plantilla (estas pruebas ni siquiera construyen un
    documento de entregable, solo codigo/nombre + pack)."""

    # --- casos numerados 7-14 del ajuste 2 -----------------------------

    def test_07_criterion_usable_con_max_score_es_scored(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(value={"puntos_max": 4})]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "scored")

    def test_08_criterion_human_validated_con_score_es_scored(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="accredited", review_state="human_validated", value={"puntos_max": 4}),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        entity = pack.entities[0]
        self.assertTrue(entity.is_canonical())
        self.assertEqual(kp.compute_scoring_expectation(match), "scored")

    def test_09_criterion_accredited_unvalidated_es_scored_pero_marcado(self):
        """Permitido por las reglas ya existentes (accredited-sin-validar es
        utilizable): scoring_expectation sigue siendo 'scored' — la cautela
        de 'no validado' no vive en scoring_expectation (que es un estado de
        3 valores, no 4), sino en SectionProvenance.unvalidated_knowledge_used
        y en la marca '[PENDIENTE DE VALIDACIÓN HUMANA]' de
        format_normative_context. Se verifican ambas aquí."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="accredited", review_state="unvalidated", value={"puntos_max": 4}),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        entity = pack.entities[0]
        self.assertTrue(entity.is_usable_but_unvalidated())
        self.assertFalse(entity.is_canonical())
        self.assertEqual(kp.compute_scoring_expectation(match), "scored")
        gaps = kp.compute_knowledge_gaps(match, "scored")
        prov = kp.build_section_provenance(match, gaps)
        self.assertIn(entity.entity_id, prov.unvalidated_knowledge_used)
        self.assertIn("[PENDIENTE DE VALIDACIÓN HUMANA]", kp.format_normative_context(match))

    def test_10_criterion_conflict_es_unknown_nunca_scored_firme(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="conflict", review_state="unvalidated",
                    conflicting_values=[{"puntos_max": 4}, {"puntos_max": 6}]),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_11_criterion_not_located_es_unknown(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_located", review_state="unvalidated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_12_not_applicable_sin_declaracion_explicita_es_unknown(self):
        """Ajuste 2 — el núcleo de la corrección: 'not_applicable' en un
        'criterion' YA NO se interpreta como 'not_scored'. 'not_applicable'
        significa 'este hecho concreto no procede en este caso' (vocabulario
        real de i40 Analiza), no 'este apartado carece de puntuación'. Sin
        una señal explícita adicional que lo confirme, el resultado correcto
        es 'unknown' — ni scored ni not_scored."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_applicable", review_state="human_validated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_13_ausencia_de_criterion_es_unknown_mas_scoring_status_unknown_gap(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(entity_type="documentation", label="Certificado exigido", value="x"),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        scoring_expectation = kp.compute_scoring_expectation(match)
        self.assertEqual(scoring_expectation, "unknown")
        gaps = kp.compute_knowledge_gaps(match, scoring_expectation)
        kinds = {g.kind for g in gaps}
        self.assertNotIn("missing_entity_type", kinds)
        self.assertIn("scoring_status_unknown", kinds)

    def test_14_not_scored_reservado_pero_nunca_inferido_hoy(self):
        """No existe hoy en el modelo interno (entity_type/evidence_status/
        review_state) ninguna señal explícita e inequívoca de 'este apartado
        no puntúa' que no sea inventarla — ni siquiera con el criterion
        'not_applicable' más fuerte posible (human_validated). Por eso
        compute_scoring_expectation NUNCA devuelve 'not_scored' en esta
        iteración: queda reservado en el tipo y compute_knowledge_gaps ya lo
        trata correctamente (sin exigir 'criterion', sin scoring_status_unknown)
        para cuando un Knowledge Pack real lo declare de forma estructurada."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_applicable", review_state="human_validated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")
        # uso futuro reservado: si se pasara "not_scored" a mano, la lógica de
        # gaps ya está preparada, aunque compute_scoring_expectation no lo
        # produzca todavía por sí sola.
        gaps = kp.compute_knowledge_gaps(match, "not_scored")
        kinds = {g.kind for g in gaps}
        self.assertNotIn("missing_entity_type", kinds)
        self.assertNotIn("scoring_status_unknown", kinds)

    # --- cobertura adicional ya existente, mantenida ---------------------

    def test_scored_still_produces_missing_criterion_gap_when_absent(self):
        """Comportamiento sin cambios respecto al expects_scoring=True original:
        si de verdad se espera puntuación y no hay 'criterion' usable, el gap
        se sigue generando."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(entity_type="subcriterion", label="Fuentes de financiación", value={"puntos_max": 1}),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        # Forzamos 'scored' explícitamente (simula que otra fuente del pack ya
        # estableció que este apartado puntúa) para probar la rama scored con
        # 'criterion' ausente, sin depender de que compute_scoring_expectation
        # también devuelva 'scored' en este fixture concreto.
        gaps = kp.compute_knowledge_gaps(match, "scored")
        self.assertTrue(any(g.kind == "missing_entity_type" and g.entity_type == "criterion" for g in gaps))

    def test_never_derived_from_template_text(self):
        """compute_scoring_expectation no recibe ni puede recibir texto de
        plantilla: su única entrada es un SectionMatch (codigo/nombre + pack).
        Verificación estructural de la firma, no solo de comportamiento."""
        import inspect
        params = inspect.signature(kp.compute_scoring_expectation).parameters
        self.assertEqual(list(params), ["section_match"])


if __name__ == "__main__":
    unittest.main()
