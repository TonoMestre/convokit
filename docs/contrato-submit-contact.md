# Contrato — `POST /submit-contact`

Formulario independiente «Quiero que reviséis mi caso» (final de `https://innovate40.es/inpyme/`).
Sustituye a Web3Forms. **No es una evaluación**: no calcula ni envía resultados y no comparte
nada con `POST /submit-evaluation`, que no se ha modificado.

Todos los ejemplos usan datos ficticios.

## Resumen

| | |
|---|---|
| Ruta | `POST /submit-contact` |
| Backend | el mismo de ConvoKit en Railway (`BACKEND_URL`) |
| Autenticación | ninguna (ruta pública, como `/submit-evaluation`); protegida por origen, antispam y límites |
| Cuerpo | JSON (`Content-Type: application/json`), máximo 16 KB |
| CORS | solo los orígenes de `CONTACT_ALLOWED_ORIGINS` (por defecto `https://innovate40.es` y `https://www.innovate40.es`). El resto de rutas conserva su CORS global `*` |
| Emails | dos, vía Resend: aviso interno a `hola@innovate40.es` y confirmación al cliente |

## Campos de la solicitud

| Campo | Tipo | Obligatorio | Reglas |
|---|---|---|---|
| `nombre` | string | **sí** | 2–100 caracteres |
| `empresa` | string | **sí** | 2–150 caracteres |
| `email` | string | **sí** | email válido, máx. 254. Se usa como destinatario de la confirmación y como `reply-to` del aviso interno |
| `privacy` | boolean | **sí** | debe ser `true` (también se acepta `"true"`, `"on"`, `"1"`, `"si"`) |
| `poblacion` | string | no | máx. 100 |
| `telefono` | string | no | dígitos, espacios y `+ ( ) - .`; 6–20 caracteres |
| `mensaje` | string | no | máx. 3000 caracteres |
| `page_url` | string | no | URL `http(s)://…`, máx. 300 |
| `submission_id` | string | recomendado | 8–64 caracteres `A-Za-z0-9_-` (un UUID sirve). Ver «Reintentos» |
| `website` | string | no | **campo trampa antispam**: debe enviarse vacío u omitirse. También se trata como trampa `botcheck` con valor verdadero (nombre del campo de Web3Forms) |
| `source` | string | no | si se envía, debe ser `landing_inpyme` |
| `form_name` | string | no | si se envía, debe ser `consulta_inpyme` |

El servidor fija siempre `source: "landing_inpyme"` y `form_name: "consulta_inpyme"` en los emails
(el cliente no puede cambiarlos). Los campos desconocidos se ignoran. Los saltos de línea de los
campos de una línea se colapsan; los textos se escapan en el HTML de los emails.

> Los campos obligatorios son un mínimo pensado para no rechazar envíos legítimos: **hay que
> contrastarlos con el formulario real de WordPress**. Cambiar el conjunto obligatorio es una línea
> (`REQUIRED_FIELDS` y las validaciones en `backend/contact_form.py`).

## Ejemplo

```http
POST /submit-contact HTTP/1.1
Origin: https://innovate40.es
Content-Type: application/json

{
  "nombre": "Ana Ejemplo",
  "empresa": "Empresa Ficticia SL",
  "poblacion": "Ciudad Ficticia",
  "telefono": "600 000 000",
  "email": "ana@cliente-ficticio.test",
  "mensaje": "Quiero que revisen mi caso de ejemplo.",
  "privacy": true,
  "website": "",
  "submission_id": "4f9c2d7e-0000-4000-8000-000000000001",
  "source": "landing_inpyme",
  "form_name": "consulta_inpyme",
  "page_url": "https://innovate40.es/inpyme/"
}
```

## Respuestas

Todas son JSON con `success` (boolean) y `status` (string). WordPress debe decidir por `status`.
`success: true` **solo** cuando los dos emails han sido aceptados por Resend.

| Situación | HTTP | `success` | `status` | `code` | Notas |
|---|---|---|---|---|---|
| Éxito, los dos emails aceptados | 200 | true | `sent` | — | `emails: {internal: "accepted", client: "accepted"}` |
| Reintento de un envío ya completado | 200 | true | `duplicate` | — | No se ha reenviado ningún correo |
| Datos inválidos | 422 | false | `invalid` | `validation_error` | `errors: {campo: mensaje}` |
| JSON ilegible / no es un objeto | 422 | false | `invalid` | `invalid_json` | |
| Cuerpo demasiado grande | 413 | false | `invalid` | `payload_too_large` | |
| Antispam (campo trampa) | 400 | false | `spam` | `spam_detected` | No se envía nada |
| Origen no autorizado o ausente | 403 | false | `forbidden` | `origin_not_allowed` | Sin cabeceras CORS |
| Demasiadas solicitudes | 429 | false | `rate_limited` | `rate_limited` | Por IP y por email |
| Otra solicitud idéntica en curso | 409 | false | `in_progress` | `in_progress` | `retry_allowed: true` |
| **Envío parcial** (un email aceptado, otro fallido) | 502 | **false** | `partial_failure` | `partial_failure` | `emails` indica cuál falló; `retry_allowed: true` |
| Ningún email enviado | 502 | false | `send_failed` | `send_failed` | `retry_allowed: true` |
| Resend no configurado | 503 | false | `unavailable` | `email_not_configured` | |
| Error inesperado | 500 | false | `server_error` | `server_error` | Sin detalles internos; `retry_allowed: true` |

