# -*- coding: utf-8 -*-
"""
Tests de integración del modo i40 Knowledge Pack sobre main._generate_output_4_kp,
completamente offline: monkeypatchea main._claude con respuestas fijas (nunca sale
a la red). Cubren específicamente lo que la unidad pura de knowledge_pack.py no
puede probar por sí sola: que el pipeline completo produce un objeto v2.5 real,
que ese objeto pasa por exporters.export_output_4 sin tocarlo, y que el modo
tradicional (_generate_output_4) sigue funcionando exactamente igual.

Ejecutar: python -m unittest backend.tests.test_knowledge_pack_e2e -v
"""
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_PASSWORD", "")  # no exigir login al importar main

import main
import exporters
import knowledge_pack as kp


_FAKE_KP = {
    "pack_id": "kp-fake-1",
    "convocatoria_ref": "FAKE-2026",
    "convocatoria_metadata": {"anio": 2026, "organismo": "Organismo Falso", "tipo_ayuda": "otro"},
    "entities": [
        {
            "entity_id": "iia-criterion", "entity_type": "criterion", "section_ref": "II.A Apartado con datos",
            "label": "Puntuación de II.A", "value": {"puntos_max": 5},
            "evidence_status": "accredited", "review_state": "human_validated",
            "evidence_refs": [{"document_id": "doc-1", "quote": "II.A vale 5 puntos", "section": "Anexo"}],
        },
        {
            "entity_id": "iib-criterion", "entity_type": "criterion", "section_ref": "II.B Apartado con hueco",
            "label": "Puntuación de II.B", "value": {"puntos_max": 3},
            "evidence_status": "accredited", "review_state": "human_validated",
            "evidence_refs": [{"document_id": "doc-1", "quote": "II.B vale 3 puntos", "section": "Anexo"}],
        },
        {
            "entity_id": "iib-sub-secreta", "entity_type": "subcriterion", "section_ref": "II.B Apartado con hueco",
            "label": "Subcriterio nunca localizado", "value": None,
            "evidence_status": "not_located", "review_state": "unvalidated", "evidence_refs": [],
        },
    ],
}


def _fake_claude_dispatcher(captured_calls):
    """Devuelve un doble de main._claude que enruta por el system prompt recibido,
    registrando cada llamada en captured_calls para poder inspeccionar qué vio el
    modelo (aserciones de 'nunca se envía normativa no usable')."""

    def fake(client, system, user, max_tokens=2000, model=None, _track=None):
        captured_calls.append({"system": system, "user": user})

        if system == main.p.SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP:
            return json.dumps({"secciones": [
                {"codigo": "II.A", "nombre": "Apartado con datos"},
                {"codigo": "II.B", "nombre": "Apartado con hueco"},
            ]})

        if system == main.p.SECTION_PROMPT_SYSTEM_KP:
            codigo = "II.A" if "Apartado: II.A" in user else "II.B"
            return (
                f"### Sección {codigo}: Apartado ({'5' if codigo == 'II.A' else '3'} puntos)\n\n"
                "**Requiere cálculo de rentabilidad:** No\n"
                "**Usa tabla de inversiones:** No\n\n"
                "**QUÉ BUSCA EL EVALUADOR**\nCriterio de prueba.\n\n"
                "**QUÉ DEBES APORTAR ANTES DE GENERAR**\n\n"
                "*Específico de este proyecto — imprescindible para redactar el apartado:*\n"
                "- Dato de prueba para el apartado\n\n"
                "**INSTRUCCIÓN A CLAUDE**\n```\nRedacta el apartado de prueba.\n```"
            )

        if system == main.p.OUTPUT_4_JSON_EXTRACTOR:
            is_iia = "5 puntos" in user
            return json.dumps({
                "codigo": "II.A" if is_iia else "II.B",
                "nombre": "Apartado con datos" if is_iia else "Apartado con hueco",
                "puntos_max": 5 if is_iia else 3,
                "contexto_evaluador": "Criterio de prueba.",
                "requiere_calculo_rentabilidad": False,
                "usa_tabla_inversiones": False,
                "inputs": [{"id": "dato-x", "label": "Dato de prueba para el apartado", "tipo": "texto_libre", "nivel": "minimo"}],
                "documentos_requeridos": [],
                "prompt": "Redacta el apartado de prueba.",
            })

        if system == main.p.OUTPUT_4_CAMPOS_EMPRESA_CONSOLIDATOR:
            return json.dumps({"campos_empresa": [], "remapeo": []})

        if system == main.p.OUTPUT_4_CAMPOS_PROYECTO_CONSOLIDATOR:
            return json.dumps({"campos_proyecto": [], "remapeo_inputs": [], "remapeo_datos_aplicativo": [], "duplicados_datos_aplicativo": []})

        raise AssertionError(f"system prompt inesperado en el test: {system[:60]}...")

    return fake


