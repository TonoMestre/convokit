"""
ConvoKit — Plantilla HTML del email de resultado del evaluador de encaje.
Se envía al cliente vía Resend tras completar el formulario de contacto.

Restricciones de email (NO son como una web):
- Maquetación con <table>, nunca flexbox/grid (Gmail/Outlook no los soportan).
- Estilos inline, unidades en px (no rem).
- Imágenes alojadas en URL pública (Gmail bloquea base64 inline).
- Fuentes web-safe (Georgia/Arial); los clientes no cargan Google Fonts.
"""

import html
import json

NAVY = "#1D254C"
RED = "#C50339"
CREAM = "#F2EBD8"
WHITE = "#FFFFFF"


def _esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def _score_block(puntuacion_actual: int, puntuacion_max: int) -> str:
    if puntuacion_max <= 0:
        return ""
    bar_width = min(round(puntuacion_actual / puntuacion_max * 100), 100)
    return f"""
              <!-- Score -->
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0 0 28px 0;">
                <tr>
                  <td width="50%" style="padding:0 6px 0 0;" valign="top">
                    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};">
                      <tr><td style="padding:24px 16px;text-align:center;">
                        <div style="font-family:Georgia,serif;font-weight:700;font-size:40px;color:{NAVY};line-height:1;">{puntuacion_actual}</div>
                        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-top:10px;">Puntuación estimada</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="50%" style="padding:0 0 0 6px;" valign="top">
                    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};">
                      <tr><td style="padding:24px 16px;text-align:center;">
                        <div style="font-family:Georgia,serif;font-weight:700;font-size:40px;color:{NAVY};line-height:1;">{puntuacion_max}</div>
                        <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;margin-top:10px;">Puntos totales</div>
                      </td></tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Barra de progreso -->
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0 0 8px 0;">
                <tr>
                  <td style="background:#e5e1d4;font-size:0;line-height:0;height:8px;">
                    <table width="{bar_width}%" cellpadding="0" cellspacing="0" role="presentation"><tr>
                      <td style="background:{NAVY};font-size:0;line-height:0;height:8px;">&nbsp;</td>
                    </tr></table>
                  </td>
                </tr>
              </table>
              <p style="font-size:12px;color:#8a8a8a;margin:0 0 4px 0;">Puntuación estimada sobre {puntuacion_max} puntos totales</p>
    """


def _header(logo_url: str) -> str:
    if logo_url:
        brand = f'<img src="{logo_url}" height="30" alt="Innóvate 4.0" style="display:block;border:0;height:30px;width:auto;" />'
    else:
        brand = f'<span style="font-family:Georgia,serif;font-weight:700;font-size:18px;color:{WHITE};letter-spacing:0.02em;">INNÓVATE 4.0</span>'
    return f"""
          <!-- Header -->
          <tr>
            <td style="background:{NAVY};padding:22px 36px;border-bottom:3px solid {RED};">
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td valign="middle">{brand}</td>
                  <td valign="middle" align="right">
                    <span style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:rgba(255,255,255,0.55);text-transform:uppercase;letter-spacing:0.12em;">Evaluador de encaje</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
    """


def build_result_email_html(
    nombre: str,
    empresa: str,
    convocatoria: str,
    puntuacion_actual: int,
    puntuacion_max: int,
    veredicto: str,
    logo_url: str = "",
) -> str:
    nombre = _esc(nombre)
    empresa = _esc(empresa)
    convocatoria = _esc(convocatoria)
    veredicto = _esc(veredicto)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
  <title>Tu resultado en {convocatoria}</title>
</head>
<body style="margin:0;padding:0;background:{CREAM};font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">

  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="max-width:600px;width:100%;">

          {_header(logo_url)}

          <!-- Body -->
          <tr>
            <td style="background:{WHITE};padding:44px 40px;">

              <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{RED};margin:0 0 10px 0;">{empresa}</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:28px;color:{NAVY};margin:0 0 24px 0;line-height:1.2;">
                Tu resultado en {convocatoria}
              </h1>

              <p style="font-size:15px;line-height:1.65;color:{NAVY};margin:0 0 32px 0;">
                Hola {nombre}, gracias por completar el evaluador de encaje. Aquí tienes tu resultado estimado:
              </p>

              {_score_block(puntuacion_actual, puntuacion_max)}

              <!-- Veredicto -->
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:32px 0;">
                <tr>
                  <td style="background:{CREAM};border-left:4px solid {RED};padding:22px 26px;">
                    <p style="font-size:15px;line-height:1.7;color:{NAVY};margin:0;">{veredicto}</p>
                  </td>
                </tr>
              </table>

              <!-- CTA -->
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:36px 0 0 0;">
                <tr>
                  <td style="background:{NAVY};padding:32px;">
                    <h2 style="font-family:Georgia,serif;font-weight:700;font-size:19px;color:{WHITE};margin:0 0 14px 0;line-height:1.3;">
                      ¿Quieres maximizar tu puntuación?
                    </h2>
                    <p style="font-size:14px;color:rgba(255,255,255,0.82);line-height:1.7;margin:0 0 24px 0;">
                      En Innóvate 4.0 te ayudamos a trabajar los criterios mejorables y a preparar una memoria técnica que argumente tu candidatura al máximo nivel.
                    </p>
                    <table cellpadding="0" cellspacing="0" role="presentation">
                      <tr>
                        <td style="background:{WHITE};">
                          <a href="mailto:hola@innovate40.es"
                             style="display:inline-block;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;padding:14px 30px;text-decoration:none;">
                            <span style="color:{NAVY};text-decoration:none;">Contactar con Innóvate 4.0</span>
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
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
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""


