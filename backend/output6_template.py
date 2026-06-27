"""
ConvoKit — Plantilla HTML para la Salida 6 (Evaluador de encaje interactivo).

Flujo de generación:
1. Claude extrae un objeto JSON de config desde los documentos de la convocatoria.
2. build_output_6_html(config) sustituye los placeholders en la plantilla estática.

El HTML resultante es completamente autocontenido (sin dependencias JS externas).
"""

import json


_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{{TITULO_EVALUADOR}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,700;0,9..144,900&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
<style>
  :root {
    --navy: #1D254C;
    --red: #C50339;
    --cream: #F2EBD8;
    --white: #FFFFFF;
    --black: #000000;
    --navy-10: rgba(29,37,76,0.10);
    --navy-20: rgba(29,37,76,0.20);
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { font-size: 16px; scroll-behavior: smooth; }
  body {
    font-family: 'IBM Plex Sans', sans-serif;
    background: var(--cream);
    color: var(--navy);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  .site-header {
    background: var(--navy);
    padding: 14px 24px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .site-header .logo-text {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 1.15rem;
    color: var(--white);
    letter-spacing: -0.01em;
  }
  .site-header .logo-text span { color: var(--red); }

  /* ── Progress bar ── */
  .progress-bar-wrap {
    background: var(--navy-10);
    height: 4px;
    width: 100%;
  }
  .progress-bar-inner {
    height: 100%;
    background: var(--red);
    transition: width 0.4s ease;
  }

  /* ── Layout ── */
  .container {
    max-width: 680px;
    width: 100%;
    margin: 0 auto;
    padding: 40px 24px 80px;
    flex: 1;
  }

  /* ── Steps ── */
  .step { display: none; }
  .step.active { display: block; }

  /* ── Intro ── */
  .intro-titulo {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 2rem;
    line-height: 1.15;
    color: var(--navy);
    margin-bottom: 14px;
  }
  .intro-lead {
    font-size: 1.05rem;
    line-height: 1.6;
    color: var(--navy);
    margin-bottom: 28px;
  }

  /* ── Strip ── */
  .strip {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 36px;
  }
  .strip-item {
    background: var(--navy);
    color: var(--white);
    padding: 10px 16px;
    flex: 1 1 auto;
  }
  .strip-item .strip-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.7;
    margin-bottom: 4px;
  }
  .strip-item .strip-valor {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 1rem;
  }

  /* ── Form fields ── */
  .field { margin-bottom: 20px; }
  .field label {
    display: block;
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--navy);
    margin-bottom: 6px;
  }
  .field input[type="text"],
  .field input[type="email"],
  .field input[type="tel"],
  .field input[type="number"] {
    width: 100%;
    padding: 11px 14px;
    border: 1.5px solid var(--navy-20);
    background: var(--white);
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.95rem;
    color: var(--navy);
    outline: none;
    border-radius: 0;
    transition: border-color 0.2s;
  }
  .field input:focus { border-color: var(--navy); }
  .field input.error { border-color: var(--red); }

  /* ── RGPD ── */
  .rgpd-block {
    background: var(--white);
    border: 1px solid var(--navy-10);
    padding: 16px;
    margin-bottom: 24px;
    font-size: 0.8rem;
    color: var(--navy);
    line-height: 1.55;
  }
  .rgpd-block a { color: var(--red); }
  .rgpd-check {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-top: 12px;
    font-size: 0.82rem;
    font-weight: 500;
    cursor: pointer;
  }
  .rgpd-check input[type="checkbox"] {
    margin-top: 2px;
    accent-color: var(--navy);
    width: 16px;
    height: 16px;
    flex-shrink: 0;
    border-radius: 0;
  }

  /* ── Opciones de pregunta ── */
  .pregunta-block {
    background: var(--white);
    border: 1px solid var(--navy-10);
    padding: 22px;
    margin-bottom: 20px;
  }
  .pregunta-titulo {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 1rem;
    color: var(--navy);
    margin-bottom: 8px;
  }
  .pregunta-ayuda {
    font-size: 0.82rem;
    color: rgba(29,37,76,0.65);
    margin-bottom: 14px;
    line-height: 1.5;
  }
  .opciones-lista { display: flex; flex-direction: column; gap: 8px; }
  .opcion {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 14px;
    border: 1.5px solid var(--navy-20);
    background: var(--white);
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
    text-align: left;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.9rem;
    color: var(--navy);
    border-radius: 0;
    width: 100%;
  }
  .opcion:hover { border-color: var(--navy); background: var(--cream); }
  .opcion.selected { border-color: var(--navy); background: var(--navy); color: var(--white); }
  .opcion .opcion-radio {
    width: 16px;
    height: 16px;
    border: 2px solid currentColor;
    border-radius: 0;
    flex-shrink: 0;
    margin-top: 2px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .opcion.selected .opcion-radio::after {
    content: '';
    width: 8px;
    height: 8px;
    background: var(--white);
    display: block;
  }
  .puntos-badge {
    margin-left: auto;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--red);
    white-space: nowrap;
    flex-shrink: 0;
  }
  .opcion.selected .puntos-badge { color: rgba(255,255,255,0.8); }

  /* ── Bloqueo panel ── */
  #bloqueo-panel {
    display: none;
    background: var(--navy);
    color: var(--white);
    padding: 28px;
    margin-top: 24px;
  }
  #bloqueo-panel.visible { display: block; }
  #bloqueo-panel h2 {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 1.4rem;
    margin-bottom: 10px;
  }
  #bloqueo-panel p {
    font-size: 0.9rem;
    line-height: 1.6;
    opacity: 0.88;
    margin-bottom: 20px;
  }
  #bloqueo-panel .field label { color: rgba(255,255,255,0.8); }
  #bloqueo-panel .field input {
    background: rgba(255,255,255,0.08);
    border-color: rgba(255,255,255,0.25);
    color: var(--white);
  }
  #bloqueo-panel .field input::placeholder { color: rgba(255,255,255,0.4); }
  #bloqueo-panel .field input:focus { border-color: var(--white); }

  /* ── Sección header ── */
  .section-header {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--red);
    border-bottom: 2px solid var(--red);
    padding-bottom: 6px;
    margin-bottom: 20px;
    margin-top: 36px;
  }
  .section-header:first-child { margin-top: 0; }

  /* ── Botones ── */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 13px 28px;
    font-family: 'IBM Plex Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    border: none;
    border-radius: 0;
    transition: background 0.2s, color 0.2s;
  }
  .btn-primary { background: var(--navy); color: var(--white); }
  .btn-primary:hover { background: #111828; }
  .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-secondary { background: transparent; color: var(--navy); border: 1.5px solid var(--navy); }
  .btn-secondary:hover { background: var(--navy); color: var(--white); }
  .btn-red { background: var(--red); color: var(--white); }
  .btn-red:hover { background: #a00230; }

  /* ── Step nav ── */
  .step-nav {
    display: flex;
    gap: 12px;
    margin-top: 28px;
    align-items: center;
  }

  /* ── Resultado ── */
  .resultado-card {
    background: var(--white);
    border: 1px solid var(--navy-10);
    padding: 28px;
    margin-bottom: 20px;
  }
  .resultado-empresa {
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--red);
    margin-bottom: 8px;
  }
  .veredicto-texto {
    font-size: 0.95rem;
    line-height: 1.65;
    color: var(--navy);
  }

  .score-display {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    margin: 20px 0;
  }
  .score-box {
    flex: 1 1 auto;
    background: var(--cream);
    padding: 16px 20px;
    text-align: center;
  }
  .score-box .score-num {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 2.5rem;
    color: var(--navy);
    line-height: 1;
  }
  .score-box .score-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: rgba(29,37,76,0.6);
    margin-top: 6px;
  }
  .score-box.potencial .score-num { color: var(--red); }

  .score-bar-wrap {
    height: 8px;
    background: var(--navy-10);
    margin-bottom: 6px;
  }
  .score-bar-inner {
    height: 100%;
    background: var(--navy);
    transition: width 0.6s ease;
  }
  .score-bar-inner.potencial { background: var(--red); opacity: 0.5; }

  /* ── Mejoras ── */
  .mejoras-lista { list-style: none; }
  .mejoras-lista li {
    padding: 10px 14px;
    border-left: 3px solid var(--red);
    background: var(--white);
    margin-bottom: 8px;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--navy);
  }

  /* ── Calculadora ── */
  .calc-block {
    background: var(--white);
    border: 1px solid var(--navy-10);
    padding: 24px;
    margin-bottom: 20px;
  }
  .calc-block h3 {
    font-family: 'Fraunces', serif;
    font-weight: 700;
    font-size: 1rem;
    color: var(--navy);
    margin-bottom: 8px;
  }
  .calc-formula {
    font-size: 0.8rem;
    color: rgba(29,37,76,0.65);
    margin-bottom: 16px;
    line-height: 1.5;
  }
  .calc-result {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 1.6rem;
    color: var(--red);
    margin-top: 12px;
  }

  /* ── CTA ── */
  .cta-block {
    background: var(--navy);
    color: var(--white);
    padding: 28px;
    margin-bottom: 20px;
  }
  .cta-block h2 {
    font-family: 'Fraunces', serif;
    font-weight: 900;
    font-size: 1.3rem;
    margin-bottom: 10px;
  }
  .cta-block p {
    font-size: 0.9rem;
    opacity: 0.88;
    line-height: 1.6;
    margin-bottom: 20px;
  }

  /* ── Nota fuente ── */
  .nota-fuente {
    font-size: 0.72rem;
    color: rgba(29,37,76,0.5);
    margin-top: 24px;
    line-height: 1.5;
  }

  /* ── Confirmación bloqueo ── */
  #bloqueo-confirm { display: none; }
  #bloqueo-confirm.visible { display: block; }
  #bloqueo-confirm p {
    font-size: 0.9rem;
    color: rgba(255,255,255,0.88);
    margin-top: 12px;
  }

  /* ── Footer ── */
  .site-footer {
    background: var(--navy);
    color: rgba(255,255,255,0.55);
    text-align: center;
    padding: 18px 24px;
    font-size: 0.75rem;
  }
  .site-footer a { color: rgba(255,255,255,0.55); }
  .site-footer a:hover { color: var(--white); }

  /* ── Responsive ── */
  @media (max-width: 480px) {
    .intro-titulo { font-size: 1.5rem; }
    .strip { gap: 8px; }
    .strip-item { padding: 8px 12px; }
    .score-display { gap: 12px; }
  }
