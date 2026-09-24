"""
ConvoKit — emails del formulario de consulta de la landing de INPYME.

Reutiliza la paleta y el escapado de `result_email.py` (el mismo diseño que los
emails del evaluador) pero NO llama a sus funciones de cabecera/pie: la
cabecera del evaluador dice "Evaluador de encaje" y aquí no procede. Este
módulo no modifica `result_email.py`.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from result_email import CREAM, NAVY, RED, WHITE, _esc


def _header(logo_url: str, label: str) -> str:
    if logo_url:
        brand = f'<img src="{_esc(logo_url)}" height="30" alt="Innóvate 4.0" style="display:block;border:0;height:30px;width:auto;" />'
    else:
        brand = f'<span style="font-family:Georgia,serif;font-weight:700;font-size:18px;color:{WHITE};letter-spacing:0.02em;">INNÓVATE 4.0</span>'
    return f"""
          <tr>
            <td style="background:{NAVY};padding:22px 36px;border-bottom:3px solid {RED};">
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td valign="middle">{brand}</td>
                  <td valign="middle" align="right">
                    <span style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:0.12em;">{_esc(label)}</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""


_FOOTER = f"""
          <tr>
            <td style="background:{NAVY};padding:28px 36px;">
              <p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:rgba(255,255,255,0.55);margin:0;line-height:2;text-align:center;">
                Innóvate 4.0 Estrategia Empresarial, S.L. &nbsp;·&nbsp; NIF B-01.734.813<br />
                C/ Almirante Cadarso 13-8ª, 46005 València<br />
                <a href="mailto:hola@innovate40.es" style="color:#ffffff;text-decoration:underline;"><span style="color:#ffffff;">hola@innovate40.es</span></a>
                &nbsp;·&nbsp; 960 66 66 10<br />
                <a href="https://innovate40.es/aviso-legal/" style="color:#ffffff;text-decoration:underline;"><span style="color:#ffffff;">Aviso legal</span></a>
                &nbsp;·&nbsp;
                <a href="https://innovate40.es/politica-de-privacidad/" style="color:#ffffff;text-decoration:underline;"><span style="color:#ffffff;">Política de privacidad</span></a>
              </p>
            </td>
          </tr>"""


def _rows(pairs: list[tuple[str, str]]) -> str:
    rows = []
    for label, value in pairs:
        shown = _esc(value) if value else "—"
        rows.append(f"""
              <tr>
                <td style="padding:8px 12px;font-size:12.5px;font-weight:700;color:{NAVY};background:{CREAM};border-bottom:1px solid #e5e1d4;white-space:nowrap;vertical-align:top;">{_esc(label)}</td>
                <td style="padding:8px 12px;font-size:13px;color:{NAVY};border-bottom:1px solid #e5e1d4;">{shown}</td>
              </tr>""")
    return f"""
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid #e5e1d4;margin:0 0 24px 0;">
                {''.join(rows)}
              </table>"""