def _format_value(value):
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if value is None:
        return "—"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return value


def _kv_rows_html(data) -> str:
    """
    Filas etiqueta/valor para el bloque de resumen de un email.

    Acepta dos formatos:
    - Lista de {"label": ..., "value": ...}: el evaluador ya decidió la
      etiqueta legible (preferido: evita adivinar traducciones de claves
      técnicas como "objective_score" o "sector_tension").
    - Dict plano (compatibilidad): la clave se usa como etiqueta best-effort
      (guiones bajos → espacios, primera letra en mayúscula).
    """
    if isinstance(data, list):
        pairs = [
            (item.get("label", ""), item.get("value", ""))
            for item in data if isinstance(item, dict)
        ]
    elif isinstance(data, dict):
        pairs = [(str(k).replace("_", " ").capitalize(), v) for k, v in data.items()]
    else:
        pairs = []

    if not pairs:
        return ""

    rows = []
    for label, value in pairs:
        rows.append(f"""
              <tr>
                <td style="padding:8px 12px;font-size:12.5px;font-weight:700;color:{NAVY};background:{CREAM};border-bottom:1px solid #e5e1d4;white-space:nowrap;vertical-align:top;">{_esc(label)}</td>
                <td style="padding:8px 12px;font-size:13px;color:{NAVY};border-bottom:1px solid #e5e1d4;">{_esc(_format_value(value))}</td>
              </tr>""")
    return f"""
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid #e5e1d4;margin:0 0 24px 0;">
                {''.join(rows)}
              </table>"""


def _pending_actions_html(pending_actions: list) -> str:
    if not pending_actions:
        return ""
    items = []
    for action in pending_actions:
        if not isinstance(action, dict):
            continue
        gain = _esc(action.get("gain", ""))
        title = _esc(action.get("title", ""))
        text = _esc(action.get("text", ""))
        items.append(f"""
              <tr>
                <td style="padding:10px 12px;background:{CREAM};border-left:3px solid {RED};">
                  <span style="font-weight:700;color:{RED};">{gain}</span>
                  <span style="font-weight:700;color:{NAVY};"> — {title}</span>
                  <div style="font-size:12.5px;color:{NAVY};margin-top:3px;">{text}</div>
                </td>
              </tr>
              <tr><td style="height:6px;line-height:6px;font-size:0;">&nbsp;</td></tr>""")
    if not items:
        return ""
    return f"""
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0 0 24px 0;">
                {''.join(items)}
              </table>"""


