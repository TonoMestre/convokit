# -*- coding: utf-8 -*-
"""
Tests de caracterización de POST /submit-evaluation (evaluador de encaje).

No prueban funcionalidad nueva: fijan el comportamiento actual del evaluador
(honeypot, validación, gating del email al cliente, CORS global "*") para
comprobar que añadir POST /submit-contact no lo altera. Offline (Resend
simulado); datos ficticios.

Ejecutar: python -m unittest backend.tests.test_submit_evaluation_regression -v
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_PASSWORD", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used-network-is-mocked")

from starlette.testclient import TestClient

import main


def evaluation_payload(**lead_overrides):
    lead = {
        "nombre": "Ana Ejemplo",
        "empresa": "Empresa Ficticia SL",
        "poblacion": "Ciudad Ficticia",
        "telefono": "600 000 000",
        "email": "ana@cliente-ficticio.test",
        "website": "",
        "privacy": True,
    }
    lead.update(lead_overrides)
    return {
        "source": "inpyme",
        "tool": "INPYME",
        "created_at": "2026-01-01T10:00:00Z",
        "page_url": "https://innovate40.es/inpyme/",
        "lead": lead,
        "summary": [{"label": "Puntuación", "value": "50"}],
        "answers": {"pregunta_1": "respuesta ficticia"},
        "pending_actions": [],
    }


class EvaluationRegressionCase(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for key in ("EVALUATOR_INTERNAL_EMAIL", "EVALUATOR_REPLY_TO_EMAIL", "BACKEND_URL",
                    "CONTACT_ALLOWED_ORIGINS"):
            os.environ.pop(key, None)
        os.environ["RESEND_API_KEY"] = "re_test_key_ficticia"
        os.environ["RESEND_FROM_EMAIL"] = "Innóvate 4.0 <hola@innovate40.es>"
        os.environ["EVALUATOR_INTERNAL_EMAIL"] = "interno@innovate40.test"

        self.sent = []
        self.fail_to = set()

        def fake_send(*args, **kwargs):
            params = args[0]
            self.sent.append((args, kwargs))
            if params["to"][0] in self.fail_to:
                raise RuntimeError("fallo simulado")
            return {"id": "re_fake"}

        patcher = mock.patch.object(main.resend.Emails, "send", side_effect=fake_send)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(main.app)

    def post(self, payload=None, headers=None):
        return self.client.post("/submit-evaluation", json=payload or evaluation_payload(), headers=headers)


class TestSubmitEvaluationUnchanged(EvaluationRegressionCase):
    def test_success_sends_internal_and_client_emails(self):
        r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"success": True})
        self.assertEqual(len(self.sent), 2)
        internal, client = self.sent[0][0][0], self.sent[1][0][0]
        self.assertEqual(internal["to"], ["interno@innovate40.test"])
        self.assertTrue(internal["subject"].startswith("Nuevo resultado de cualificador - INPYME"))
        self.assertEqual(client["to"], ["ana@cliente-ficticio.test"])
        self.assertEqual(client["subject"], "Resultado de tu evaluación para INPYME")

    def test_send_is_called_exactly_as_before_without_idempotency_options(self):
        self.post()
        for args, kwargs in self.sent:
            self.assertEqual(len(args), 1)
            self.assertEqual(kwargs, {})

    def test_honeypot_still_answers_success_silently(self):
        r = self.post(evaluation_payload(website="http://spam.example"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"success": True})
        self.assertEqual(self.sent, [])

    def test_missing_required_fields(self):
        r = self.post(evaluation_payload(telefono=""))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json(), {"success": False, "message": "Revisa los campos obligatorios antes de continuar."})
        self.assertEqual(self.sent, [])

    def test_privacy_required(self):
        self.assertEqual(self.post(evaluation_payload(privacy=False)).status_code, 422)

    def test_invalid_email(self):
        r = self.post(evaluation_payload(email="no-valido"))
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["message"], "Introduce un correo electrónico válido.")

    def test_missing_resend_key(self):
        os.environ.pop("RESEND_API_KEY")
        r = self.post()
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.json()["success"])

    def test_client_email_failure_blocks_the_result(self):
        self.fail_to = {"ana@cliente-ficticio.test"}
        r = self.post()
        self.assertEqual(r.status_code, 502)
        self.assertFalse(r.json()["success"])

    def test_internal_email_failure_does_not_block_the_user(self):
        self.fail_to = {"interno@innovate40.test"}
        r = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"success": True})

    def test_still_public_when_app_password_is_enabled(self):
        with mock.patch.object(main, "APP_PASSWORD", "clave-ficticia"):
            self.assertEqual(self.post().status_code, 200)

    def test_cors_is_still_the_global_wildcard_for_any_origin_and_without_origin(self):
        r = self.post(headers={"Origin": "https://cualquier-sitio.test"})
        self.assertEqual(r.headers["access-control-allow-origin"], "*")
        self.assertEqual(self.post().status_code, 200)  # sin cabecera Origin: sigue funcionando
        pre = self.client.options("/submit-evaluation", headers={
            "Origin": "https://cualquier-sitio.test", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(pre.headers["access-control-allow-origin"], "*")

    def test_evaluation_never_uses_the_contact_persistence_or_limits(self):
        with mock.patch.object(main.db, "claim_contact_submission") as claim:
            for _ in range(8):  # más que el límite por IP de /submit-contact
                self.assertEqual(self.post().status_code, 200)
        claim.assert_not_called()

    def test_send_result_email_route_is_untouched(self):
        r = self.client.post("/send-result-email", json={
            "nombre": "Ana", "empresa": "Empresa Ficticia SL", "email": "no-valido",
            "convocatoria": "INPYME",
        })
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
