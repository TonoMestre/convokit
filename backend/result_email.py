"""
ConvoKit — Plantilla HTML del email de resultado del evaluador de encaje.
Se envía al cliente vía Resend tras completar el formulario de contacto.

Restricciones de email (NO son como una web):
- Maquetación con <table>, nunca flexbox/grid (Gmail/Outlook no los soportan).
- Estilos inline, unidades en px (no rem).
- Imágenes alojadas en URL pública (Gmail bloquea base64 inline).
- Fuentes web-safe (Georgia/Arial); los clientes no cargan Google Fonts.
"""

NAVY = "#1D254C"
RED = "#C50339"
CREAM = "#F2EBD8"
WHITE = "#FFFFFF"


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
                        <td style="background:{RED};">
                          <a href="mailto:hola@innovate40.es"
                             style="display:inline-block;color:{WHITE};font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;padding:14px 30px;text-decoration:none;">
                            Contactar con Innóvate 4.0
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
              <p style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:rgba(255,255,255,0.5);margin:0;line-height:2;text-align:center;">
                Innóvate 4.0 Estrategia Empresarial, S.L. &nbsp;·&nbsp; NIF B-01.734.813<br />
                C/ Almirante Cadarso 13-8ª, 46005 València<br />
                <a href="mailto:hola@innovate40.es" style="color:rgba(255,255,255,0.5);text-decoration:underline;">hola@innovate40.es</a>
                &nbsp;·&nbsp; 960 66 66 10<br />
                <a href="https://innovate40.es/aviso-legal/" style="color:rgba(255,255,255,0.5);text-decoration:underline;">Aviso legal</a>
                &nbsp;·&nbsp;
                <a href="https://innovate40.es/politica-de-privacidad/" style="color:rgba(255,255,255,0.5);text-decoration:underline;">Política de privacidad</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""