class TestKnowledgePackPipelineOffline(unittest.TestCase):
    def test_prohibited_normative_documents_rejected_before_any_call(self):
        """Cargar 'convocatoria'/'bases_reguladoras'/'guia_convocante' en modo KP
        debe fallar ANTES de llamar a Claude ni una sola vez (regla del punto 4:
        'en este modo esos documentos ni siquiera deberían cargarse')."""
        calls = []
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)):
            with self.assertRaises(main.HTTPException) as ctx:
                main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=[
                        {"etiqueta": "plantilla_memoria", "texto": "x", "nombre_archivo": "a.docx"},
                        {"etiqueta": "convocatoria", "texto": "y", "nombre_archivo": "b.pdf"},
                    ],
                    knowledge_pack_raw=_FAKE_KP,
                )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(calls, [])

    def test_full_pipeline_produces_valid_v25_object(self):
        calls = []
        deliverable_docs = [
            {"etiqueta": "plantilla_memoria", "texto": "II.A y II.B, sin puntos aquí.", "nombre_archivo": "plantilla.docx"},
        ]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)):
            with mock.patch("time.sleep"):
                markdown, root, audit = main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs,
                    knowledge_pack_raw=_FAKE_KP,
                )

        # --- forma del objeto v2.5 ---
        self.assertEqual(root["version_esquema"], "2.5")
        self.assertEqual(root["convocatoria"]["nombre"], "FAKE 2026")
        self.assertEqual(root["convocatoria"]["anio"], 2026)
        self.assertEqual(root["convocatoria"]["organismo"], "Organismo Falso")
        codigos = {a["codigo"] for a in root["apartados"]}
        self.assertEqual(codigos, {"II.A", "II.B"})

        # --- pasa por el exportador v2.5 SIN modificarlo ---
        exported = exporters.export_output_4(json.dumps(root, ensure_ascii=False))
        self.assertEqual(exported["version_esquema"], "2.5")
        self.assertEqual(len(exported["apartados"]), 2)
        self.assertEqual(exported["convocatoria"]["nombre"], "FAKE 2026")

        # --- auditoría interna: el hueco de II.B (subcriterio not_located) aparece ---
        gap_codes = {g.get("entity_id") for g in audit["knowledge_gaps"]}
        self.assertIn("iib-sub-secreta", gap_codes)

        # --- el contenido not_located nunca llegó al modelo como hecho ---
        iib_calls = [c for c in calls if "Apartado: II.B" in c["user"]]
        self.assertTrue(iib_calls)
        for c in iib_calls:
            self.assertNotIn("Subcriterio nunca localizado", c["user"])

    def test_traditional_mode_still_works_unchanged(self):
        """El pipeline documental tradicional (_generate_output_4) no depende de
        knowledge_pack.py y sigue produciendo v2.5 exactamente igual que antes."""
        calls = []

        def fake_traditional(client, system, user, max_tokens=2000, model=None, _track=None):
            calls.append(system)
            if system == main.p.SECTION_EXTRACTOR_PROMPT:
                return json.dumps({
                    "convocatoria": {"nombre": "TRAD 2026", "anio": 2026, "organismo": "Org", "tipo_ayuda": "otro"},
                    "secciones": [{"codigo": "I", "nombre": "Único apartado", "puntos_max": 10, "es_habilitante": False}],
                })
            if system == main.p.SECTION_PROMPT_SYSTEM:
                return (
                    "### Sección I: Único apartado (10 puntos)\n\n"
                    "**Requiere cálculo de rentabilidad:** No\n**Usa tabla de inversiones:** No\n\n"
                    "**QUÉ BUSCA EL EVALUADOR**\nCriterio.\n\n**QUÉ DEBES APORTAR ANTES DE GENERAR**\n\n"
                    "**INSTRUCCIÓN A CLAUDE**\n```\nRedacta.\n```"
                )
            if system == main.p.OUTPUT_4_JSON_EXTRACTOR:
                return json.dumps({
                    "codigo": "I", "nombre": "Único apartado", "puntos_max": 10,
                    "requiere_calculo_rentabilidad": False, "usa_tabla_inversiones": False,
                    "inputs": [], "documentos_requeridos": [], "prompt": "Redacta.",
                })
            if system == main.p.OUTPUT_4_CAMPOS_EMPRESA_CONSOLIDATOR:
                return json.dumps({"campos_empresa": [], "remapeo": []})
            if system == main.p.OUTPUT_4_FICHA_EXTRACTOR:
                return json.dumps({
                    "parametros_convocatoria": [], "tres_ofertas": {"umbral": None, "exencion_gasto_antes_resolucion": False, "condiciones_exencion": ""},
                    "datos_aplicativo": [], "documentos_convocatoria": [],
                })
            if system == main.p.OUTPUT_4_CAMPOS_PROYECTO_CONSOLIDATOR:
                return json.dumps({"campos_proyecto": [], "remapeo_inputs": [], "remapeo_datos_aplicativo": [], "duplicados_datos_aplicativo": []})
            raise AssertionError(f"unexpected system in traditional test: {system[:50]}")

        with mock.patch.object(main, "_claude", side_effect=fake_traditional):
            with mock.patch("time.sleep"):
                markdown, root = main._generate_output_4(
                    client=None, conv_name="TRAD 2026",
                    documents_json=[{"etiqueta": "plantilla_memoria", "texto": "algo", "nombre_archivo": "p.docx"}],
                )
        self.assertEqual(root["version_esquema"], "2.5")
        self.assertEqual(root["apartados"][0]["codigo"], "I")
        # knowledge_pack nunca se invoca en la ruta tradicional
        self.assertNotIn(main.p.SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP, calls)
        self.assertNotIn(main.p.SECTION_PROMPT_SYSTEM_KP, calls)


class TestMemorAICompatibility(unittest.TestCase):
    """Punto 10 del encargo: el JSON generado en modo KP debe pasar convokit_validator
    de MemorAI (_upload_v2) sin ningún cambio en su código. Se salta si el repo de
    MemorAI no está disponible en esta máquina (no es una dependencia de ConvoKit)."""

    def test_generated_v25_object_passes_memorai_validator(self):
        memorai_backend = r"C:\Dev\MEMORAI\backend"
        if not os.path.isdir(memorai_backend):
            self.skipTest("MemorAI no está presente en esta máquina; test opcional.")

        sys.path.insert(0, memorai_backend)
        from app.services import convokit_validator  # import de solo lectura, sin tocar el repo

        calls = []
        deliverable_docs = [{"etiqueta": "plantilla_memoria", "texto": "II.A y II.B.", "nombre_archivo": "plantilla.docx"}]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)):
            with mock.patch("time.sleep"):
                _, root, _ = main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs, knowledge_pack_raw=_FAKE_KP,
                )

        self.assertTrue(convokit_validator.es_json_v2(root))
        errores = convokit_validator.validar(root)
        self.assertEqual(errores, [], f"convokit_validator.validar encontró errores: {errores}")


if __name__ == "__main__":
    unittest.main()