</style>
</head>
<body>

<header class="site-header">
  <div class="logo-text">Innóvate<span>4.0</span></div>
</header>

<div class="progress-bar-wrap" id="progress-bar-wrap" style="display:none">
  <div class="progress-bar-inner" id="progress-bar-inner" style="width:0%"></div>
</div>

<main class="container">

  <!-- ═══════════════════════════════════════════════
       PASO 1 — Datos de la empresa
  ══════════════════════════════════════════════════ -->
  <div class="step active" id="step1">
    <p class="intro-titulo" id="intro-titulo-el"></p>
    <p class="intro-lead" id="intro-lead-el"></p>

    <div class="strip" id="strip-el"></div>

    <div class="field">
      <label for="campo-nombre">Tu nombre *</label>
      <input type="text" id="campo-nombre" placeholder="Nombre y apellidos" autocomplete="name" />
    </div>
    <div class="field">
      <label for="campo-empresa">Empresa *</label>
      <input type="text" id="campo-empresa" placeholder="Nombre de la empresa" autocomplete="organization" />
    </div>
    <div class="field">
      <label for="campo-municipio">Municipio</label>
      <input type="text" id="campo-municipio" placeholder="Municipio donde opera la empresa" autocomplete="address-level2" />
    </div>

    <div class="rgpd-block">
      <strong>Información sobre protección de datos</strong><br /><br />
      <strong>Responsable:</strong> INNÓVATE CONSULTORÍA AYUDAS PÚBLICAS S.L. — NIF B-01.734.813<br />
      <strong>Dirección:</strong> C/ Almirante Cadarso 13-8ª, 46005 València<br />
      <strong>Email:</strong> <a href="mailto:GDPR@INNOVATE40.ES">GDPR@INNOVATE40.ES</a><br /><br />
      Tus datos se utilizarán exclusivamente para atender tu consulta sobre ayudas públicas y no se cederán a terceros sin tu consentimiento. Puedes ejercer tus derechos de acceso, rectificación, supresión y portabilidad en la dirección anterior.
      <a href="https://innovate40.es/contacto/" target="_blank" rel="noopener"> Política de privacidad</a><br /><br />
      <label class="rgpd-check">
        <input type="checkbox" id="rgpd-check" />
        <span>He leído y acepto el tratamiento de mis datos para recibir información sobre esta convocatoria de ayudas públicas. *</span>
      </label>
    </div>

    <div class="step-nav">
      <button class="btn btn-primary" onclick="irPaso2()">Comenzar el evaluador →</button>
    </div>
    <div id="step1-error" style="color:var(--red);font-size:0.82rem;margin-top:10px;display:none;">
      Por favor, completa los campos obligatorios y acepta la política de privacidad.
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════
       PASO 2 — Preguntas (elegibilidad + baremo)
  ══════════════════════════════════════════════════ -->
  <div class="step" id="step2">
    <div id="preguntas-container"></div>

    <div id="bloqueo-panel">
      <h2 id="bloqueo-titulo-el"></h2>
      <p id="bloqueo-texto-el"></p>
      <div id="bloqueo-form">
        <div class="field">
          <label for="bloqueo-email">Tu email *</label>
          <input type="email" id="bloqueo-email" placeholder="email@empresa.com" />
        </div>
        <div class="field">
          <label for="bloqueo-tel">Teléfono</label>
          <input type="tel" id="bloqueo-tel" placeholder="Número de contacto" />
        </div>
        <button class="btn btn-red" onclick="enviarLeadBloqueo()">Recibir información de otras ayudas</button>
      </div>
      <div id="bloqueo-confirm">
        <p>✓ Gracias. Nos pondremos en contacto contigo para orientarte hacia las ayudas que mejor se adapten a tu empresa.</p>
      </div>
    </div>

    <div class="step-nav" id="step2-nav" style="display:none">
      <button class="btn btn-primary" onclick="irPaso3()">Continuar →</button>
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════
       PASO 3 — Datos de contacto
  ══════════════════════════════════════════════════ -->
  <div class="step" id="step3">
    <p class="section-header">Último paso</p>
    <p class="intro-lead" style="margin-bottom:24px;">Introduce tus datos de contacto para ver tu resultado personalizado.</p>

    <div class="field">
      <label for="campo-email">Email *</label>
      <input type="email" id="campo-email" placeholder="email@empresa.com" autocomplete="email" />
    </div>
    <div class="field">
      <label for="campo-tel">Teléfono *</label>
      <input type="tel" id="campo-tel" placeholder="Número de contacto" autocomplete="tel" />
    </div>

    <div class="step-nav">
      <button class="btn btn-primary" onclick="irPaso4()">Ver mi resultado →</button>
    </div>
    <div id="step3-error" style="color:var(--red);font-size:0.82rem;margin-top:10px;display:none;">
      Por favor, completa tu email y teléfono para ver el resultado.
    </div>
  </div>

  <!-- ═══════════════════════════════════════════════
       PASO 4 — Resultado
  ══════════════════════════════════════════════════ -->
  <div class="step" id="step4">
    <div id="resultado-container"></div>
  </div>

