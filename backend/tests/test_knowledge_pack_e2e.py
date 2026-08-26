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
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used-network-is-mocked")

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

    def test_deliverable_context_value_absent_from_normative_context_never_reaches_model(self):
        """Caso G del encargo de endurecimiento: un valor visible en la plantilla
        (deliverable) pero ausente del Knowledge Pack no debe llegar al modelo NI
        SIQUIERA con salvedad. Fixture deliberado: II.B en NORMATIVE_CONTEXT solo
        trae 3 puntos (nunca 1), y el deliverable de la plantilla SÍ contiene un
        subcriterio de pay-back a "(máx. 1 punto)" que el pack no cubre — el mismo
        patrón real detectado en la ejecución de INPYME 2026. Con la sanitización
        determinista (endurecimiento 1), esa cifra debe desaparecer del mensaje
        antes de construirse, sin depender de que el modelo respete la instrucción."""
        calls = []
        deliverable_docs = [{
            "etiqueta": "plantilla_memoria",
            "texto": (
                "II.B Viabilidad económica de la inversión\n"
                "Periodo de recuperación de la inversión (pay-back) y método para su "
                "obtención (máx. 1 punto)"
            ),
            "nombre_archivo": "plantilla.docx",
        }]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)):
            with mock.patch("time.sleep"):
                _, root, audit = main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs, knowledge_pack_raw=_FAKE_KP,
                )

        iib_calls = [c for c in calls if "Apartado: II.B" in c["user"] and c["system"] == main.p.SECTION_PROMPT_SYSTEM_KP]
        self.assertTrue(iib_calls)
        for c in iib_calls:
            # ni la cifra cruda ni la unidad quedan en el mensaje enviado al modelo
            self.assertNotIn("1 punto", c["user"])
            self.assertNotIn("máx. 1", c["user"])
            self.assertIn(kp.NORMATIVE_VALUE_OMITTED_PLACEHOLDER, c["user"])

        # auditoría interna: la sanitización queda registrada, sin enviarse a MemorAI
        sanitization = audit["sections"]["II.B"]["deliverable_sanitization"]
        self.assertTrue(any("1 punto" in h["original"] or "1  punto" in h["original"] for h in sanitization) or
                         any("punto" in h["original"].lower() for h in sanitization))
        exported = exporters.export_output_4(json.dumps(root, ensure_ascii=False))
        self.assertNotIn("deliverable_sanitization", json.dumps(exported, ensure_ascii=False))

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


# ---------------------------------------------------------------------------
# Fases 2/3/4/5 del encargo de formalización (i40 Knowledge Pack mode como
# vía oficial): red de seguridad determinista sobre scoring_expectation,
# identidad/readiness en la auditoría, y el entrypoint oficial async.
# ---------------------------------------------------------------------------

_FAKE_KP_WITH_EXCLUSION = {
    "pack_id": "kp-fake-excl",
    "convocatoria_ref": "FAKE-2026",
    "convocatoria_metadata": {"anio": 2026, "organismo": "Organismo Falso", "tipo_ayuda": "otro"},
    "entities": [
        {
            "entity_id": "apartado-0-exclusion", "entity_type": "exclusion", "section_ref": "0 Vinculación",
            "label": "Vinculación con el sector",
            "value": {"scoring_status": "not_scored", "is_exclusionary": True, "requirement_text": "Debe justificarse."},
            "evidence_status": "accredited", "review_state": "human_validated", "evidence_refs": [],
        },
    ],
}


