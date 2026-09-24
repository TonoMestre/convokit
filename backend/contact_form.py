"""
ConvoKit — lógica pura del formulario de consulta de la landing de INPYME
(`POST /submit-contact`). Sin FastAPI ni Resend: validación, saneado, huella de
deduplicación, control de origen y límites de frecuencia. Así se puede probar
sin red y sin tocar el evaluador (`/submit-evaluation`), que no comparte nada
con este módulo.
"""

import hashlib
import os
import re
import time
from collections import defaultdict, deque
from threading import Lock

SOURCE = "landing_inpyme"
FORM_NAME = "consulta_inpyme"

# Campos que puede rellenar el formulario. Solo los cuatro primeros son
# obligatorios; el resto se admiten si el formulario los tiene.
REQUIRED_FIELDS = ("nombre", "empresa", "email", "privacy")

MAX_BODY_BYTES = 16 * 1024
_MAX_LEN = {
    "nombre": 100,
    "empresa": 150,
    "poblacion": 100,
    "telefono": 20,
    "email": 254,
    "mensaje": 3000,
    "page_url": 300,
}

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
_PHONE_RE = re.compile(r"^[0-9+()\-.\s]{6,20}$")
_SUBMISSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TRUE_STRINGS = {"true", "on", "1", "yes", "si", "sí"}

DEFAULT_ALLOWED_ORIGINS = "https://innovate40.es,https://www.innovate40.es"


def allowed_origins() -> set[str]:
    # `or`: una variable declarada pero vacía (como en .env.example) usa el valor por defecto.
    raw = os.environ.get("CONTACT_ALLOWED_ORIGINS") or DEFAULT_ALLOWED_ORIGINS
    return {o.strip().rstrip("/").lower() for o in raw.split(",") if o.strip()}


def is_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    return origin.strip().rstrip("/").lower() in allowed_origins()


def is_valid_email(value: str) -> bool:
    value = (value or "").strip()
    return bool(_EMAIL_RE.match(value)) and len(value) <= _MAX_LEN["email"]


def _single_line(value: str) -> str:
    """Colapsa saltos de línea y espacios: el valor acaba en asuntos de email."""
    return re.sub(r"\s+", " ", _CONTROL_RE.sub(" ", value)).strip()


def _multi_line(value: str) -> str:
    value = _CONTROL_RE.sub("", value.replace("\r\n", "\n").replace("\r", "\n"))
    return value.strip()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_STRINGS
    return False


class ContactPayload(dict):
    """Solicitud ya validada y saneada."""


def validate_payload(data) -> tuple[ContactPayload | None, dict[str, str]]:
    """
    Devuelve (payload, errores). Si hay errores, payload es None. No comprueba
    el honeypot ni la frecuencia: eso lo decide el endpoint antes/después.
    """
    errors: dict[str, str] = {}
    if not isinstance(data, dict):
        return None, {"_body": "El cuerpo de la solicitud no es válido."}

    out = ContactPayload()

    for field in ("nombre", "empresa", "poblacion", "telefono", "email", "mensaje", "page_url"):
        raw = data.get(field, "")
        if raw is None:
            raw = ""
        if not isinstance(raw, str):
            errors[field] = "Formato no válido."
            continue
        cleaned = _multi_line(raw) if field == "mensaje" else _single_line(raw)
        if len(cleaned) > _MAX_LEN[field]:
            errors[field] = f"Máximo {_MAX_LEN[field]} caracteres."
            continue
        out[field] = cleaned

    if "nombre" not in errors and len(out.get("nombre", "")) < 2:
        errors["nombre"] = "Indica tu nombre."
    if "empresa" not in errors and len(out.get("empresa", "")) < 2:
        errors["empresa"] = "Indica el nombre de la empresa."
    if "email" not in errors and not is_valid_email(out.get("email", "")):
        errors["email"] = "Introduce un correo electrónico válido."
    if "telefono" not in errors and out.get("telefono") and not _PHONE_RE.match(out["telefono"]):
        errors["telefono"] = "Introduce un teléfono válido."
    if "page_url" not in errors and out.get("page_url") and not re.match(r"^https?://", out["page_url"]):
        errors["page_url"] = "URL no válida."

    out["privacy"] = _truthy(data.get("privacy"))
    if not out["privacy"]:
        errors["privacy"] = "Debes aceptar la política de privacidad."

    # source/form_name son fijos en el servidor. Si el cliente los envía deben
    # coincidir: este endpoint no acepta formularios de otras páginas.
    sent_source = data.get("source")
    if sent_source not in (None, "") and sent_source != SOURCE:
        errors["source"] = "Origen del formulario no válido."
    sent_form = data.get("form_name")
    if sent_form not in (None, "") and sent_form != FORM_NAME:
        errors["form_name"] = "Formulario no válido."

    submission_id = data.get("submission_id")
    if submission_id in (None, ""):
        out["submission_id"] = ""
    elif isinstance(submission_id, str) and _SUBMISSION_ID_RE.match(submission_id):
        out["submission_id"] = submission_id
    else:
        errors["submission_id"] = "Identificador de envío no válido."

    if errors:
        return None, errors
    out["source"] = SOURCE
    out["form_name"] = FORM_NAME
    return out, {}


def is_honeypot_filled(data) -> bool:
    """
    Campo trampa relleno. `website` es el mismo nombre que usa el evaluador;
    `botcheck` es el que usa Web3Forms, por si el formulario lo conserva al migrar.
    """
    if not isinstance(data, dict):
        return False
    return bool(str(data.get("website") or "").strip()) or _truthy(data.get("botcheck"))


def dedupe_key(payload: ContactPayload) -> str:
    """
    Clave de idempotencia del envío. Si el cliente manda `submission_id`
    (recomendado: un UUID generado al cargar el formulario y reutilizado en los
    reintentos) manda ese. Si no, huella del contenido: el mismo email, nombre,
    empresa y mensaje se consideran el mismo envío (ventana en la BD).
    """
    if payload["submission_id"]:
        return "id:" + payload["submission_id"]
    basis = "|".join(
        [
            payload["email"].lower(),
            payload["nombre"].lower(),
            payload["empresa"].lower(),
            re.sub(r"\s+", " ", payload.get("mensaje", "")).lower(),
        ]
    )
    return "fp:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()


def hash_identifier(value: str) -> str:
    return hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:16]


class RateLimiter:
    """
    Ventana deslizante en memoria. Es por proceso: se reinicia con cada
    despliegue y no se comparte entre réplicas (Railway ejecuta una sola
    instancia de este backend). Frena ráfagas, no es una defensa distribuida.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._hits) > 5000:  # poda de claves caducadas: memoria acotada
                for stale in [k for k, h in self._hits.items() if not h or now - h[-1] >= self.window]:
                    del self._hits[stale]
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


def client_ip(headers, fallback: str) -> str:
    """
    IP del solicitante. Detrás del proxy de Railway, la última entrada de
    X-Forwarded-For es la que añade el proxy (las anteriores las controla el
    cliente y son falsificables).
    """
    xff = headers.get("x-forwarded-for", "")
    parts = [p.strip() for p in xff.split(",") if p.strip()]
    return parts[-1] if parts else (fallback or "unknown")