def build_internal_lead_email_html(
    tool: str,
    source: str,
    page_url: str,
    created_at: str,
    lead: dict,
    summary,
    answers: dict,
    pending_actions: list,
    logo_url: str = "",
) -> str:
    """
    Email interno para Innóvate 4.0 tras un envío del evaluador/cualificador.
    Incluye datos de contacto, resumen del resultado, respuestas completas y
    alertas/riesgos detectados. No se muestra al cliente.
    """
    lead = lead or {}
    contacto = {
        "Nombre": lead.get("nombre", ""),
        "Empresa": lead.get("empresa", ""),
        "Poblacion": lead.get("poblacion", ""),
        "Telefono": lead.get("telefono", ""),
        "Email": lead.get("email", ""),
    }
    metadata = {
        "Ayuda / herramienta": tool or source or "",
        "Origen": source or "",
        "URL de origen": page_url or "",
        "Fecha y hora": created_at or "",
    }

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Nuevo resultado de cualificador — {_esc(lead.get("empresa", ""))}</title>
</head>
<body style="margin:0;padding:0;background:{CREAM};font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="680" cellpadding="0" cellspacing="0" role="presentation" style="max-width:680px;width:100%;">

          {_header(logo_url)}

          <tr>
            <td style="background:{WHITE};padding:36px 32px;">
              <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{RED};margin:0 0 10px 0;">Nuevo lead del cualificador</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:22px;color:{NAVY};margin:0 0 22px 0;line-height:1.3;">
                {_esc(lead.get("empresa", "Empresa sin nombre"))} — {_esc(tool or source)}
              </h1>

              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Contacto</p>
              {_kv_rows_html(contacto)}

              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Datos del envío</p>
              {_kv_rows_html(metadata)}

              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Resultado / resumen</p>
              {_kv_rows_html(summary) or f'<p style="font-size:13px;color:{NAVY};margin:0 0 24px 0;">Sin resumen estructurado.</p>'}

              {(_pending_actions_html(pending_actions) and f'<p style="font-size:13px;font-weight:700;color:{NAVY};margin:0 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Alertas y puntos de mejora</p>' + _pending_actions_html(pending_actions)) or ""}

              <p style="font-size:13px;font-weight:700;color:{NAVY};margin:24px 0 8px 0;text-transform:uppercase;letter-spacing:0.05em;">Respuestas completas</p>
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f4f1e8;border:1px solid #e5e1d4;margin:0;">
                <tr><td style="padding:14px 16px;font-family:'Courier New',monospace;font-size:11.5px;color:{NAVY};white-space:pre-wrap;word-break:break-word;">{_esc(json.dumps(answers, ensure_ascii=False, indent=2))}</td></tr>
              </table>

            </td>
          </tr>

          <tr>
            <td style="background:{NAVY};padding:22px 32px;">
              <p style="font-family:Arial,Helvetica,sans-serif;font-size:11.5px;color:rgba(255,255,255,0.55);margin:0;line-height:1.8;text-align:center;">
                ConvoKit · notificación automática del evaluador de encaje
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def build_user_lead_email_html(
    tool: str,
    lead: dict,
    summary,
    logo_url: str = "",
) -> str:
    """
    Email al cliente tras completar el evaluador/cualificador. Resumen breve,
    aviso de que es orientativo, y mensaje de que Innóvate 4.0 contactará.
    """
    lead = lead or {}
    nombre = lead.get("nombre", "").strip() or "Hola"
    empresa = lead.get("empresa", "")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tu resultado en {_esc(tool)}</title>
</head>
<body style="margin:0;padding:0;background:{CREAM};font-family:Arial,Helvetica,sans-serif;-webkit-font-smoothing:antialiased;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{CREAM};padding:40px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="max-width:600px;width:100%;">

          {_header(logo_url)}

          <tr>
            <td style="background:{WHITE};padding:44px 40px;">
              <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:{RED};margin:0 0 10px 0;">{_esc(empresa)}</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:26px;color:{NAVY};margin:0 0 24px 0;line-height:1.2;">
                Tu resultado en {_esc(tool)}
              </h1>

              <p style="font-size:15px;line-height:1.65;color:{NAVY};margin:0 0 28px 0;">
                {_esc(nombre)}, gracias por completar el evaluador. Este es el resumen de tu resultado:
              </p>

              {_kv_rows_html(summary)}

              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0 0 28px 0;">
                <tr>
                  <td style="background:{CREAM};border-left:4px solid {RED};padding:18px 22px;">
                    <p style="font-size:13px;line-height:1.6;color:{NAVY};margin:0;">
                      Este resultado es orientativo. La puntuación y el encaje definitivos dependen de la documentación real del expediente y de la evaluación del organismo convocante.
                    </p>
                  </td>
                </tr>
              </table>

              <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin:0;">
                <tr>
                  <td style="background:{NAVY};padding:28px;">
                    <h2 style="font-family:Georgia,serif;font-weight:700;font-size:18px;color:{WHITE};margin:0 0 12px 0;line-height:1.3;">
                      Nos ponemos en contacto contigo
                    </h2>
                    <p style="font-size:13.5px;color:rgba(255,255,255,0.82);line-height:1.7;margin:0 0 20px 0;">
                      Un consultor de Innóvate 4.0 revisará tu caso y te contactará para comentar el proyecto y los siguientes pasos.
                    </p>
                    <table cellpadding="0" cellspacing="0" role="presentation">
                      <tr>
                        <td style="background:{WHITE};">
                          <a href="mailto:hola@innovate40.es"
                             style="display:inline-block;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;padding:14px 30px;text-decoration:none;">
                            <span style="color:{NAVY};text-decoration:none;">Contactar con Innóvate 4.0</span>
                          </a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

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
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
