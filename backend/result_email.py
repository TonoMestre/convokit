"""
ConvoKit — Plantilla HTML del email de resultado del evaluador de encaje.
Se envía al cliente vía Resend tras completar el formulario de contacto.
"""


def build_result_email_html(
    nombre: str,
    empresa: str,
    convocatoria: str,
    puntuacion_actual: int,
    puntuacion_max: int,
    veredicto: str,
) -> str:
    pct = round(puntuacion_actual / puntuacion_max * 100) if puntuacion_max > 0 else 0
    bar_width = min(pct, 100)

    score_block = ""
    if puntuacion_max > 0:
        score_block = f"""
        <div style="margin:24px 0;">
          <div style="display:flex;gap:16px;margin-bottom:12px;">
            <div style="flex:1;background:#F2EBD8;padding:16px 20px;text-align:center;">
              <div style="font-family:'Georgia',serif;font-weight:700;font-size:2.2rem;color:#1D254C;line-height:1;">{puntuacion_actual}</div>
              <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;color:rgba(29,37,76,0.6);margin-top:6px;">Puntuación estimada</div>
            </div>
            <div style="flex:1;background:#F2EBD8;padding:16px 20px;text-align:center;">
              <div style="font-family:'Georgia',serif;font-weight:700;font-size:2.2rem;color:#1D254C;line-height:1;">{puntuacion_max}</div>
              <div style="font-size:0.72rem;text-transform:uppercase;letter-spacing:0.07em;color:rgba(29,37,76,0.6);margin-top:6px;">Puntos totales</div>
            </div>
          </div>
          <div style="height:8px;background:rgba(29,37,76,0.1);margin-bottom:6px;">
            <div style="height:100%;width:{bar_width}%;background:#1D254C;"></div>
          </div>
          <p style="font-size:0.72rem;color:rgba(29,37,76,0.55);margin:0;">Puntuación estimada sobre {puntuacion_max} puntos totales</p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Tu resultado en {convocatoria}</title>
</head>
<body style="margin:0;padding:0;background:#F2EBD8;font-family:Arial,Helvetica,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F2EBD8;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#1D254C;padding:20px 32px;border-bottom:3px solid #C50339;">
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td>
                    <span style="font-family:Georgia,serif;font-weight:700;font-size:1.1rem;color:#FFFFFF;letter-spacing:0.02em;">INNÓVATE 4.0</span>
                  </td>
                  <td align="right">
                    <span style="font-size:0.7rem;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.1em;">Evaluador de encaje</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="background:#FFFFFF;padding:36px 32px;">

              <p style="font-size:0.78rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#C50339;margin:0 0 8px 0;">{empresa}</p>
              <h1 style="font-family:Georgia,serif;font-weight:700;font-size:1.5rem;color:#1D254C;margin:0 0 20px 0;line-height:1.25;">
                Tu resultado en {convocatoria}
              </h1>

              <p style="font-size:0.95rem;line-height:1.6;color:#1D254C;margin:0 0 20px 0;">
                Hola {nombre}, gracias por completar el evaluador de encaje. Aquí tienes tu resultado estimado:
              </p>

              {score_block}

              <div style="border-left:3px solid #C50339;padding:16px 20px;background:#F2EBD8;margin:24px 0;">
                <p style="font-size:0.95rem;line-height:1.65;color:#1D254C;margin:0;">{veredicto}</p>
              </div>

              <div style="background:#1D254C;padding:24px 28px;margin:28px 0 0 0;">
                <h2 style="font-family:Georgia,serif;font-weight:700;font-size:1.1rem;color:#FFFFFF;margin:0 0 10px 0;">
                  ¿Quieres maximizar tu puntuación?
                </h2>
                <p style="font-size:0.88rem;color:rgba(255,255,255,0.85);line-height:1.6;margin:0 0 16px 0;">
                  En Innóvate 4.0 te ayudamos a trabajar los criterios mejorables y a preparar una memoria técnica que argumente tu candidatura al máximo nivel.
                </p>
                <a href="mailto:hola@innovate40.es"
                   style="display:inline-block;background:#C50339;color:#FFFFFF;font-size:0.88rem;font-weight:600;padding:12px 24px;text-decoration:none;">
                  Contactar con Innóvate 4.0
                </a>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background:#1D254C;padding:20px 32px;">
              <p style="font-size:0.72rem;color:rgba(255,255,255,0.45);margin:0;line-height:1.8;text-align:center;">
                Innóvate 4.0 Estrategia Empresarial, S.L. &nbsp;·&nbsp; NIF B-01.734.813<br />
                C/ Almirante Cadarso 13-8ª, 46005 València<br />
                <a href="mailto:hola@innovate40.es" style="color:rgba(255,255,255,0.45);">hola@innovate40.es</a>
                &nbsp;·&nbsp; 960 66 66 10<br />
                <a href="https://innovate40.es/aviso-legal/" style="color:rgba(255,255,255,0.45);">Aviso legal</a>
                &nbsp;·&nbsp;
                <a href="https://innovate40.es/politica-de-privacidad/" style="color:rgba(255,255,255,0.45);">Política de privacidad</a>
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""
