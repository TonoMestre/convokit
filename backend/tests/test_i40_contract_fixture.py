# -*- coding: utf-8 -*-
"""
Drift protection against i40 Analiza's Knowledge Pack adapter (KP-2 gap 1,
encargo 2026-08-29 "cross-repo drift protection"). Sin red: no checkout de
i40 Analiza, sin base de datos, sin llamadas a Claude.

fixtures/i40-convokit-pack-output.v1.json is a FROZEN, byte-identical copy
of the output i40's own `to_convokit_pack()` adapter produces for its own
checked-in source fixture (i40 repo:
contracts/fixtures/i40-convokit-pack-{source,output}.v1.json, regenerated
via services/worker/scripts/regenerate_convokit_contract_fixture.py). i40's
OWN test suite (test_convokit_pack_output_matches_frozen_contract_fixture,
tests/unit/test_application_knowledge.py) fails its CI the moment
to_convokit_pack's output stops matching this exact file -- that is what
catches drift FROM i40's side. This file is the other half: it fails
ConvoKit's OWN CI the moment THIS parser stops accepting that exact,
already-proven-real i40 output shape -- catching drift FROM ConvoKit's
side. Neither repo needs the other checked out at test time; the shared
frozen fixture file is the only synchronization point, kept in lockstep by
review (a PR that regenerates the i40 fixture should copy the new file here
in the same review, and vice versa).

Ejecutar: python -m unittest backend.tests.test_i40_contract_fixture -v
(desde la raíz del repo, o `python -m unittest discover -s backend/tests`)
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import knowledge_pack as kp

_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "i40-convokit-pack-output.v1.json")


def _load_fixture() -> dict:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class TestI40ContractFixture(unittest.TestCase):
    def test_fixture_file_exists_and_is_valid_json(self):
        pack = _load_fixture()
        self.assertIsInstance(pack, dict)
        self.assertIn("entities", pack)

    def test_real_parser_accepts_the_frozen_i40_output(self):
        pack = _load_fixture()
        parsed = kp.parse_knowledge_pack(pack)
        # 3 application_knowledge entities (block score, block threshold,
        # criterion) + 3 mapped facts (importe_maximo/value, gastos_
        # subvencionables/value, periodo_elegible_fin/single-row conflict)
        # + 1 mapped ambiguous fact (compatibilidad, KP-2 gap 2 -- two
        # competing candidates via conflicting_values) = 7. If i40 ever adds/
        # removes a fixture entity without updating this count, that is
        # exactly the drift this test exists to surface -- update BOTH this
        # assertion and the fixture file together, never one without the other.
        self.assertEqual(len(parsed.entities), 7)

    def test_readiness_is_draft_because_facts_are_not_fully_reviewed(self):
        """The fixture deliberately includes an unreviewed fact
        (gastos_subvencionables, review_state='unvalidated') -- i40's own
        blocking-gap invariant (an i40 blocking gap forces every entity
        unvalidated) is exercised separately in i40's own test suite; this
        fixture instead proves the SIMPLER case: ConvoKit's own whole-pack
        readiness already goes to 'draft' the moment even one entity isn't
        human_validated, with no i40-side signal needed."""
        parsed = kp.parse_knowledge_pack(_load_fixture())
        self.assertEqual(kp.compute_pack_readiness(parsed), "draft")

    def test_fact_entities_present_with_expected_types(self):
        parsed = kp.parse_knowledge_pack(_load_fixture())
        by_id = {e.entity_id: e for e in parsed.entities}

        self.assertIn("fact.importe_maximo", by_id)
        self.assertEqual(by_id["fact.importe_maximo"].entity_type, "limit")
        self.assertEqual(by_id["fact.importe_maximo"].review_state, "human_validated")

        self.assertIn("fact.gastos_subvencionables", by_id)
        self.assertEqual(by_id["fact.gastos_subvencionables"].entity_type, "cost_rule")
        self.assertEqual(by_id["fact.gastos_subvencionables"].review_state, "unvalidated")

    def test_single_row_conflict_fact_carries_real_conflicting_values(self):
        """periodo_elegible_fin: a single ScopedFact whose own extraction saw
        disagreeing source passages (i40's public.conflicts table) -- distinct
        from the multi-candidate ambiguous case below, same ConvoKit channel."""
        parsed = kp.parse_knowledge_pack(_load_fixture())
        entity = next(e for e in parsed.entities if e.entity_id == "fact.periodo_elegible_fin")
        self.assertTrue(entity.is_conflict())
        self.assertEqual(entity.conflicting_values, ("2026-11-04", "2026-12-31"))
        self.assertEqual(entity.review_state, "unvalidated")

    def test_ambiguous_fact_preserves_both_competing_candidates(self):
        """compatibilidad: KP-2 gap 2 -- i40's own resolve_general_fact found
        TWO competing general facts and (as of this fixture) carries both
        through as conflicting_values, reusing this exact ConvoKit channel.
        Both candidates must stay identifiable with their own evidence, and
        must never be mistaken for a reviewed value."""
        parsed = kp.parse_knowledge_pack(_load_fixture())
        entity = next(e for e in parsed.entities if e.entity_id == "fact.compatibilidad")

        self.assertTrue(entity.is_conflict())
        self.assertEqual(
            entity.conflicting_values,
            (
                "Compatible con otras ayudas para costes distintos",
                "Incompatible con cualquier otra ayuda para el mismo proyecto",
            ),
        )
        self.assertEqual(len(entity.evidence_refs), 2)
        documents = {r.document_id for r in entity.evidence_refs}
        self.assertEqual(documents, {"convocatoria-fixture.pdf", "guia-fixture.pdf"})

        # never mistakable for a reviewed value
        self.assertEqual(entity.review_state, "unvalidated")
        self.assertFalse(entity.is_canonical())
        self.assertFalse(entity.is_usable_but_unvalidated())

    def test_not_available_and_pure_ambiguous_note_never_leak_as_entities(self):
        """intensidad (not_available) never appears at all -- the i40 fixture
        also doesn't include a bare ambiguous-without-candidates fact (that
        remaining CONTRACT_MISMATCH case is exercised in i40's own test
        suite, not here, since it never produces an entity to assert on)."""
        parsed = kp.parse_knowledge_pack(_load_fixture())
        entity_ids = {e.entity_id for e in parsed.entities}
        self.assertNotIn("fact.intensidad", entity_ids)


if __name__ == "__main__":
    unittest.main()