</main>

<footer class="site-footer">
  © Innóvate Consultoría Ayudas Públicas, S.L. &nbsp;|&nbsp;
  <a href="https://innovate40.es/aviso-legal/" target="_blank" rel="noopener">Aviso legal</a> &nbsp;|&nbsp;
  <a href="https://innovate40.es/contacto/" target="_blank" rel="noopener">Política de privacidad</a>
</footer>

<script>
// ═══════════════════════════════════════════════════
// Configuración extraída por Claude de la convocatoria
// ═══════════════════════════════════════════════════
window.CONVOCATORIA = {{CONFIG_JSON}};

const CFG = window.CONVOCATORIA;
const WEB3FORMS_KEY = "9230bf98-4a35-437a-b326-eb6e24e88f2e";
const BACKUP_EMAIL = "proyectos2@innovate40.es";

// Estado de la sesión
const STATE = {
  nombre: "",
  empresa: "",
  municipio: "",
  email: "",
  tel: "",
  respuestas: {},   // id -> { puntos, label, influenciable, esBloqueo, bloquea, motivo }
  bloqueado: false,
  bloqueoMotivo: "",
};

// ── Inicialización ──────────────────────────────
(function init() {
  // Intro
  document.getElementById("intro-titulo-el").textContent = CFG.textos.intro_titulo;
  document.getElementById("intro-lead-el").textContent = CFG.textos.intro_lead;

  // Strip
  const stripEl = document.getElementById("strip-el");
  (CFG.strip || []).forEach(function(item) {
    const div = document.createElement("div");
    div.className = "strip-item";
    div.innerHTML =
      '<div class="strip-label">' + escHtml(item.label) + '</div>' +
      '<div class="strip-valor">' + escHtml(item.valor) + '</div>';
    stripEl.appendChild(div);
  });

  // Renderizar preguntas
  renderPreguntas();
})();