def _fake_claude_dispatcher_hallucinates_score_for_apartado_0(captured_calls):
    """Como _fake_claude_dispatcher, pero simula un extractor JSON que 'alucina'
    una puntuación para un apartado que el Knowledge Pack ya declara not_scored
    — exactamente el escenario que la red de seguridad determinista de
    main._generate_output_4_kp debe corregir, sin depender de que el modelo
    real respete la instrucción SCORING_EXPECTATION del prompt."""

    def fake(client, system, user, max_tokens=2000, model=None, _track=None):
        captured_calls.append({"system": system, "user": user})

        if system == main.p.SECTION_STRUCTURE_EXTRACTOR_PROMPT_KP:
            return json.dumps({"secciones": [{"codigo": "0", "nombre": "Vinculación"}]})

        if system == main.p.SECTION_PROMPT_SYSTEM_KP:
            return (
                "### Sección 0: Vinculación ([criterio excluyente])\n\n"
                "**Requiere cálculo de rentabilidad:** No\n**Usa tabla de inversiones:** No\n\n"
                "**QUÉ BUSCA EL EVALUADOR**\nCriterio excluyente, no puntuable.\n\n"
                "**QUÉ DEBES APORTAR ANTES DE GENERAR**\n\n"
                "**INSTRUCCIÓN A CLAUDE**\n```\nRedacta el apartado excluyente.\n```"
            )

        if system == main.p.OUTPUT_4_JSON_EXTRACTOR:
            # Deliberadamente incorrecto: un extractor real nunca debería hacer
            # esto, pero el código no puede depender de que nunca ocurra.
            return json.dumps({
                "codigo": "0", "nombre": "Vinculación", "puntos_max": 5,
                "contexto_evaluador": "Criterio excluyente, no puntuable.",
                "requiere_calculo_rentabilidad": False, "usa_tabla_inversiones": False,
                "inputs": [], "documentos_requeridos": [], "prompt": "Redacta el apartado excluyente.",
            })

        if system == main.p.OUTPUT_4_CAMPOS_EMPRESA_CONSOLIDATOR:
            return json.dumps({"campos_empresa": [], "remapeo": []})

        if system == main.p.OUTPUT_4_CAMPOS_PROYECTO_CONSOLIDATOR:
            return json.dumps({"campos_proyecto": [], "remapeo_inputs": [], "remapeo_datos_aplicativo": [], "duplicados_datos_aplicativo": []})

        raise AssertionError(f"system prompt inesperado en el test: {system[:60]}...")

    return fake


class TestScoringExpectationEnforcement(unittest.TestCase):
    """Fase 2 — formaliza en código (no solo en el prompt) que el Knowledge
    Pack manda: un apartado que declara scoring_status='not_scored' nunca
    termina con puntos_max distinto de None, pase lo que pase en la respuesta
    del modelo o del extractor JSON."""

    def test_not_scored_section_forces_puntos_max_null_even_if_extractor_hallucinates_points(self):
        calls = []
        deliverable_docs = [{"etiqueta": "plantilla_memoria", "texto": "Apartado 0, excluyente.", "nombre_archivo": "p.docx"}]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher_hallucinates_score_for_apartado_0(calls)):
            with mock.patch("time.sleep"):
                _, root, audit = main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs, knowledge_pack_raw=_FAKE_KP_WITH_EXCLUSION,
                )
        apartado_0 = next(a for a in root["apartados"] if a["codigo"] == "0")
        self.assertIsNone(apartado_0["puntos_max"])
        self.assertEqual(audit["sections"]["0"]["puntos_max_forced_null"], 5)

    def test_scoring_expectation_line_present_in_prompt_sent_to_model(self):
        calls = []
        deliverable_docs = [{"etiqueta": "plantilla_memoria", "texto": "Apartado 0.", "nombre_archivo": "p.docx"}]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher_hallucinates_score_for_apartado_0(calls)):
            with mock.patch("time.sleep"):
                main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs, knowledge_pack_raw=_FAKE_KP_WITH_EXCLUSION,
                )
        section_calls = [c for c in calls if c["system"] == main.p.SECTION_PROMPT_SYSTEM_KP]
        self.assertTrue(section_calls)
        self.assertIn("SCORING_EXPECTATION: not_scored", section_calls[0]["user"])


