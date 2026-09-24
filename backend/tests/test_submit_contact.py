# -*- coding: utf-8 -*-
"""
Tests de POST /submit-contact (formulario «Quiero que reviséis mi caso» de la
landing de INPYME). Completamente offline: Resend está sustituido por un doble
que registra los envíos, y la base SQLite es un fichero temporal por test.
Todos los datos son ficticios.

Ejecutar: python -m unittest backend.tests.test_submit_contact -v
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_PASSWORD", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used-network-is-mocked")

from starlette.testclient import TestClient

import contact_form
import database
import main

ORIGIN = "https://innovate40.es"
_ENV_KEYS = [
    "CONTACT_ALLOWED_ORIGINS", "CONTACT_INTERNAL_EMAIL", "CONTACT_REPLY_TO_EMAIL",
    "EVALUATOR_REPLY_TO_EMAIL", "EVALUATOR_INTERNAL_EMAIL", "BACKEND_URL",
]


def valid_payload(**overrides):
    data = {
        "nombre": "Ana Ejemplo",
        "empresa": "Empresa Ficticia SL",
        "poblacion": "Ciudad Ficticia",
        "telefono": "600 000 000",
        "email": "ana@cliente-ficticio.test",
        "mensaje": "Quiero que revisen mi caso de ejemplo.",
        "privacy": True,
        "website": "",
    }
    data.update(overrides)
    return data


class Outbox:
    """Doble de resend.Emails.send: registra (params, options) y permite fallar."""

    def __init__(self):
        self.calls = []
        self.fail_to = set()
        self.no_id_to = set()

    def __call__(self, params, options=None):
        self.calls.append((params, options))
        recipient = params["to"][0]
        if recipient in self.fail_to:
            raise RuntimeError("fallo simulado de Resend")
        if recipient in self.no_id_to:
            return {}
        return {"id": f"re_fake_{len(self.calls)}"}

    def to(self, recipient):
        return [p for p, _ in self.calls if p["to"] == [recipient]]


class ContactTestCase(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["RESEND_API_KEY"] = "re_test_key_ficticia"
        os.environ["RESEND_FROM_EMAIL"] = "Innóvate 4.0 <hola@innovate40.es>"

        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        db_patch = mock.patch.object(main.db, "_DB_PATH", os.path.join(self.tmp, "test.db"))
        db_patch.start()
        self.addCleanup(db_patch.stop)

        self.outbox = Outbox()
        send_patch = mock.patch.object(main.resend.Emails, "send", side_effect=self.outbox)
        send_patch.start()
        self.addCleanup(send_patch.stop)

        main._CONTACT_IP_LIMITER.clear()
        main._CONTACT_EMAIL_LIMITER.clear()
        self.client = TestClient(main.app)

    def post(self, payload=None, headers=None, **kwargs):
        headers = {"Origin": ORIGIN, **(headers or {})}
        return self.client.post(
            "/submit-contact", json=valid_payload() if payload is None else payload,
            headers=headers, **kwargs,
        )


class TestSuccessAndEmails(ContactTestCase):
    def test_sends_both_emails_and_reports_success(self):
        r = self.post()
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["status"], "sent")
        self.assertEqual(body["emails"], {"internal": "accepted", "client": "accepted"})
        self.assertFalse(body["delivery_confirmed"])
        self.assertEqual(len(self.outbox.calls), 2)

    def test_internal_email_goes_to_hola_with_identifiable_subject_and_client_reply_to(self):
        self.post()
        internal = self.outbox.to("hola@innovate40.es")[0]
        self.assertEqual(internal["subject"], "Nueva consulta INPYME 2027 · Empresa Ficticia SL")
        self.assertEqual(internal["reply_to"], ["ana@cliente-ficticio.test"])
        self.assertEqual(internal["from"], "Innóvate 4.0 <hola@innovate40.es>")
        html = internal["html"]
        for expected in ("Ana Ejemplo", "Empresa Ficticia SL", "Ciudad Ficticia", "600 000 000",
                         "ana@cliente-ficticio.test", "Quiero que revisen mi caso",
                         "landing_inpyme", "consulta_inpyme", "no es una evaluación"):
            self.assertIn(expected, html)

    def test_client_email_confirms_receipt_without_evaluation_or_promises(self):
        self.post()
        client = self.outbox.to("ana@cliente-ficticio.test")[0]
        self.assertIn("Hemos recibido tu consulta", client["subject"])
        html = client["html"].lower()
        self.assertIn("hemos recibido tu consulta sobre inpyme", html)
        for forbidden in ("puntuación", "resultado", "plazo", "concesión", "en 24", "en 48"):
            self.assertNotIn(forbidden, html)

    def test_internal_recipient_is_configurable(self):
        os.environ["CONTACT_INTERNAL_EMAIL"] = "equipo@innovate40.test"
        self.post()
        self.assertEqual(len(self.outbox.to("equipo@innovate40.test")), 1)
        self.assertEqual(len(self.outbox.to("hola@innovate40.es")), 0)

    def test_optional_fields_can_be_omitted(self):
        r = self.post({"nombre": "Ana Ejemplo", "empresa": "Empresa Ficticia SL",
                       "email": "ana@cliente-ficticio.test", "privacy": True})
        self.assertEqual(r.status_code, 200)

    def test_accepts_matching_source_and_form_name(self):
        r = self.post(valid_payload(source="landing_inpyme", form_name="consulta_inpyme"))
        self.assertEqual(r.status_code, 200)

    def test_privacy_accepted_as_string_true(self):
        self.assertEqual(self.post(valid_payload(privacy="true")).status_code, 200)

    def test_subject_cannot_be_used_for_header_injection(self):
        self.post(valid_payload(empresa="Empresa\r\nBcc: victima@ejemplo.test"))
        subject = self.outbox.to("hola@innovate40.es")[0]["subject"]
        self.assertNotIn("\n", subject)
        self.assertNotIn("\r", subject)

    def test_user_input_is_html_escaped_in_both_emails(self):
        self.post(valid_payload(mensaje="<script>alert('x')</script>", nombre="<b>Ana</b>"))
        for params, _ in self.outbox.calls:
            self.assertNotIn("<script>", params["html"])
            self.assertNotIn("<b>Ana</b>", params["html"])
            self.assertIn("&lt;script&gt;", params["html"])

    def test_response_does_not_leak_personal_data_or_resend_ids(self):
        text = self.post().text
        for leaked in ("ana@cliente-ficticio.test", "Ana Ejemplo", "re_fake_"):
            self.assertNotIn(leaked, text)


class TestValidation(ContactTestCase):
    def assert_invalid(self, r, field):
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "invalid")
        self.assertEqual(body["code"], "validation_error")
        self.assertIn(field, body["errors"])
        self.assertEqual(self.outbox.calls, [])

    def test_privacy_is_required(self):
        self.assert_invalid(self.post(valid_payload(privacy=False)), "privacy")
        self.assert_invalid(self.post({k: v for k, v in valid_payload().items() if k != "privacy"}), "privacy")

    def test_required_fields(self):
        for field in ("nombre", "empresa", "email"):
            with self.subTest(field=field):
                self.assert_invalid(self.post(valid_payload(**{field: "  "})), field)

    def test_invalid_email(self):
        for bad in ("no-es-un-email", "a@b", "a b@c.test", "a@@c.test"):
            with self.subTest(email=bad):
                self.assert_invalid(self.post(valid_payload(email=bad)), "email")

    def test_invalid_phone(self):
        self.assert_invalid(self.post(valid_payload(telefono="abc")), "telefono")

    def test_field_length_limits(self):
        self.assert_invalid(self.post(valid_payload(mensaje="x" * 3001)), "mensaje")
        self.assert_invalid(self.post(valid_payload(nombre="x" * 101)), "nombre")

    def test_non_string_fields_are_rejected(self):
        self.assert_invalid(self.post(valid_payload(nombre=["Ana"])), "nombre")

    def test_source_and_form_name_must_match_when_sent(self):
        self.assert_invalid(self.post(valid_payload(source="otra_landing")), "source")
        self.assert_invalid(self.post(valid_payload(form_name="otro_form")), "form_name")

    def test_invalid_submission_id(self):
        self.assert_invalid(self.post(valid_payload(submission_id="corto")), "submission_id")

    def test_malformed_json(self):
        r = self.client.post("/submit-contact", content=b"{no es json",
                             headers={"Origin": ORIGIN, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["code"], "invalid_json")

    def test_non_object_json(self):
        r = self.post([1, 2, 3])
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["status"], "invalid")

    def test_oversized_body(self):
        r = self.post(valid_payload(extra="x" * (contact_form.MAX_BODY_BYTES + 1)))
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.json()["code"], "payload_too_large")

    def test_unknown_extra_fields_are_ignored(self):
        self.assertEqual(self.post(valid_payload(_wpnonce="abc123")).status_code, 200)


class TestAntispam(ContactTestCase):
    def test_honeypot_website_is_reported_as_spam_and_sends_nothing(self):
        r = self.post(valid_payload(website="http://spam.example"))
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "spam")
        self.assertEqual(body["code"], "spam_detected")
        self.assertEqual(self.outbox.calls, [])

    def test_web3forms_style_botcheck_is_also_a_honeypot(self):
        r = self.post(valid_payload(botcheck=True))
        self.assertEqual(r.json()["status"], "spam")
        self.assertEqual(self.outbox.calls, [])

    def test_unchecked_botcheck_is_not_spam(self):
        self.assertEqual(self.post(valid_payload(botcheck=False)).status_code, 200)

    def test_per_ip_rate_limit(self):
        for i in range(5):
            r = self.post(valid_payload(mensaje=f"consulta ficticia {i}", email=f"u{i}@cliente-ficticio.test"))
            self.assertEqual(r.status_code, 200)
        r = self.post(valid_payload(mensaje="una más", email="u9@cliente-ficticio.test"))
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.json()["status"], "rate_limited")
        self.assertEqual(len(self.outbox.calls), 10)

    def test_rate_limit_is_per_ip(self):
        for i in range(5):
            self.post(valid_payload(mensaje=f"m{i}", email=f"v{i}@cliente-ficticio.test"),
                      headers={"X-Forwarded-For": "203.0.113.1"})
        other = self.post(valid_payload(mensaje="otra ip"), headers={"X-Forwarded-For": "203.0.113.2"})
        self.assertEqual(other.status_code, 200)

    def test_per_email_limit_prevents_using_the_form_to_spam_a_third_party(self):
        for i in range(3):
            self.assertEqual(self.post(valid_payload(mensaje=f"distinto {i}")).status_code, 200)
        r = self.post(valid_payload(mensaje="distinto 3"))
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(self.outbox.calls), 6)


class TestCors(ContactTestCase):
    def test_allowed_origin_gets_its_own_origin_not_wildcard(self):
        r = self.post()
        self.assertEqual(r.headers["access-control-allow-origin"], ORIGIN)

    def test_www_origin_is_allowed(self):
        r = self.post(headers={"Origin": "https://www.innovate40.es"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["access-control-allow-origin"], "https://www.innovate40.es")

    def test_unknown_origin_is_rejected_without_cors_headers(self):
        r = self.post(headers={"Origin": "https://sitio-malicioso.test"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "origin_not_allowed")
        self.assertNotIn("access-control-allow-origin", r.headers)
        self.assertEqual(self.outbox.calls, [])

    def test_missing_origin_is_rejected(self):
        r = self.client.post("/submit-contact", json=valid_payload())
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.outbox.calls, [])

    def test_look_alike_origin_is_rejected(self):
        for origin in ("https://innovate40.es.evil.test", "http://innovate40.es", "https://innovate40.com"):
            with self.subTest(origin=origin):
                self.assertEqual(self.post(headers={"Origin": origin}).status_code, 403)

    def test_preflight_allowed(self):
        r = self.client.options("/submit-contact", headers={
            "Origin": ORIGIN, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        self.assertEqual(r.status_code, 204)
        self.assertEqual(r.headers["access-control-allow-origin"], ORIGIN)
        self.assertIn("POST", r.headers["access-control-allow-methods"])
        self.assertEqual(self.outbox.calls, [])

    def test_preflight_rejected_for_unknown_origin(self):
        r = self.client.options("/submit-contact", headers={
            "Origin": "https://sitio-malicioso.test", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(r.status_code, 403)
        self.assertNotIn("access-control-allow-origin", r.headers)

    def test_allowed_origins_are_configurable(self):
        os.environ["CONTACT_ALLOWED_ORIGINS"] = "https://staging.innovate40.test"
        self.assertEqual(self.post(headers={"Origin": "https://staging.innovate40.test"}).status_code, 200)
        self.assertEqual(self.post(headers={"Origin": ORIGIN}).status_code, 403)

    def test_empty_allowed_origins_variable_falls_back_to_defaults(self):
        os.environ["CONTACT_ALLOWED_ORIGINS"] = ""
        self.assertEqual(self.post().status_code, 200)

    def test_other_routes_keep_the_global_wildcard_cors(self):
        r = self.client.get("/health", headers={"Origin": "https://cualquier-sitio.test"})
        self.assertEqual(r.headers["access-control-allow-origin"], "*")
        pre = self.client.options("/submit-evaluation", headers={
            "Origin": "https://cualquier-sitio.test", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(pre.headers["access-control-allow-origin"], "*")


class TestAccessControl(ContactTestCase):
    def test_public_when_app_password_is_enabled(self):
        with mock.patch.object(main, "APP_PASSWORD", "clave-ficticia"):
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(self.client.get("/stats").status_code, 401)


class TestServerErrors(ContactTestCase):
    def test_missing_resend_key_is_unavailable_and_sends_nothing(self):
        os.environ.pop("RESEND_API_KEY")
        r = self.post()
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.json()["success"])
        self.assertEqual(r.json()["status"], "unavailable")
        self.assertEqual(self.outbox.calls, [])

    def test_both_emails_failing_is_not_success(self):
        self.outbox.fail_to = {"hola@innovate40.es", "ana@cliente-ficticio.test"}
        r = self.post()
        self.assertEqual(r.status_code, 502)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "send_failed")
        self.assertEqual(body["emails"], {"internal": "failed", "client": "failed"})
        self.assertTrue(body["retry_allowed"])

    def test_partial_when_client_email_fails(self):
        self.outbox.fail_to = {"ana@cliente-ficticio.test"}
        r = self.post()
        self.assertEqual(r.status_code, 502)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "partial_failure")
        self.assertEqual(body["emails"], {"internal": "accepted", "client": "failed"})

    def test_partial_when_internal_email_fails(self):
        self.outbox.fail_to = {"hola@innovate40.es"}
        body = self.post().json()
        self.assertFalse(body["success"])
        self.assertEqual(body["status"], "partial_failure")
        self.assertEqual(body["emails"], {"internal": "failed", "client": "accepted"})

    def test_a_failure_in_one_email_does_not_prevent_attempting_the_other(self):
        self.outbox.fail_to = {"hola@innovate40.es"}
        self.post()
        self.assertEqual(len(self.outbox.calls), 2)

    def test_resend_answer_without_id_counts_as_failed(self):
        self.outbox.no_id_to = {"ana@cliente-ficticio.test"}
        self.assertEqual(self.post().json()["status"], "partial_failure")

    def test_unexpected_error_returns_generic_server_error_without_details(self):
        with mock.patch.object(main.db, "claim_contact_submission", side_effect=RuntimeError("secreto interno")):
            r = self.post()
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.json()["status"], "server_error")
        self.assertNotIn("secreto interno", r.text)


class TestDuplicatesAndRetries(ContactTestCase):
    def test_same_submission_id_is_not_sent_twice(self):
        payload = valid_payload(submission_id="envio-ficticio-0001")
        first = self.post(payload)
        second = self.post(payload)
        self.assertEqual(first.json()["status"], "sent")
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json()["success"])
        self.assertEqual(second.json()["status"], "duplicate")
        self.assertEqual(len(self.outbox.calls), 2)

    def test_identical_content_without_id_is_deduplicated_by_fingerprint(self):
        self.post()
        r = self.post()
        self.assertEqual(r.json()["status"], "duplicate")
        self.assertEqual(len(self.outbox.calls), 2)

    def test_fingerprint_ignores_case_and_whitespace_differences(self):
        self.post()
        r = self.post(valid_payload(email="ANA@cliente-ficticio.test", mensaje="  quiero que revisen   mi caso de ejemplo. "))
        self.assertEqual(r.json()["status"], "duplicate")

    def test_different_content_is_a_new_submission(self):
        self.post()
        self.post(valid_payload(mensaje="Otra consulta distinta."))
        self.assertEqual(len(self.outbox.calls), 4)

    def test_retry_after_partial_failure_only_resends_the_missing_email(self):
        payload = valid_payload(submission_id="envio-ficticio-0002")
        self.outbox.fail_to = {"ana@cliente-ficticio.test"}
        first = self.post(payload)
        self.assertEqual(first.json()["status"], "partial_failure")
        self.assertEqual(len(self.outbox.calls), 2)

        self.outbox.fail_to = set()
        retry = self.post(payload)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["status"], "sent")
        self.assertEqual(retry.json()["emails"], {"internal": "accepted", "client": "accepted"})
        # Un solo envío nuevo (al cliente): el interno ya estaba aceptado.
        self.assertEqual(len(self.outbox.calls), 3)
        self.assertEqual(self.outbox.calls[-1][0]["to"], ["ana@cliente-ficticio.test"])
        self.assertEqual(len(self.outbox.to("hola@innovate40.es")), 1)

    def test_retry_after_total_failure_sends_both(self):
        payload = valid_payload(submission_id="envio-ficticio-0003")
        self.outbox.fail_to = {"hola@innovate40.es", "ana@cliente-ficticio.test"}
        self.post(payload)
        self.outbox.fail_to = set()
        self.assertEqual(self.post(payload).json()["status"], "sent")
        self.assertEqual(len(self.outbox.calls), 4)

    def test_resend_receives_stable_idempotency_keys(self):
        payload = valid_payload(submission_id="envio-ficticio-0004")
        self.outbox.fail_to = {"ana@cliente-ficticio.test"}
        self.post(payload)
        self.outbox.fail_to = set()
        self.post(payload)
        client_keys = [o["idempotency_key"] for p, o in self.outbox.calls if p["to"] == ["ana@cliente-ficticio.test"]]
        self.assertEqual(len(client_keys), 2)
        self.assertEqual(client_keys[0], client_keys[1])
        self.assertTrue(client_keys[0].startswith("contact-client-"))
        internal_key = [o["idempotency_key"] for p, o in self.outbox.calls if p["to"] == ["hola@innovate40.es"]][0]
        self.assertTrue(internal_key.startswith("contact-internal-"))
        self.assertNotEqual(internal_key, client_keys[0])

    def test_concurrent_identical_request_is_reported_in_progress(self):
        key = contact_form.dedupe_key(contact_form.validate_payload(valid_payload())[0])
        main.db.claim_contact_submission(key)  # otra solicitud la tiene reservada
        r = self.post()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["status"], "in_progress")
        self.assertFalse(r.json()["success"])
        self.assertEqual(self.outbox.calls, [])

    def test_abandoned_reservation_can_be_taken_over(self):
        main.db.claim_contact_submission("id:reserva-vieja")
        self.assertEqual(main.db.claim_contact_submission("id:reserva-vieja")["action"], "in_progress")
        self.assertEqual(main.db.claim_contact_submission("id:reserva-vieja", stale_seconds=0)["action"], "send")

    def test_fingerprint_keys_expire_after_the_window_but_ids_do_not(self):
        for key in ("fp:abc", "id:abcdefgh"):
            main.db.claim_contact_submission(key)
            main.db.finish_contact_submission(key, "accepted", "accepted")
        self.assertEqual(main.db.claim_contact_submission("fp:abc", window_seconds=0)["action"], "send")
        self.assertEqual(main.db.claim_contact_submission("id:abcdefgh", window_seconds=0)["action"], "duplicate")

    def test_database_stores_no_personal_data(self):
        self.post()
        conn = sqlite3.connect(os.path.join(self.tmp, "test.db"))
        dump = json.dumps(conn.execute("SELECT * FROM contact_submissions").fetchall())
        conn.close()
        for personal in ("ana@cliente-ficticio.test", "Ana Ejemplo", "Empresa Ficticia", "600 000 000", "revisen"):
            self.assertNotIn(personal, dump)


class TestContactFormUnits(unittest.TestCase):
    def test_rate_limiter_window(self):
        limiter = contact_form.RateLimiter(limit=2, window_seconds=10)
        self.assertTrue(limiter.allow("a", now=0))
        self.assertTrue(limiter.allow("a", now=1))
        self.assertFalse(limiter.allow("a", now=2))
        self.assertTrue(limiter.allow("b", now=2))
        self.assertTrue(limiter.allow("a", now=11))

    def test_client_ip_uses_last_forwarded_entry(self):
        headers = {"x-forwarded-for": "1.1.1.1, 9.9.9.9"}
        self.assertEqual(contact_form.client_ip(headers, "10.0.0.1"), "9.9.9.9")
        self.assertEqual(contact_form.client_ip({}, "10.0.0.1"), "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