// ── Render de preguntas ──────────────────────────
function renderPreguntas() {
  const container = document.getElementById("preguntas-container");
  container.innerHTML = "";

  const elegibilidad = CFG.elegibilidad || [];
  const baremo = CFG.baremo || [];

  if (elegibilidad.length > 0) {
    const h = document.createElement("p");
    h.className = "section-header";
    h.textContent = "Requisitos de acceso";
    container.appendChild(h);

    elegibilidad.forEach(function(preg) {
      container.appendChild(buildPreguntaEl(preg, true));
    });
  }

  if (baremo.length > 0) {
    const h = document.createElement("p");
    h.className = "section-header";
    h.textContent = "Criterios de valoración";
    container.appendChild(h);

    baremo.forEach(function(preg) {
      container.appendChild(buildPreguntaEl(preg, false));
    });
  }

  // Si no hay preguntas en ningún bloque, mostrar el nav directamente
  if (elegibilidad.length === 0 && baremo.length === 0) {
    document.getElementById("step2-nav").style.display = "flex";
  }

  actualizarNavPaso2();
}

function buildPreguntaEl(preg, esElegibilidad) {
  const block = document.createElement("div");
  block.className = "pregunta-block";
  block.id = "preg-block-" + preg.id;

  const titulo = document.createElement("p");
  titulo.className = "pregunta-titulo";
  titulo.textContent = preg.pregunta;
  block.appendChild(titulo);

  if (preg.ayuda) {
    const ayuda = document.createElement("p");
    ayuda.className = "pregunta-ayuda";
    ayuda.textContent = preg.ayuda;
    block.appendChild(ayuda);
  }

  const lista = document.createElement("div");
  lista.className = "opciones-lista";

  preg.opciones.forEach(function(opt, idx) {
    const btn = document.createElement("button");
    btn.className = "opcion";
    btn.setAttribute("data-id", preg.id);
    btn.setAttribute("data-idx", idx);
    btn.type = "button";

    const radio = document.createElement("span");
    radio.className = "opcion-radio";
    btn.appendChild(radio);

    const labelSpan = document.createElement("span");
    labelSpan.textContent = opt.label;
    btn.appendChild(labelSpan);

    if (!esElegibilidad && opt.puntos !== undefined) {
      const badge = document.createElement("span");
      badge.className = "puntos-badge";
      badge.textContent = opt.puntos + " pt";
      btn.appendChild(badge);
    }

    btn.addEventListener("click", function() {
      seleccionarOpcion(preg, opt, esElegibilidad, idx);
    });

    lista.appendChild(btn);
  });

  block.appendChild(lista);
  return block;
}