def _wrap(title: str, header_label: str, body: str, logo_url: str, width: int = 600) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{_esc(title)}</title>
</head>
<body style="margin:0;padding:0;background:{CREAM};font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="{width}" cellpadding="0" cellspacing="0" role="presentation" style="max-width:{width}px;width:100%;">
          {_header(logo_url, header_label)}
          <tr>
            <td style="background:{WHITE};padding:40px 36px;">
{body}
            </td>
          </tr>
          {_FOOTER}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def format_received_at(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    try:
        return now.astimezone(ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M (hora de Madrid)")
    except ZoneInfoNotFoundError:
        # Imagen sin base de zonas horarias: mejor UTC explícito que fallar.
        return now.astimezone(timezone.utc).strftime("%d/%m/%Y %H:%M (UTC)")


def internal_subject(empresa: str) -> str:
    return f"Nueva consulta INPYME 2027 · {empresa[:80]}"


def build_internal_email_html(payload: dict, submission_key: str, received_at: str, logo_url: str = "") -> str:
    """Aviso interno de una consulta de la landing. No es una evaluación."""
    empresa = payload.get("empresa", "")
    mensaje = payload.get("mensaje", "")
    mensaje_html = (
        f'<table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f1e8;border:1px solid #e5e1d4;margin:0 0 24px 0;">'
        f'<tr><td style="padding:14px 16px;font-size:13px;color:{NAVY};white-space:pre-wrap;word-break:break-word;">{_esc(mensaje)}</td></tr></table>'
        if mensaje
        else f'<p style="font-size:13px;color:{NAVY};margin:0 0 24px 0;">El cliente no ha escrito ningún mensaje.</p>'
    )
    body = f"""
              <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{RED};margin:0 0 10px 0;">Consulta de la landing · no es una evaluación</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:22px;color:{NAVY};margin:0 0 22px 0;line-height:1.3;">
                {_esc(empresa)} — Quiere que revisemos su caso (INPYME)
              </h1>
              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Contacto</p>
              {_rows([
                  ("Nombre", payload.get("nombre", "")),
                  ("Empresa", empresa),
                  ("Población", payload.get("poblacion", "")),
                  ("Teléfono", payload.get("telefono", "")),
                  ("Email", payload.get("email", "")),
              ])}
              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Mensaje</p>
              {mensaje_html}
              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Datos del envío</p>
              {_rows([
                  ("Origen", payload.get("source", "")),
                  ("Formulario", payload.get("form_name", "")),
                  ("URL de origen", payload.get("page_url", "")),
                  ("Recibida", received_at),
                  ("Referencia", submission_key),
              ])}
              <p style="font-size:12px;color:#6b7280;margin:0;line-height:1.6;">Puedes responder a este correo: la respuesta irá directamente al cliente.</p>"""
    return _wrap(internal_subject(empresa), "Consulta de la landing", body, logo_url, width=680)


def build_client_email_html(payload: dict, logo_url: str = "") -> str:
    """
    Confirmación de recepción al cliente. Solo confirma que la consulta ha
    llegado: no contiene resultado de evaluación, ni promesas de concesión, ni
    plazos de respuesta.
    """
    nombre = payload.get("nombre", "").strip() or "Hola"
    mensaje = payload.get("mensaje", "")
    echo = (
        f"""
              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Lo que nos has enviado</p>
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f1e8;border:1px solid #e5e1d4;margin:0 0 24px 0;">
                <tr><td style="padding:14px 16px;font-size:13px;color:{NAVY};white-space:pre-wrap;word-break:break-word;">{_esc(mensaje)}</td></tr>
              </table>"""
        if mensaje
        else ""
    )
    body = f"""
              <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{RED};margin:0 0 10px 0;">{_esc(payload.get("empresa", ""))}</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:26px;color:{NAVY};margin:0 0 24px 0;line-height:1.2;">
                Hemos recibido tu consulta sobre INPYME 2027
              </h1>
              <p style="font-size:15px;line-height:1.65;color:{NAVY};margin:0 0 16px 0;">
                {_esc(nombre)}, gracias por escribirnos. Este correo confirma que Innóvate 4.0 ha recibido tu consulta.
              </p>
              <p style="font-size:14px;line-height:1.65;color:{NAVY};margin:0 0 24px 0;">
                Tu consulta se refiere a la preparación de INPYME 2027, para la que tomamos como referencia la información de la convocatoria de 2026. Esa información es orientativa y no presupone las condiciones de una futura convocatoria.
              </p>
              {echo}
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0 0 28px 0;">
                <tr>
                  <td style="background:{CREAM};border-left:4px solid {RED};padding:18px 22px;">
                    <p style="font-size:13px;line-height:1.6;color:{NAVY};margin:0;">
                      Revisaremos la información que nos has facilitado. Este mensaje es solo una confirmación de recepción: no supone una valoración de tu proyecto ni garantiza el acceso a ninguna ayuda.
                    </p>
                  </td>
                </tr>
              </table>
              <p style="font-size:13px;line-height:1.6;color:#6b7280;margin:0;">
                Si quieres añadir algo, responde a este correo o escríbenos a
                <a href="mailto:hola@innovate40.es" style="color:{NAVY};">hola@innovate40.es</a>.
              </p>"""
    return _wrap("Hemos recibido tu consulta sobre INPYME 2027", "Consulta recibida", body, logo_url)
