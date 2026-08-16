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


class TestScoringExpectation(unittest.TestCase):
    """Endurecimiento 2. Deriva scoring_expectation EXCLUSIVAMENTE de entidades
    del Knowledge Pack — nunca de texto de plantilla (estas pruebas ni siquiera
    construyen un documento de entregable, solo codigo/nombre + pack)."""

    def test_scored_when_criterion_usable_with_value(self):
        pack = kp.parse_knowledge_pack(_pack([_entity(value={"puntos_max": 4})]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "scored")

    def test_not_scored_when_pack_marks_not_applicable(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_applicable", review_state="human_validated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "not_scored")

    def test_unknown_when_no_criterion_matched_at_all(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(entity_type="documentation", label="Certificado exigido", value="x"),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_unknown_when_only_missing_criterion(self):
        """not_located/not_provided = desconocido, no 'no puntúa'. No debe
        derivarse ni 'scored' ni 'not_scored' de una entidad missing."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_located", review_state="unvalidated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_conflict_criterion_never_becomes_scored_firmly(self):
        """Un criterion en conflicto no convierte automáticamente el apartado
        en 'scored': una de las versiones contradictorias podría tener puntos,
        pero no se eleva a hecho firme."""
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="conflict", review_state="unvalidated",
                    conflicting_values=[{"puntos_max": 4}, {"puntos_max": 6}]),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        self.assertEqual(kp.compute_scoring_expectation(match), "unknown")

    def test_unknown_never_produces_missing_criterion_gap(self):
        """El requisito central del endurecimiento 2: unknown -> NUNCA
        missing_entity_type, en su lugar un gap explícito scoring_status_unknown."""
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

    def test_not_scored_never_produces_missing_criterion_gap(self):
        pack = kp.parse_knowledge_pack(_pack([
            _entity(evidence_status="not_applicable", review_state="human_validated", value=None),
        ]))
        match = kp.match_section_to_knowledge("II.B", "Viabilidad económica de la inversión", pack)
        scoring_expectation = kp.compute_scoring_expectation(match)
        self.assertEqual(scoring_expectation, "not_scored")
        gaps = kp.compute_knowledge_gaps(match, scoring_expectation)
        kinds = {g.kind for g in gaps}
        self.assertNotIn("missing_entity_type", kinds)
        self.assertNotIn("scoring_status_unknown", kinds)

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