function seleccionarOpcion(preg, opt, esElegibilidad, idx) {
  // Actualizar UI
  const bloques = document.querySelectorAll('[data-id="' + preg.id + '"]');
  bloques.forEach(function(b) { b.classList.remove("selected"); });
  document.querySelectorAll('[data-id="' + preg.id + '"][data-idx="' + idx + '"]')
    .forEach(function(b) { b.classList.add("selected"); });

  // Guardar respuesta
  STATE.respuestas[preg.id] = {
    puntos: opt.puntos || 0,
    label: opt.label,
    influenciable: preg.influenciable || false,
    esBloqueo: esElegibilidad,
    bloquea: esElegibilidad && !!opt.bloquea,
    motivo: opt.motivo || "",
    preguntaLabel: preg.pregunta,
    puntosMax: preg.puntos_max || 0,
  };

  // Si es pregunta de elegibilidad y bloquea
  if (esElegibilidad && opt.bloquea) {
    STATE.bloqueado = true;
    STATE.bloqueoMotivo = opt.motivo || CFG.textos.no_elegible_texto;
    mostrarBloqueo();
  } else if (esElegibilidad && !opt.bloquea && STATE.bloqueado) {
    // Si desbloquea (cambió respuesta)
    STATE.bloqueado = false;
    ocultarBloqueo();
  }

  actualizarNavPaso2();
}

function actualizarNavPaso2() {
  if (STATE.bloqueado) {
    document.getElementById("step2-nav").style.display = "none";
    return;
  }

  const elegibilidad = CFG.elegibilidad || [];
  const baremo = CFG.baremo || [];
  const total = elegibilidad.length + baremo.length;

  const respondidas = Object.keys(STATE.respuestas).filter(function(id) {
    return !STATE.respuestas[id].bloquea;
  }).length;

  // Mostrar nav cuando todas respondidas (o no hay preguntas)
  const allAnswered = respondidas >= total;
  document.getElementById("step2-nav").style.display = allAnswered ? "flex" : "none";
}