class TestPackIdentityAndReadinessInAudit(unittest.TestCase):
    """Fases 3/5 — la auditoría interna (nunca enviada a MemorAI) lleva la
    identidad determinista del pack y su readiness; el .md de trabajo humano
    lleva un aviso visible cuando el pack es draft."""

    def test_audit_carries_pack_identity_and_readiness_and_markdown_warns_when_draft(self):
        calls = []
        deliverable_docs = [{"etiqueta": "plantilla_memoria", "texto": "II.A y II.B.", "nombre_archivo": "p.docx"}]
        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)):
            with mock.patch("time.sleep"):
                markdown, root, audit = main._generate_output_4_kp(
                    client=None, conv_name="FAKE 2026",
                    deliverable_documents_json=deliverable_docs, knowledge_pack_raw=_FAKE_KP,
                )

        identity = audit["pack_identity"]
        self.assertEqual(identity["pack_id"], "kp-fake-1")
        self.assertEqual(identity["schema_version"], "0.1-synthetic")
        self.assertEqual(len(identity["pack_hash"]), 64)
        # _FAKE_KP tiene una entidad 'unvalidated' (iib-sub-secreta) -> draft
        self.assertEqual(identity["readiness"], "draft")
        self.assertIn("draft", markdown.lower())

        # nunca se envía a MemorAI: exportar no debe arrastrar pack_identity
        exported = exporters.export_output_4(json.dumps(root, ensure_ascii=False))
        self.assertNotIn("pack_identity", json.dumps(exported, ensure_ascii=False))


class TestOfficialAsyncEntrypoint(unittest.TestCase):
    """Fase 4 — entrypoint oficial: main._run_kp_generation_job es exactamente
    el código que ejecuta POST /convocatorias/{id}/generate/kp/async en un
    hilo de fondo (mismo patrón que _process_job para el modo documental).
    Se prueba llamándolo directamente, sin threading real ni sqlite real:
    se monkeypatchea el módulo main.db completo."""

    def test_job_completes_and_persists_entregables_with_pack_identity(self):
        calls = []
        fake_conv = {
            "nombre": "FAKE 2026",
            "documentos_json": [{"etiqueta": "plantilla_memoria", "texto": "II.A y II.B.", "nombre_archivo": "p.docx"}],
            "entregables_json": {main._KP_ENTREGABLE_KEY: json.dumps(_FAKE_KP)},
        }
        job_updates = []
        entregables_saved = {}

        with mock.patch.object(main, "_claude", side_effect=_fake_claude_dispatcher(calls)), \
             mock.patch.object(main.db, "get_convocatoria", return_value=fake_conv), \
             mock.patch.object(main.db, "update_job", side_effect=lambda jid, status, progress: job_updates.append((jid, status, progress))), \
             mock.patch.object(main.db, "update_entregables", side_effect=lambda cid, data: entregables_saved.update(data)), \
             mock.patch("time.sleep"):
            main._run_kp_generation_job(job_id=42, convocatoria_id=99, instrucciones="")

        last_job_id, last_status, last_progress = job_updates[-1]
        self.assertEqual(last_job_id, 42)
        self.assertEqual(last_status, "completed")
        outcome = last_progress["outputs"]["4_kp"]
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(outcome["pack_identity"]["pack_id"], "kp-fake-1")

        self.assertIn("4_kp", entregables_saved)
        self.assertIn("4_kp_json", entregables_saved)
        self.assertIn("4_kp_audit", entregables_saved)
        root = json.loads(entregables_saved["4_kp_json"])
        self.assertEqual(root["version_esquema"], "2.5")

    def test_job_reports_error_status_when_no_pack_uploaded(self):
        """La misma validación 404/422 del endpoint síncrono se aplica dentro
        del job: nunca se deja un job colgado en 'running' si la entrada es
        inválida antes de gastar ninguna llamada a Claude."""
        fake_conv = {
            "nombre": "FAKE 2026",
            "documentos_json": [{"etiqueta": "plantilla_memoria", "texto": "x", "nombre_archivo": "p.docx"}],
            "entregables_json": {},  # sin pack subido
        }
        job_updates = []

        with mock.patch.object(main.db, "get_convocatoria", return_value=fake_conv), \
             mock.patch.object(main.db, "update_job", side_effect=lambda jid, status, progress: job_updates.append((status, progress))):
            main._run_kp_generation_job(job_id=1, convocatoria_id=1)

        self.assertEqual(job_updates[-1][0], "error")
        self.assertIn("Knowledge Pack", job_updates[-1][1]["outputs"]["4_kp"]["error"])


if __name__ == "__main__":
    unittest.main()