Ejemplos:

```json
{"success": true, "status": "sent", "message": "Hemos recibido tu consulta. Te hemos enviado un correo de confirmación.",
 "reference": "3fa1c2d4e5b60718", "emails": {"internal": "accepted", "client": "accepted"}, "delivery_confirmed": false}
```

```json
{"success": false, "status": "invalid", "code": "validation_error", "message": "Revisa los campos del formulario.",
 "errors": {"email": "Introduce un correo electrónico válido.", "privacy": "Debes aceptar la política de privacidad."}}
```

```json
{"success": false, "status": "partial_failure", "code": "partial_failure",
 "message": "Hemos recibido tu consulta pero no hemos podido completar todos los envíos. Puedes reintentar: no se duplicará lo que ya se envió.",
 "reference": "3fa1c2d4e5b60718", "emails": {"internal": "accepted", "client": "failed"},
 "retry_allowed": true, "delivery_confirmed": false}
```

Recomendación de interfaz: `sent`/`duplicate` → confirmación; `invalid` → marcar los campos de
`errors`; `partial_failure`/`send_failed`/`server_error`/`in_progress` → permitir reintentar con el
**mismo** `submission_id`; `rate_limited` → pedir esperar; `spam`/`forbidden` → mensaje genérico.
Si `emails.internal` es `accepted` el equipo **ya tiene** la consulta aunque el cliente no reciba la
confirmación.

## Aceptado por Resend ≠ entregado

`emails.*: "accepted"` significa que **Resend aceptó el mensaje**, no que llegue a la bandeja
(puede rebotar o caer en spam después). Este backend no procesa webhooks de entrega, así que
`delivery_confirmed` es siempre `false`. La respuesta no incluye direcciones ni ids de Resend
(estos últimos se guardan solo en la base de datos, no en la respuesta).

## Reintentos y duplicados

- **Clave de idempotencia**: `submission_id` si se envía (recomendado: un UUID generado al cargar el
  formulario y reutilizado en cada reintento de ese envío); si no, una huella del contenido
  (email + nombre + empresa + mensaje, sin distinguir mayúsculas ni espacios) que caduca a las 24 h.
- Un reintento con la misma clave **nunca reenvía un email ya aceptado**: si el interno se aceptó y
  el del cliente falló, el reintento envía solo el del cliente y devuelve `sent`.
- Resend recibe además una `Idempotency-Key` estable por email, que protege frente a duplicados
  incluso si se perdiera la base de datos local.
- La base guarda solo la clave y el **estado** de cada email (tabla `contact_submissions`);
  no guarda nombre, email, teléfono ni mensaje.
- Si el usuario **cambia el contenido** tras un fallo, conviene generar un `submission_id` nuevo.

## Antispam y límites

- Campo trampa `website` (o `botcheck`): relleno → `400 spam`, sin envíos. A diferencia de
  `/submit-evaluation` (que responde éxito silencioso), aquí se distingue a propósito para que
  WordPress pueda tratarlo.
- Origen: se exige cabecera `Origin` de la lista permitida (comparación exacta de esquema y host).
  Una petición sin `Origin` (curl, servidor) se rechaza.
- Límites de frecuencia en memoria: 5 solicitudes / 10 min por IP; 3 envíos nuevos / hora por email
  (impide usar el formulario para mandar confirmaciones a terceros). Son por proceso: se reinician
  al desplegar y no se comparten entre réplicas.
- IP del solicitante: última entrada de `X-Forwarded-For` (la que añade el proxy de Railway).

## Variables de entorno

Nuevas (todas opcionales):

| Variable | Uso | Por defecto |
|---|---|---|
| `CONTACT_ALLOWED_ORIGINS` | Orígenes permitidos, separados por comas | `https://innovate40.es,https://www.innovate40.es` |
| `CONTACT_INTERNAL_EMAIL` | Destinatario del aviso interno | `hola@innovate40.es` |
| `CONTACT_REPLY_TO_EMAIL` | `reply-to` del email al cliente | `EVALUATOR_REPLY_TO_EMAIL`, o ninguno |

Reutilizadas: `RESEND_API_KEY` (obligatoria), `RESEND_FROM_EMAIL` (remitente verificado existente),
`EVALUATOR_REPLY_TO_EMAIL` (fallback), `BACKEND_URL` (logo en los emails), `DB_PATH`.
Ninguna clave va a WordPress ni al repositorio.

## Limitaciones conocidas

- El asunto interno usa literalmente «INPYME 2027» (según el encargo); ConvoKit trabaja hoy con
  INPYME 2026. Está en `contact_email.internal_subject`.
- Sin verificación de bandeja de entrada (ver arriba) ni reintentos automáticos en segundo plano:
  el reintento lo inicia el cliente (WordPress).
- Los límites de frecuencia no son distribuidos.