function mostrarBloqueo() {
  const panel = document.getElementById("bloqueo-panel");
  panel.classList.add("visible");
  document.getElementById("step2-nav").style.display = "none";
  document.getElementById("bloqueo-titulo-el").textContent = CFG.textos.no_elegible_titulo;
  document.getElementById("bloqueo-texto-el").textContent = STATE.bloqueoMotivo || CFG.textos.no_elegible_texto;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function ocultarBloqueo() {
  document.getElementById("bloqueo-panel").classList.remove("visible");
  document.getElementById("bloqueo-confirm").classList.remove("visible");
  document.getElementById("bloqueo-form").style.display = "";
}

async function enviarLeadBloqueo() {
  const email = document.getElementById("bloqueo-email").value.trim();
  if (!email) {
    document.getElementById("bloqueo-email").classList.add("error");
    return;
  }
  await enviarWeb3Forms({
    tipo: "bloqueo",
    nombre: STATE.nombre,
    empresa: STATE.empresa,
    municipio: STATE.municipio,
    email: email,
    tel: document.getElementById("bloqueo-tel").value.trim(),
    motivo_bloqueo: STATE.bloqueoMotivo,
    convocatoria: CFG.titulo_corto,
  });
  document.getElementById("bloqueo-form").style.display = "none";
  document.getElementById("bloqueo-confirm").classList.add("visible");
}

// ── Navegación ───────────────────────────────────
function irPaso2() {
  const nombre = document.getElementById("campo-nombre").value.trim();
  const empresa = document.getElementById("campo-empresa").value.trim();
  const rgpd = document.getElementById("rgpd-check").checked;

  if (!nombre || !empresa || !rgpd) {
    document.getElementById("step1-error").style.display = "block";
    return;
  }
  document.getElementById("step1-error").style.display = "none";
  STATE.nombre = nombre;
  STATE.empresa = empresa;
  STATE.municipio = document.getElementById("campo-municipio").value.trim();

  mostrarStep("step2");
  setProgress(33);
}

function irPaso3() {
  mostrarStep("step3");
  setProgress(66);
}

async function irPaso4() {
  const email = document.getElementById("campo-email").value.trim();
  const tel = document.getElementById("campo-tel").value.trim();
  if (!email || !tel) {
    document.getElementById("step3-error").style.display = "block";
    return;
  }
  document.getElementById("step3-error").style.display = "none";
  STATE.email = email;
  STATE.tel = tel;

  // Calcular score
  const score = calcularScore();

  // Enviar lead (silently)
  enviarWeb3Forms({
    tipo: "resultado",
    nombre: STATE.nombre,
    empresa: STATE.empresa,
    municipio: STATE.municipio,
    email: STATE.email,
    tel: STATE.tel,
    convocatoria: CFG.titulo_corto,
    puntuacion_actual: score.actual,
    puntuacion_potencial: score.potencial,
    puntuacion_max: score.max,
  }).catch(function() {});

  mostrarStep("step4");
  setProgress(100);
  renderResultado(score);
}

// ── Score ────────────────────────────────────────
function calcularScore() {
  let actual = 0;
  let potencial = 0;
  let max = CFG.puntos_max_total || 0;
  const mejoras = [];

  Object.values(STATE.respuestas).forEach(function(r) {
    if (r.esBloqueo) return;  // no suma al baremo
    actual += r.puntos || 0;
    if (r.influenciable && r.puntosMax > (r.puntos || 0)) {
      const ganancia = r.puntosMax - (r.puntos || 0);
      potencial += ganancia;
      mejoras.push({
        pregunta: r.preguntaLabel,
        puntos_ganables: ganancia,
      });
    }
  });

  return {
    actual: actual,
    potencial: actual + potencial,
    max: max,
    mejoras: mejoras,
  };
}

// ── Render resultado ─────────────────────────────
function renderResultado(score) {
  const container = document.getElementById("resultado-container");
  container.innerHTML = "";

  const empresa = STATE.empresa;

  // Veredicto
  let veredictoTexto;
  const pct = score.max > 0 ? score.actual / score.max : 0;
  if (pct >= 0.65) {
    veredictoTexto = CFG.textos.veredicto_alto;
  } else if (pct >= 0.35) {
    veredictoTexto = CFG.textos.veredicto_medio;
  } else {
    veredictoTexto = CFG.textos.veredicto_bajo;
  }
  veredictoTexto = veredictoTexto.replace(/\{empresa\}/g, empresa);

  // Card de resultado
  if (score.max > 0) {
    const card = document.createElement("div");
    card.className = "resultado-card";

    const empLabel = document.createElement("p");
    empLabel.className = "resultado-empresa";
    empLabel.textContent = empresa;
    card.appendChild(empLabel);

    const vText = document.createElement("p");
    vText.className = "veredicto-texto";
    vText.textContent = veredictoTexto;
    card.appendChild(vText);

    // Score display
    const scoreDisplay = document.createElement("div");
    scoreDisplay.className = "score-display";

    const boxActual = document.createElement("div");
    boxActual.className = "score-box";
    boxActual.innerHTML =
      '<div class="score-num">' + score.actual + '</div>' +
      '<div class="score-label">Puntuación estimada</div>';
    scoreDisplay.appendChild(boxActual);

    if (score.potencial > score.actual) {
      const boxPot = document.createElement("div");
      boxPot.className = "score-box potencial";
      boxPot.innerHTML =
        '<div class="score-num">' + score.potencial + '</div>' +
        '<div class="score-label">Potencial con Innóvate</div>';
      scoreDisplay.appendChild(boxPot);
    }

    card.appendChild(scoreDisplay);

    // Barra de progreso del score
    const barWrap = document.createElement("div");
    barWrap.className = "score-bar-wrap";
    const barInner = document.createElement("div");
    barInner.className = "score-bar-inner";
    const pctActual = score.max > 0 ? Math.round((score.actual / score.max) * 100) : 0;
    setTimeout(function() { barInner.style.width = pctActual + "%"; }, 100);
    barWrap.appendChild(barInner);
    card.appendChild(barWrap);

    if (score.potencial > score.actual) {
      const barWrap2 = document.createElement("div");
      barWrap2.className = "score-bar-wrap";
      barWrap2.style.marginTop = "4px";
      const barInner2 = document.createElement("div");
      barInner2.className = "score-bar-inner potencial";
      const pctPot = Math.round((score.potencial / score.max) * 100);
      setTimeout(function() { barInner2.style.width = Math.min(pctPot, 100) + "%"; }, 200);
      barWrap2.appendChild(barInner2);
      card.appendChild(barWrap2);

      const barLegend = document.createElement("p");
      barLegend.style.cssText = "font-size:0.75rem;color:rgba(29,37,76,0.55);margin-top:6px;";
      barLegend.textContent = "Puntuación sobre " + score.max + " puntos totales";
      card.appendChild(barLegend);
    }

    container.appendChild(card);
  } else {
    // Sin baremo — mostrar veredicto simple
    const card = document.createElement("div");
    card.className = "resultado-card";
    const empLabel = document.createElement("p");
    empLabel.className = "resultado-empresa";
    empLabel.textContent = empresa;
    card.appendChild(empLabel);
    const vText = document.createElement("p");
    vText.className = "veredicto-texto";
    vText.textContent = veredictoTexto;
    card.appendChild(vText);
    container.appendChild(card);
  }

  // Acciones de mejora
  if (score.mejoras && score.mejoras.length > 0) {
    const h = document.createElement("p");
    h.className = "section-header";
    h.textContent = "Criterios mejorables antes de solicitar";
    container.appendChild(h);

    const lista = document.createElement("ul");
    lista.className = "mejoras-lista";
    score.mejoras.forEach(function(m) {
      const li = document.createElement("li");
      li.innerHTML =
        '<strong>' + escHtml(m.pregunta) + '</strong>' +
        ' — hasta <strong>' + m.puntos_ganables + ' pt</strong> adicionales';
      lista.appendChild(li);
    });
    container.appendChild(lista);
  }

  // Calculadora de inversión
  const inv = CFG.inversion;
  if (inv) {
    const h = document.createElement("p");
    h.className = "section-header";
    h.textContent = "Estimación de la ayuda";
    container.appendChild(h);

    const calcBlock = document.createElement("div");
    calcBlock.className = "calc-block";

    const calcTitle = document.createElement("h3");
    calcTitle.textContent = "Calculadora de ayuda estimada";
    calcBlock.appendChild(calcTitle);

    const formula = document.createElement("p");
    formula.className = "calc-formula";
    formula.textContent = inv.formula_texto || "";
    calcBlock.appendChild(formula);

    if (inv.tiene_campo) {
      const field = document.createElement("div");
      field.className = "field";
      const lbl = document.createElement("label");
      lbl.setAttribute("for", "calc-inversion");
      lbl.textContent = inv.etiqueta_campo || "Inversión elegible prevista (€)";
      field.appendChild(lbl);
      const inp = document.createElement("input");
      inp.type = "number";
      inp.id = "calc-inversion";
      inp.placeholder = "Ej: 150000";
      inp.min = "0";
      inp.step = "1000";
      field.appendChild(inp);
      calcBlock.appendChild(field);

      const resultEl = document.createElement("div");
      resultEl.className = "calc-result";
      resultEl.id = "calc-result";
      resultEl.textContent = "";
      calcBlock.appendChild(resultEl);

      inp.addEventListener("input", function() {
        const val = parseFloat(inp.value) || 0;
        if (val <= 0) { resultEl.textContent = ""; return; }
        const pctMin = inv.pct_min || 0;
        const pctMax = inv.pct_max || 0;
        const tope = inv.tope_euros || Infinity;
        const ayudaMax = Math.min(val * pctMax / 100, tope);
        const ayudaMin = Math.min(val * pctMin / 100, tope);
        if (pctMin !== pctMax) {
          resultEl.textContent = "Ayuda estimada: " + formatEur(ayudaMin) + " – " + formatEur(ayudaMax);
        } else {
          resultEl.textContent = "Ayuda estimada: " + formatEur(ayudaMax);
        }
      });
    } else if (inv.importe_fijo) {
      const fixedEl = document.createElement("div");
      fixedEl.className = "calc-result";
      fixedEl.textContent = "Importe fijo: " + formatEur(inv.importe_fijo);
      calcBlock.appendChild(fixedEl);
    }

    container.appendChild(calcBlock);
  }

  // CTA
  const ctaBlock = document.createElement("div");
  ctaBlock.className = "cta-block";

  const ctaTitulo = document.createElement("h2");
  ctaTitulo.textContent = CFG.textos.cta_titulo;
  ctaBlock.appendChild(ctaTitulo);

  const ctaTexto = document.createElement("p");
  ctaTexto.textContent = CFG.textos.cta_texto;
  ctaBlock.appendChild(ctaTexto);

  const ctaBtn = document.createElement("a");
  ctaBtn.href = "https://innovate40.es/contacto/";
  ctaBtn.target = "_blank";
  ctaBtn.rel = "noopener noreferrer";
  ctaBtn.className = "btn btn-red";
  ctaBtn.textContent = "Hablar con un consultor";
  ctaBlock.appendChild(ctaBtn);

  container.appendChild(ctaBlock);

  // Nota fuente
  if (CFG.textos.nota_fuente) {
    const nota = document.createElement("p");
    nota.className = "nota-fuente";
    nota.textContent = CFG.textos.nota_fuente;
    container.appendChild(nota);
  }
}

// ── Helpers ──────────────────────────────────────
function mostrarStep(id) {
  document.querySelectorAll(".step").forEach(function(s) {
    s.classList.remove("active");
  });
  document.getElementById(id).classList.add("active");

  // Progress bar visible desde paso 2
  const pbWrap = document.getElementById("progress-bar-wrap");
  pbWrap.style.display = id === "step1" ? "none" : "block";

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function setProgress(pct) {
  document.getElementById("progress-bar-inner").style.width = pct + "%";
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatEur(n) {
  return Math.round(n).toLocaleString("es-ES") + " €";
}

async function enviarWeb3Forms(datos) {
  try {
    const payload = Object.assign({}, datos, {
      access_key: WEB3FORMS_KEY,
      subject: "[ConvoKit] " + CFG.titulo_corto + " — " + (datos.tipo || "lead"),
      from_name: "Evaluador Innóvate 4.0",
      email: datos.email || BACKUP_EMAIL,
    });
    await fetch("https://api.web3forms.com/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) {
    // Fail silently
  }
}
</script>
</body>
</html>"""


def build_output_6_html(config: dict) -> str:
    """
    Construye el HTML del evaluador sustituyendo los placeholders en la plantilla.

    - {{CONFIG_JSON}}: objeto JSON de configuración generado por Claude.
    - {{TITULO_EVALUADOR}}: título para la etiqueta <title>.
    """
    titulo = config.get("textos", {}).get("titulo_evaluador", "Evaluador de encaje")
    config_json = json.dumps(config, ensure_ascii=False, indent=2)

    html = _TEMPLATE.replace("{{CONFIG_JSON}}", config_json)
    html = html.replace("{{TITULO_EVALUADOR}}", titulo)
    return html
