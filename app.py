"""
Streamlit App — Sistema Experto Validador de Fotos
TP Análisis de Datos II · 2026

Deploy gratis en: https://streamlit.io/cloud
"""

import urllib.request
from io import BytesIO

import streamlit as st
from PIL import Image
from expert_system import evaluar
from streamlit_cropper import st_cropper

SCORE_INFO = {
    "foto_producto":       ("📦", "¿Se ve claramente el producto?",                    "> 0.12 → visible · 0.04–0.12 → parcial"),
    "tabla_talles":        ("📏", "¿Es una tabla de medidas/talles?",                  "> 0.50 → rechazar"),
    "lifestyle":           ("🧍", "¿Hay una persona o modelo en la foto?",             "> 0.40 → revisar / aprobar"),
    "marca_agua":          ("💧", "¿Tiene marca de agua o logo superpuesto?",          "> 0.55 → revisar"),
    "fondo_blanco":        ("⬜", "¿El fondo es blanco o neutro?",                     "> 0.35 → bonus calidad"),
    "baja_calidad":        ("🌫️", "¿La foto es borrosa u oscura?",                    "> 0.20 → rechazar"),
    "foto_detalle":        ("🔍", "¿Es un primer plano de textura/detalle?",           "> 0.25 → posible premium"),
    "multiple_productos":  ("🗂️", "¿Hay varios productos en la imagen?",              "> 0.50 → revisar"),
    "es_infografia":       ("📊", "¿Es un infográfico de características?",            "> 0.35 → rechazar"),
    "es_screenshot":       ("🖥️", "¿Es una captura de pantalla de un sitio?",         "> 0.35 → rechazar"),
    "datos_contacto":      ("📞", "¿Tiene teléfono, WhatsApp o redes superpuestos?",   "> 0.60 → rechazar"),
    "contenido_prohibido": ("🚫", "¿Tiene armas, drogas, odio u obscenidad?",          "> 0.20 sin persona · > 0.30 con persona → rechazar"),
    "es_documento":        ("🧾", "¿Es una factura, ticket o documento impreso?",       "> 0.30 → rechazar"),
}

RESULT_CSS = {
    "APROBAR ⭐⭐": ("aprobar-star", "🏆"),
    "APROBAR ⭐":  ("aprobar-star", "🌟"),
    "APROBAR":     ("aprobar",      "✅"),
    "REVISAR":     ("revisar",      "⚠️"),
    "RECHAZAR":    ("rechazar",     "❌"),
}

def css_for(res: str):
    for key, val in RESULT_CSS.items():
        if res.startswith(key):
            return val
    return ("rechazar", "❓")


st.set_page_config(
    page_title="SE Validador de Fotos",
    page_icon="📷",
    layout="wide",
)

st.markdown("""
<style>
/* ── Quitar padding superior de Streamlit ── */
#MainMenu, header, footer { visibility: hidden; height: 0; }
.block-container { padding-top: 0.4rem !important; padding-bottom: 1rem !important; }
section[data-testid="stSidebar"] { display: none; }
/* Quitar padding entre niveles de tabs */
.stTabs [data-baseweb="tab-panel"] { padding-top: 4px !important; }
div[data-testid="stTabsContent"] { padding-top: 0 !important; }
/* Tabs font size */
.stTabs [role="tablist"] { overflow-x: auto; white-space: nowrap; }
.stTabs [data-baseweb="tab"] { font-size: 21px !important; padding: 10px 18px !important; }
.stTabs [data-baseweb="tab"] p { font-size: 21px !important; }
@media (max-width: 768px) {
    .stTabs [role="tablist"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { font-size: 13px !important; padding: 6px 10px !important; }
    .stTabs [data-baseweb="tab"] p { font-size: 13px !important; }
    .block-container { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    .result-box { padding: 12px 14px !important; font-size: 15px !important; }
    .rule-chip { font-size: 11px !important; max-width: 100%; overflow-wrap: anywhere; }
}

.result-box  { padding: 16px 20px; border-radius: 10px; font-size: 18px; font-weight: bold; margin-top: 12px; }
.result-card { padding: 10px 14px; border-radius: 8px; font-size: 14px; font-weight: bold; margin-top: 6px; }
.aprobar     { background: #1b5e20; color: #a5d6a7; border-left: 5px solid #66bb6a; }
.aprobar-star{ background: #0d3b1e; color: #69f0ae; border-left: 5px solid #00e676; }
.revisar     { background: #e65100; color: #ffcc80; border-left: 5px solid #ffa726; }
.rechazar    { background: #b71c1c; color: #ef9a9a; border-left: 5px solid #ef5350; }
.rule-chip   { display: inline-block; background: #1e2d45; color: #90caf9; border-radius: 6px;
               padding: 2px 10px; margin: 2px; font-size: 12px; font-family: monospace; }
.summary-bar { background: #1e1e2e; border-radius: 10px; padding: 14px 20px; margin-bottom: 16px; font-size: 15px; }
</style>
""", unsafe_allow_html=True)

t_portada, t_problema, t_arq, t_sistema, t_evaluar, t_reglas, t_stack = st.tabs([
    "🎯 Portada", "💡 Problema & Objetivo", "⚙️ Arquitectura",
    "📋 El Sistema", "📸 Evaluar Foto", "⚙️ Reglas", "🛠️ Stack"
])



# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def render_scores(scores: dict):
    for label, val in scores.items():
        color = "🟢" if val > 0.6 else "🟡" if val > 0.35 else "🔴"
        emoji, descripcion, umbral = SCORE_INFO.get(label, ("", "", ""))
        st.progress(float(val), text=f"{color} **{label}**: {val:.3f}  {emoji} _{descripcion}_ · `{umbral}`")


def render_decision(resultado: dict, box_class="result-box"):
    res = resultado["resultado"]
    css, emoji = css_for(res)
    st.markdown(
        f'<div class="{box_class} {css}">{emoji} {res}<br>'
        f'<span style="font-size:13px;font-weight:400">{resultado["motivo"]}</span></div>',
        unsafe_allow_html=True,
    )


def render_rules(reglas: list):
    if reglas:
        html = "".join(
            f'<span class="rule-chip">{r["regla"]}: {r["condicion"]} → {r["hecho"]}</span>'
            for r in reglas
        )
        st.markdown(html, unsafe_allow_html=True)


def evaluar_con_spinner(img: Image.Image, label: str = ""):
    msg = f"⚙️ Procesando {label}..." if label else "⚙️ Procesando con CLIP + Motor de inferencia..."
    with st.spinner(msg):
        return evaluar(img)


# ──────────────────────────────────────────────
# TAB 0 — Presentación (sub-tabs)
# ──────────────────────────────────────────────

PRES_CSS = """
<style>
/* ── Base ── */
.p-page { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

/* ── PORTADA ── */
.cover-wrap {
    min-height: 80vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center; padding: 40px 20px;
}
.cover-client {
    display: flex; align-items: center; justify-content: center;
    gap: 10px; margin-bottom: 40px;
}
.cover-client-label {
    font-size: 16px; letter-spacing: 3px; text-transform: uppercase;
    color: #8b949e; margin-right: 4px;
}
.cover-divider { width: 1px; height: 28px; background: #30363d; margin: 0 12px; }

.visorai-name {
    font-size: 114px; font-weight: 900; line-height: 1;
    background: linear-gradient(135deg, #58a6ff 0%, #a5d8ff 50%, #388bfd 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 8px; letter-spacing: -3px;
}
.visorai-tagline {
    font-size: 29px; color: #8b949e; margin-bottom: 40px; font-weight: 400;
}
.cover-badges { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-bottom: 48px; }
.cbadge {
    background: #161b27; border: 1px solid #30363d; border-radius: 24px;
    padding: 8px 20px; font-size: 18px; color: #8b949e;
}
.cbadge b { color: #f0f6fc; }
.cover-uni {
    display: flex; align-items: center; gap: 16px;
    background: #161b27; border: 1px solid #21262d; border-radius: 12px;
    padding: 16px 28px; margin-top: 8px;
}
.cover-uni-text { text-align: left; }
.cover-uni-text .l1 { font-size: 20px; font-weight: 700; color: #f0f6fc; }
.cover-uni-text .l2 { font-size: 17px; color: #8b949e; margin-top: 2px; }

/* ── PROBLEMA ── */
.prob-hero {
    background: linear-gradient(135deg, #161b27, #0d1117);
    border: 1px solid #21262d; border-radius: 16px;
    padding: 40px; margin-bottom: 28px; text-align: center;
}
.prob-hero .ph-title { font-size: 57px; font-weight: 800; color: #f0f6fc; line-height: 1.2; margin-bottom: 14px; }
.prob-hero .ph-title span { color: #f0883e; }
.prob-hero .ph-sub { font-size: 23px; color: #8b949e; max-width: 600px; margin: 0 auto; line-height: 1.6; }

.pain-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 28px; }
.pain-card {
    background: #161b27; border: 1px solid #21262d; border-radius: 12px;
    padding: 24px; text-align: center;
}
.pain-icon { font-size: 52px; margin-bottom: 12px; }
.pain-title { font-size: 25px; font-weight: 700; color: #f0f6fc; margin-bottom: 8px; }
.pain-desc { font-size: 21px; color: #8b949e; line-height: 1.5; }

.obj-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.obj-item {
    background: #161b27; border: 1px solid #21262d; border-left: 3px solid #58a6ff;
    border-radius: 0 12px 12px 0; padding: 20px 22px;
    display: flex; align-items: flex-start; gap: 16px;
}
.obj-num { font-size: 42px; font-weight: 800; color: #58a6ff; line-height: 1; flex-shrink: 0; }
.obj-text .ot { font-size: 23px; font-weight: 700; color: #f0f6fc; margin-bottom: 6px; }
.obj-text .od { font-size: 20px; color: #8b949e; line-height: 1.5; }

/* ── ARQUITECTURA ── */
.arch-title { font-size: 62px; font-weight: 800; color: #f0f6fc; margin-bottom: 8px; }
.arch-title span { color: #58a6ff; }
.arch-sub { font-size: 25px; color: #8b949e; margin-bottom: 32px; }
.arch-flow-big {
    display: flex; align-items: stretch; justify-content: center;
    gap: 0; margin-bottom: 32px; flex-wrap: wrap;
}
.afb {
    background: #161b27; border: 1px solid #30363d; border-radius: 12px;
    padding: 22px 18px; text-align: center; min-width: 130px; flex: 1;
}
.afb .af-icon { font-size: 47px; display: block; margin-bottom: 10px; }
.afb .af-name { font-size: 23px; font-weight: 700; color: #f0f6fc; display: block; margin-bottom: 6px; }
.afb .af-tech { font-size: 18px; color: #58a6ff; display: block; }
.af-arrow { display: flex; align-items: center; color: #30363d; font-size: 31px; padding: 0 8px; }

.two-engine { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
.engine-card {
    background: #161b27; border: 1px solid #21262d; border-radius: 14px; padding: 30px;
}
.engine-card .ec-type { font-size: 17px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 10px; font-weight: 700; }
.engine-card .ec-name { font-size: 42px; font-weight: 800; color: #f0f6fc; margin-bottom: 12px; }
.engine-card .ec-desc { font-size: 22px; color: #8b949e; line-height: 1.7; }
.engine-card .ec-tags { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; }
.engine-card .ec-tag {
    background: #0d1117; border: 1px solid #30363d; border-radius: 6px;
    padding: 5px 14px; font-size: 18px; color: #8b949e;
}

.cycles { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.cycle-card {
    background: #0d1117; border: 1px solid #21262d; border-radius: 12px; padding: 28px;
}
.cycle-card .cc-num { font-size: 73px; font-weight: 900; line-height: 1; margin-bottom: 6px; }
.cycle-card .cc-title { font-size: 26px; font-weight: 700; color: #f0f6fc; margin-bottom: 10px; }
.cycle-card .cc-desc { font-size: 21px; color: #8b949e; line-height: 1.6; }
.cycle-card .cc-arrow { font-size: 20px; color: #58a6ff; margin-top: 10px; font-family: monospace; }

/* ── SISTEMA ── */
.kpi-big { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 32px; }
.kpib {
    background: #161b27; border: 1px solid #21262d; border-radius: 14px;
    padding: 28px 20px; text-align: center;
}
.kpib .kn { font-size: 83px; font-weight: 900; line-height: 1; margin-bottom: 6px; }
.kpib .kl { font-size: 20px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; }
.c-blue{color:#58a6ff} .c-green{color:#3fb950} .c-purple{color:#bc8cff} .c-orange{color:#f0883e}

.labels-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 14px; margin-bottom: 28px; }
.label-row {
    background: #161b27; border: 1px solid #21262d; border-radius: 12px;
    padding: 20px 24px; display: flex; align-items: center; gap: 18px;
}
.label-emoji { font-size: 44px; flex-shrink: 0; }
.label-name { font-size: 26px; font-weight: 700; color: #f0f6fc; font-family: monospace; }
.label-desc { font-size: 21px; color: #8b949e; margin-top: 4px; }
.label-action { font-size: 18px; margin-top: 5px; font-weight: 600; }
.la-reject{color:#f85149} .la-review{color:#f0883e} .la-ok{color:#3fb950}

.decision-list { display: flex; flex-direction: column; gap: 12px; }
.dec-item {
    padding: 20px 24px; border-radius: 10px; display: flex; align-items: center; gap: 16px;
}
.dec-em { font-size: 36px; flex-shrink: 0; }
.dec-name { font-size: 26px; font-weight: 800; }
.dec-desc { font-size: 20px; opacity: 0.8; margin-top: 3px; }
.d-approve2{background:#0d3b1e;border-left:4px solid #00e676;}
.d-approve1{background:#1b5e20;border-left:4px solid #66bb6a;}
.d-approve0{background:#1b4020;border-left:4px solid #4caf50;}
.d-review{background:#3e1f00;border-left:4px solid #ffa726;}
.d-reject{background:#3b0d0d;border-left:4px solid #f85149;}

/* ── EQUIPO ── */
.team-cover {
    background: linear-gradient(135deg, #161b27, #0d1117);
    border: 1px solid #21262d; border-radius: 16px;
    padding: 40px; margin-bottom: 28px; text-align: center;
}
.team-cover .tc-title { font-size: 55px; font-weight: 800; color: #f0f6fc; margin-bottom: 8px; }
.team-cover .tc-sub { font-size: 21px; color: #8b949e; }
.team-big-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 16px; margin-bottom: 28px; }
.tcard {
    background: #161b27; border: 1px solid #21262d; border-radius: 14px;
    padding: 28px 20px; text-align: center;
}
.tcard .tav {
    width: 64px; height: 64px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 29px; font-weight: 800; color: #fff;
    margin: 0 auto 14px;
}
.tcard .tn { font-size: 21px; font-weight: 700; color: #f0f6fc; margin-bottom: 4px; }
.tcard .tg { font-size: 17px; color: #8b949e; }
.uni-footer {
    background: #161b27; border: 1px solid #21262d; border-radius: 14px;
    padding: 24px 32px; display: flex; align-items: center; gap: 24px;
}
.uf-text .uft1 { font-size: 21px; font-weight: 700; color: #f0f6fc; margin-bottom: 4px; }
.uf-text .uft2 { font-size: 18px; color: #8b949e; }

/* ── Sección header ── */
.sec-hdr {
    font-size: 16px; letter-spacing: 3px; text-transform: uppercase;
    color: #58a6ff; font-weight: 700; margin-bottom: 20px;
    padding-bottom: 10px; border-bottom: 1px solid #21262d;
}

/* ── RESPONSIVE MOBILE ── */
@media (max-width: 768px) {
    /* Portada */
    .visorai-big { font-size: 58px !important; letter-spacing: -2px !important; }
    .visorai-tagline-big { font-size: 18px !important; }
    .visorai-tp-detail { font-size: 13px !important; }
    .pbadge { font-size: 13px !important; padding: 6px 12px !important; }
    .ptag { font-size: 13px !important; padding: 5px 12px !important; }
    .portada-uni { flex-direction: column; text-align: center; }
    .portada-uni-text .ul1 { font-size: 14px !important; }
    .portada-uni-text .ul2 { font-size: 12px !important; }

    /* Problema */
    .prob-hero .ph-title { font-size: 28px !important; }
    .prob-hero .ph-sub { font-size: 15px !important; }
    .pain-grid { grid-template-columns: 1fr !important; }
    .pain-title { font-size: 17px !important; }
    .pain-desc { font-size: 14px !important; }
    .obj-grid { grid-template-columns: 1fr !important; }
    .obj-text .ot { font-size: 15px !important; }
    .obj-text .od { font-size: 13px !important; }

    /* Arquitectura */
    .arch-title { font-size: 30px !important; }
    .arch-sub { font-size: 14px !important; }
    .arch-flow-big { flex-direction: column !important; align-items: stretch !important; }
    .af-arrow { transform: rotate(90deg); align-self: center; }
    .two-engine { grid-template-columns: 1fr !important; }
    .engine-card .ec-name { font-size: 22px !important; }
    .engine-card .ec-desc { font-size: 14px !important; }
    .engine-card .ec-type { font-size: 11px !important; }
    .engine-card .ec-tag { font-size: 12px !important; }
    .cycles { grid-template-columns: 1fr !important; }
    .cycle-card .cc-num { font-size: 44px !important; }
    .cycle-card .cc-title { font-size: 17px !important; }
    .cycle-card .cc-desc { font-size: 13px !important; }

    /* El Sistema */
    .kpi-big { grid-template-columns: repeat(2, 1fr) !important; }
    .kpib .kn { font-size: 44px !important; }
    .kpib .kl { font-size: 12px !important; }
    .labels-grid { grid-template-columns: 1fr !important; }
    .label-name { font-size: 15px !important; }
    .label-desc { font-size: 13px !important; }
    .label-action { font-size: 12px !important; }
    .dec-name { font-size: 17px !important; }
    .dec-desc { font-size: 13px !important; }

    /* Navegación */
}
</style>
"""


# ── PORTADA ──
with t_portada:
    st.markdown(PRES_CSS, unsafe_allow_html=True)
    st.markdown("""
<style>
.portada {
    display: flex; flex-direction: column; align-items: center;
    text-align: center; padding: 20px 20px 24px;
}
.visorai-big {
    font-size: 170px; font-weight: 900; line-height: 1;
    background: linear-gradient(135deg, #58a6ff 0%, #c0e0ff 55%, #388bfd 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; letter-spacing: -7px; margin-bottom: 8px;
}
.visorai-tagline-big { font-size: 36px; color: #8b949e; margin-bottom: 10px; font-weight: 400; }
.visorai-tp-detail {
    font-size: 23px; color: #388bfd; margin-bottom: 36px; font-style: italic;
}
.portada-badges { display: flex; flex-wrap: wrap; justify-content: center; gap: 12px; margin-bottom: 28px; }
.pbadge {
    background: #161b27; border: 1px solid #30363d; border-radius: 24px;
    padding: 10px 24px; font-size: 22px; color: #8b949e;
}
.pbadge b { color: #f0f6fc; }
.portada-team {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 12px;
    margin-bottom: 28px;
}
.ptag {
    background: #161b27; border: 1px solid #21262d; border-radius: 24px;
    padding: 9px 22px; font-size: 22px; color: #c9d1d9;
}
.portada-uni {
    display: flex; align-items: center; gap: 24px;
    background: #161b27; border: 1px solid #21262d; border-radius: 16px;
    padding: 22px 32px; margin-top: 4px;
}
.portada-uni-text .ul1 { font-size: 23px; font-weight: 700; color: #f0f6fc; }
.portada-uni-text .ul2 { font-size: 19px; color: #8b949e; margin-top: 4px; }
</style>

<div class="portada">

  <svg width="130" height="130" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg" style="margin-bottom:18px">
    <defs>
      <linearGradient id="bg-g" x1="0" y1="0" x2="130" y2="130" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#1a2540"/>
        <stop offset="100%" stop-color="#0d1117"/>
      </linearGradient>
      <linearGradient id="sh-g" x1="20" y1="10" x2="110" y2="120" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#79c0ff"/>
        <stop offset="100%" stop-color="#1f6feb"/>
      </linearGradient>
      <radialGradient id="lens-g" cx="50%" cy="45%" r="50%">
        <stop offset="0%" stop-color="#388bfd" stop-opacity="0.9"/>
        <stop offset="100%" stop-color="#1f6feb" stop-opacity="0.4"/>
      </radialGradient>
    </defs>
    <rect width="130" height="130" rx="30" fill="url(#bg-g)"/>
    <path d="M65 10 L108 28 V65 C108 88 88 106 65 116 C42 106 22 88 22 65 V28 Z"
          fill="#1f6feb" fill-opacity="0.12" stroke="url(#sh-g)" stroke-width="2.5"/>
    <circle cx="65" cy="66" r="26" stroke="url(#sh-g)" stroke-width="3" fill="none"/>
    <circle cx="65" cy="66" r="16" fill="url(#lens-g)"/>
    <circle cx="65" cy="66" r="6" fill="#79c0ff"/>
    <circle cx="57" cy="58" r="4" fill="white" fill-opacity="0.25"/>
    <line x1="65" y1="40" x2="65" y2="46" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="65" y1="86" x2="65" y2="92" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="39" y1="66" x2="45" y2="66" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/>
    <line x1="85" y1="66" x2="91" y2="66" stroke="#388bfd" stroke-width="2.5" stroke-linecap="round"/>
  </svg>

  <div class="visorai-big">VisorAI</div>
  <div class="visorai-tagline-big">Validación inteligente de fotos de producto</div>
  <div class="visorai-tp-detail">IA Híbrida · CLIP + Experta RBES · Forward Chaining · 13 labels · 38 reglas</div>

  <div class="portada-badges">
    <span class="pbadge">📅 <b>4 de junio, 2026</b></span>
    <span class="pbadge">📘 <b>ASIG00131</b> — Análisis de Datos II</span>
    <span class="pbadge">👨‍🏫 Prof. <b>Agustín Asuaje</b></span>
    <span class="pbadge">🏛️ Ciencias de Datos · 1/2026</span>
  </div>

  <div class="portada-team">
    <span class="ptag">Carina Acosta</span>
    <span class="ptag">Tomás Ramírez</span>
    <span class="ptag">Carlos Mercuri</span>
    <span class="ptag">Lourdes Reynaldo</span>
    <span class="ptag">Alex Surco Garnica</span>
    <span class="ptag">Sebastián Gines</span>
  </div>

  <div class="portada-uni">
    <img src="https://campus.udelaciudad.edu.ar/pluginfile.php/1/theme_universidadelaciudad/logo/1774038663/Udelaciudad-logo-preferencial_de%20Bs%20As.png"
         height="50" style="filter:brightness(0) invert(1);opacity:0.9;flex-shrink:0;">
    <div class="portada-uni-text">
      <div class="ul1">Universidad de la Ciudad de Buenos Aires</div>
      <div class="ul2">Sistemas Expertos y Redes de Conocimiento · Grupo B</div>
    </div>
  </div>

</div>
""", unsafe_allow_html=True)


# ── PROBLEMA & OBJETIVO ──
with t_problema:
    st.markdown(PRES_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="p-page">
<div style="text-align:right;margin-bottom:12px;display:flex;align-items:center;justify-content:flex-end;gap:8px">
  <svg width="22" height="22" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg">
    <rect width="130" height="130" rx="30" fill="#1a2540"/>
    <path d="M65 10 L108 28 V65 C108 88 88 106 65 116 C42 106 22 88 22 65 V28 Z" fill="#1f6feb" fill-opacity="0.2" stroke="#388bfd" stroke-width="3"/>
    <circle cx="65" cy="66" r="26" stroke="#388bfd" stroke-width="3" fill="none"/>
    <circle cx="65" cy="66" r="10" fill="#388bfd" opacity="0.8"/>
    <circle cx="65" cy="66" r="5" fill="#79c0ff"/>
  </svg>
  <span style="font-size:15px;font-weight:800;color:#30363d;letter-spacing:1px">VISOR<span style="color:#1f6feb">AI</span></span>
</div>

<div class="prob-hero">
  <div class="ph-title">El problema de las<br><span>malas fotos</span> en e-commerce</div>
  <div class="ph-sub">
    Cada día se publican miles de productos con imágenes que no cumplen
    los estándares mínimos. La revisión manual no escala, y las malas fotos
    cuestan conversiones, confianza y reputación de plataforma.
  </div>
</div>

<div class="sec-hdr">Tipos de violaciones más frecuentes</div>
<div class="pain-grid">
  <div class="pain-card">
    <div class="pain-icon">🧍</div>
    <div class="pain-title">Fotos con personas</div>
    <div class="pain-desc">Selfies, lifestyle y fotos familiares subidas como imagen del producto</div>
  </div>
  <div class="pain-card">
    <div class="pain-icon">📞</div>
    <div class="pain-title">Datos de contacto</div>
    <div class="pain-desc">Teléfonos, WhatsApp e Instagram superpuestos para evadir la comisión de la plataforma</div>
  </div>
  <div class="pain-card">
    <div class="pain-icon">🚫</div>
    <div class="pain-title">Contenido prohibido</div>
    <div class="pain-desc">Armas, alcohol, drogas o símbolos de odio publicados como producto</div>
  </div>
  <div class="pain-card">
    <div class="pain-icon">📏</div>
    <div class="pain-title">Tablas de talles</div>
    <div class="pain-desc">Imágenes de medidas usadas como foto principal del producto</div>
  </div>
  <div class="pain-card">
    <div class="pain-icon">🌫️</div>
    <div class="pain-title">Baja calidad</div>
    <div class="pain-desc">Fotos borrosas, oscuras o tomadas en condiciones inadecuadas</div>
  </div>
  <div class="pain-card">
    <div class="pain-icon">🧾</div>
    <div class="pain-title">Facturas y documentos</div>
    <div class="pain-desc">Recibos, tickets y manuales subidos en lugar de fotos del producto</div>
  </div>
</div>

<div class="sec-hdr">Objetivos del sistema VisorAI</div>
<div class="obj-grid">
  <div class="obj-item">
    <div class="obj-num">01</div>
    <div class="obj-text">
      <div class="ot">Automatizar la validación</div>
      <div class="od">Clasificar imágenes en tiempo real sin intervención humana para el flujo estándar</div>
    </div>
  </div>
  <div class="obj-item">
    <div class="obj-num">02</div>
    <div class="obj-text">
      <div class="ot">Detectar violaciones de política</div>
      <div class="od">Identificar contenido prohibido, datos de contacto, baja calidad y fotos no aptas</div>
    </div>
  </div>
  <div class="obj-item">
    <div class="obj-num">03</div>
    <div class="obj-text">
      <div class="ot">Premiar la calidad</div>
      <div class="od">Reconocer fotos profesionales con fondo neutro o detalle macro para mejor posicionamiento</div>
    </div>
  </div>
  <div class="obj-item">
    <div class="obj-num">04</div>
    <div class="obj-text">
      <div class="ot">Explicar cada decisión</div>
      <div class="od">Proveer trazabilidad completa: qué regla disparó y por qué, para auditoría y apelación</div>
    </div>
  </div>
</div>

</div>
""", unsafe_allow_html=True)

# ── ARQUITECTURA ──
with t_arq:
    st.markdown(PRES_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="p-page">
<div style="text-align:right;margin-bottom:12px;display:flex;align-items:center;justify-content:flex-end;gap:8px">
  <svg width="22" height="22" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg">
    <rect width="130" height="130" rx="30" fill="#1a2540"/>
    <path d="M65 10 L108 28 V65 C108 88 88 106 65 116 C42 106 22 88 22 65 V28 Z" fill="#1f6feb" fill-opacity="0.2" stroke="#388bfd" stroke-width="3"/>
    <circle cx="65" cy="66" r="26" stroke="#388bfd" stroke-width="3" fill="none"/>
    <circle cx="65" cy="66" r="10" fill="#388bfd" opacity="0.8"/>
    <circle cx="65" cy="66" r="5" fill="#79c0ff"/>
  </svg>
  <span style="font-size:15px;font-weight:800;color:#30363d;letter-spacing:1px">VISOR<span style="color:#1f6feb">AI</span></span>
</div>

<div style="text-align:center; margin-bottom:32px">
  <div class="arch-title">Arquitectura <span>Híbrida</span></div>
  <div class="arch-sub">IA Simbólica + IA Subsimbólica — dos motores, una decisión</div>
</div>

<div class="arch-flow-big" style="margin-bottom:32px">
  <div class="afb">
    <span class="af-icon">🖼️</span>
    <span class="af-name">Imagen</span>
    <span class="af-tech">Archivo · Cámara · URL</span>
  </div>
  <div class="af-arrow">→</div>
  <div class="afb" style="border-color:#388bfd">
    <span class="af-icon">🧠</span>
    <span class="af-name">CLIP ViT-B/32</span>
    <span class="af-tech">Zero-shot · 13 labels</span>
  </div>
  <div class="af-arrow">→</div>
  <div class="afb">
    <span class="af-icon">📊</span>
    <span class="af-name">Scores</span>
    <span class="af-tech">Similitud independiente · [0, 1]</span>
  </div>
  <div class="af-arrow">→</div>
  <div class="afb" style="border-color:#bc8cff">
    <span class="af-icon">⚙️</span>
    <span class="af-name">Motor Experta</span>
    <span class="af-tech">RBES · Forward Chaining</span>
  </div>
  <div class="af-arrow">→</div>
  <div class="afb" style="border-color:#3fb950">
    <span class="af-icon">✅</span>
    <span class="af-name">Decisión</span>
    <span class="af-tech">Resultado + Trazabilidad</span>
  </div>
</div>

<div class="sec-hdr">Los dos motores</div>
<div class="two-engine">
  <div class="engine-card">
    <div class="ec-type" style="color:#58a6ff">IA Subsimbólica · Aprendizaje profundo</div>
    <div class="ec-name">CLIP ViT-B/32</div>
    <div class="ec-desc">
      Modelo de visión-lenguaje de OpenAI preentrenado sobre 400 millones de pares imagen-texto.
      Compara la imagen con 13 descripciones en lenguaje natural y genera un score de similitud
      para cada una mediante <b>zero-shot classification</b> — sin necesidad de entrenamiento adicional.
    </div>
    <div class="ec-tags">
      <span class="ec-tag">Zero-shot</span>
      <span class="ec-tag">Vision Transformer</span>
      <span class="ec-tag">Embeddings</span>
      <span class="ec-tag">Sigmoid calibrado</span>
      <span class="ec-tag">OpenAI</span>
    </div>
  </div>
  <div class="engine-card">
    <div class="ec-type" style="color:#bc8cff">IA Simbólica · Sistema basado en reglas</div>
    <div class="ec-name">Experta RBES</div>
    <div class="ec-desc">
      Motor de inferencia con <b>Forward Chaining</b>: parte de los scores CLIP como hechos,
      aplica 38 reglas organizadas en dos ciclos y deriva la decisión final.
      Cada regla es interpretable, auditable y modificable sin reentrenamiento.
    </div>
    <div class="ec-tags">
      <span class="ec-tag">Forward Chaining</span>
      <span class="ec-tag">Salience</span>
      <span class="ec-tag">Hechos</span>
      <span class="ec-tag">38 reglas</span>
      <span class="ec-tag">Python</span>
    </div>
  </div>
</div>

<div class="sec-hdr">Dos ciclos de inferencia</div>
<div class="cycles">
  <div class="cycle-card">
    <div class="cc-num" style="color:#58a6ff">01</div>
    <div class="cc-title">Scores → Hechos intermedios</div>
    <div class="cc-desc">
      15 reglas con salience=100 convierten cada score CLIP en un hecho concreto
      del dominio: <em>ProductoVisible</em>, <em>EsTabla</em>, <em>BajaCalidad</em>,
      <em>ContenidoProhibido</em>, etc.
    </div>
    <div class="cc-arrow">foto_producto > 0.55  →  ProductoVisible</div>
  </div>
  <div class="cycle-card">
    <div class="cc-num" style="color:#bc8cff">02</div>
    <div class="cc-title">Hechos → Decisión final</div>
    <div class="cc-desc">
      21 reglas combinan los hechos intermedios usando lógica proposicional
      y salience para resolver conflictos. Contenido prohibido (35) siempre
      gana sobre calidad de foto (1).
    </div>
    <div class="cc-arrow">ContenidoProhibido  →  RECHAZAR  [s=35]</div>
  </div>
</div>

</div>
""", unsafe_allow_html=True)

# ── EL SISTEMA ──
with t_sistema:
    st.markdown(PRES_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="p-page">
<div style="text-align:right;margin-bottom:12px;display:flex;align-items:center;justify-content:flex-end;gap:8px">
  <svg width="22" height="22" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg">
    <rect width="130" height="130" rx="30" fill="#1a2540"/>
    <path d="M65 10 L108 28 V65 C108 88 88 106 65 116 C42 106 22 88 22 65 V28 Z" fill="#1f6feb" fill-opacity="0.2" stroke="#388bfd" stroke-width="3"/>
    <circle cx="65" cy="66" r="26" stroke="#388bfd" stroke-width="3" fill="none"/>
    <circle cx="65" cy="66" r="10" fill="#388bfd" opacity="0.8"/>
    <circle cx="65" cy="66" r="5" fill="#79c0ff"/>
  </svg>
  <span style="font-size:15px;font-weight:800;color:#30363d;letter-spacing:1px">VISOR<span style="color:#1f6feb">AI</span></span>
</div>

<div class="kpi-big">
  <div class="kpib"><div class="kn c-blue">13</div><div class="kl">Labels CLIP</div></div>
  <div class="kpib"><div class="kn c-green">38</div><div class="kl">Reglas activas</div></div>
  <div class="kpib"><div class="kn c-purple">2</div><div class="kl">Ciclos de inferencia</div></div>
  <div class="kpib"><div class="kn c-orange">5</div><div class="kl">Decisiones posibles</div></div>
</div>

<div class="sec-hdr">Labels CLIP — 13 dimensiones de análisis</div>
<div class="labels-grid">
  <div class="label-row">
    <div class="label-emoji">📦</div>
    <div><div class="label-name">foto_producto</div><div class="label-desc">Producto claramente visible</div><div class="label-action la-ok">› base para aprobar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🧍</div>
    <div><div class="label-name">lifestyle</div><div class="label-desc">Persona o modelo en la imagen</div><div class="label-action la-review">› aprobar / revisar / rechazar según producto</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">📏</div>
    <div><div class="label-name">tabla_talles</div><div class="label-desc">Tabla de medidas con números</div><div class="label-action la-reject">› rechazar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">💧</div>
    <div><div class="label-name">marca_agua</div><div class="label-desc">Marca de agua o logo superpuesto</div><div class="label-action la-review">› revisar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">⬜</div>
    <div><div class="label-name">fondo_blanco</div><div class="label-desc">Fondo blanco o neutro profesional</div><div class="label-action la-ok">› bonus calidad ⭐</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🌫️</div>
    <div><div class="label-name">baja_calidad</div><div class="label-desc">Foto borrosa, oscura o pixelada</div><div class="label-action la-reject">› rechazar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🔍</div>
    <div><div class="label-name">foto_detalle</div><div class="label-desc">Primer plano de textura o detalle</div><div class="label-action la-ok">› bonus calidad ⭐⭐</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🗂️</div>
    <div><div class="label-name">multiple_productos</div><div class="label-desc">Collage con varios productos</div><div class="label-action la-review">› revisar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">📊</div>
    <div><div class="label-name">es_infografia</div><div class="label-desc">Infográfico de características</div><div class="label-action la-reject">› rechazar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🖥️</div>
    <div><div class="label-name">es_screenshot</div><div class="label-desc">Captura de pantalla de un sitio</div><div class="label-action la-reject">› rechazar</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">📞</div>
    <div><div class="label-name">datos_contacto</div><div class="label-desc">Teléfono, WhatsApp o redes sociales</div><div class="label-action la-reject">› rechazar [s=30, umbral 0.75]</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🚫</div>
    <div><div class="label-name">contenido_prohibido</div><div class="label-desc">Armas, drogas, odio, obscenidad</div><div class="label-action la-reject">› rechazar [s=35]</div></div>
  </div>
  <div class="label-row">
    <div class="label-emoji">🧾</div>
    <div><div class="label-name">es_documento</div><div class="label-desc">Factura, ticket o documento impreso</div><div class="label-action la-reject">› rechazar [s=22]</div></div>
  </div>
</div>

<div class="sec-hdr">Decisiones posibles</div>
<div class="decision-list">
  <div class="dec-item d-approve2">
    <div class="dec-em">🏆</div>
    <div><div class="dec-name" style="color:#00e676">APROBAR ⭐⭐</div><div class="dec-desc">Foto de detalle profesional sobre fondo neutro — calidad premium</div></div>
  </div>
  <div class="dec-item d-approve1">
    <div class="dec-em">🌟</div>
    <div><div class="dec-name" style="color:#69f0ae">APROBAR ⭐</div><div class="dec-desc">Producto destacado sobre fondo neutro — calidad óptima</div></div>
  </div>
  <div class="dec-item d-approve0">
    <div class="dec-em">✅</div>
    <div><div class="dec-name" style="color:#a5d6a7">APROBAR</div><div class="dec-desc">Foto válida del producto sin observaciones</div></div>
  </div>
  <div class="dec-item d-review">
    <div class="dec-em">⚠️</div>
    <div><div class="dec-name" style="color:#ffcc80">REVISAR</div><div class="dec-desc">Foto con observaciones — requiere revisión humana</div></div>
  </div>
  <div class="dec-item d-reject">
    <div class="dec-em">❌</div>
    <div><div class="dec-name" style="color:#f85149">RECHAZAR</div><div class="dec-desc">Foto no apta — viola política o no muestra el producto</div></div>
  </div>
</div>

</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# EVALUAR FOTO
# ──────────────────────────────────────────────
with t_evaluar:
    st.markdown("""
<style>
.eval-decision {
    padding: 28px 32px; border-radius: 14px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 20px;
}
.eval-decision .ed-emoji { font-size: 52px; flex-shrink: 0; }
.eval-decision .ed-result { font-size: 42px; font-weight: 900; line-height: 1.1; }
.eval-decision .ed-motivo { font-size: 20px; font-weight: 400; margin-top: 6px; opacity: 0.85; }
.eval-score-row { font-size: 17px; margin-bottom: 4px; }
.eval-section-hdr { font-size: 20px; font-weight: 700; color: #f0f6fc; margin: 20px 0 10px; }
.eval-rule-chip {
    display: inline-block; background: #1e2d45; color: #90caf9; border-radius: 6px;
    padding: 4px 14px; margin: 3px; font-size: 15px; font-family: monospace;
    max-width: 100%; overflow-wrap: anywhere;
}
@media (max-width: 768px) {
    .eval-decision {
        padding: 16px 18px !important;
        gap: 12px !important;
        align-items: flex-start !important;
    }
    .eval-decision .ed-emoji { font-size: 34px !important; }
    .eval-decision .ed-result { font-size: 26px !important; }
    .eval-decision .ed-motivo { font-size: 14px !important; }
    .eval-section-hdr { font-size: 16px !important; }
    .eval-rule-chip { font-size: 12px !important; padding: 3px 8px !important; }
}
</style>
""", unsafe_allow_html=True)

    modo = st.radio("Fuente:", ["📁 Archivo", "📷 Cámara", "🔗 URL"], horizontal=True)

    img, nombre, usar_cropper = None, "", False

    if modo == "📁 Archivo":
        archivo = st.file_uploader("Seleccioná una imagen", type=["jpg", "jpeg", "png", "webp"])
        if archivo:
            img = Image.open(archivo).convert("RGB")
            nombre = archivo.name

    elif modo == "📷 Cámara":
        foto = st.camera_input("Apuntá al producto y sacá la foto")
        if foto:
            img = Image.open(foto).convert("RGB")
            nombre = "foto_camara.jpg"
            usar_cropper = True

    elif modo == "🔗 URL":
        url = st.text_input("URL de la imagen:")
        if url and st.button("Cargar"):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    img = Image.open(BytesIO(r.read())).convert("RGB")
                nombre = url.split("/")[-1]
            except Exception as e:
                st.error(f"No se pudo cargar: {e}")

    if img:
        col_foto, col_result = st.columns([1, 1])
        with col_foto:
            if usar_cropper:
                st.caption("✂️ Encuadrá el producto antes de evaluar")
                img_eval = st_cropper(
                    img,
                    realtime_update=True,
                    box_color="#388bfd",
                    aspect_ratio=None,
                )
            else:
                st.image(img, width="stretch", caption=nombre)
                img_eval = img
        with col_result:
            resultado = evaluar_con_spinner(img_eval)
            res = resultado["resultado"]
            css, emoji = css_for(res)

            st.markdown(
                f'<div class="eval-decision {css}">'
                f'  <div class="ed-emoji">{emoji}</div>'
                f'  <div>'
                f'    <div class="ed-result">{res}</div>'
                f'    <div class="ed-motivo">{resultado["motivo"]}</div>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if resultado["reglas"]:
                st.markdown('<div class="eval-section-hdr">Reglas disparadas</div>', unsafe_allow_html=True)
                html = "".join(
                    f'<span class="eval-rule-chip">{r["regla"]}: {r["condicion"]} → {r["hecho"]}</span>'
                    for r in resultado["reglas"]
                )
                st.markdown(html, unsafe_allow_html=True)

            with st.expander("📊 Ver scores CLIP detallados"):
                render_scores(resultado["scores"])
    else:
        st.info("👆 Elegí una imagen para evaluarla")


# ──────────────────────────────────────────────
# REGLAS
# ──────────────────────────────────────────────
with t_reglas:
    st.subheader("Base de Reglas — Forward Chaining")
    st.caption("38 reglas en dos ciclos: Scores → Hechos y Hechos → Decisión")

    st.markdown("### Ciclo 1 — Scores → Hechos intermedios (salience=100)")
    st.table({
        "ID":             ["R1p","R1","R1b","R2","R3","R4","R5","R6","R7","R7b","R7c","R8","R8b","R8d","R8c"],
        "Condición":      [
            "foto_producto > 0.80",
            "foto_producto > 0.55",
            "0.45 < foto_producto ≤ 0.55",
            "tabla_talles > 0.50",
            "lifestyle > 0.20",
            "marca_agua > 0.55",
            "baja_calidad > 0.50",
            "fondo_blanco > 0.60",
            "foto_detalle > 0.25",
            "es_infografia > 0.35",
            "es_screenshot > 0.35",
            "multiple_productos > 0.50",
            "datos_contacto > 0.60",
            "es_documento > 0.30",
            "contenido_prohibido > 0.75",
        ],
        "Hecho generado": [
            "ProductoDestacado","ProductoVisible","ProductoParcial","EsTabla","EsLifestyle","TieneWatermark",
            "BajaCalidad","FondoProfesional","FotoDetalle","EsInfografia","EsScreenshot",
            "MultipleProductos","TieneDatosContacto","EsDocumento","ContenidoProhibido",
        ],
    })

    st.markdown("### Ciclo 2 — Hechos → Decisión")
    st.table({
        "ID":         ["R_PROHIBIDO","R_CONTACTO","R14b","R_DOC","R9","R10","R10b","R10c","R11","R15","R12b","R12","R13","R14","R16b","R16","R17"],
        "Condición":  [
            "ContenidoProhibido",
            "TieneDatosContacto",
            "EsScreenshot",
            "EsDocumento",
            "EsTabla",
            "EsLifestyle ∧ ¬ProductoVisible",
            "EsLifestyle ∧ ProductoVisible ∧ ¬ProductoDestacado",
            "EsLifestyle ∧ ProductoDestacado",
            "BajaCalidad",
            "EsInfografia",
            "ProductoParcial ∧ ¬problemas",
            "MultipleProductos ∧ ¬EsTabla",
            "¬ProductoVisible ∧ ¬ProductoParcial ∧ ...",
            "ProductoVisible ∧ TieneWatermark ∧ ...",
            "ProductoDestacado ∧ FotoDetalle ∧ FondoProfesional",
            "ProductoDestacado ∧ FondoProfesional ∧ ...",
            "ProductoVisible ∧ ¬problemas",
        ],
        "Decisión":   [
            "❌ RECHAZAR","❌ RECHAZAR","❌ RECHAZAR","❌ RECHAZAR","❌ RECHAZAR","❌ RECHAZAR",
            "⚠️ REVISAR","✅ APROBAR","❌ RECHAZAR","❌ RECHAZAR","⚠️ REVISAR",
            "⚠️ REVISAR","❌ RECHAZAR","⚠️ REVISAR","🏆 APROBAR ⭐⭐","🌟 APROBAR ⭐","✅ APROBAR",
        ],
        "Salience":   ["35","30","25","22","20","20","19","18","20","20","18","15","15","10","7","5","1"],
    })

    st.info("💡 **Resolución de conflictos por Salience:** cuando múltiples reglas aplican, se ejecuta primero la de mayor salience. Contenido prohibido (35) y datos de contacto (30) tienen prioridad absoluta sobre cualquier otra evaluación.")


# ──────────────────────────────────────────────
# STACK TECNOLÓGICO
# ──────────────────────────────────────────────
with t_stack:
    st.markdown(PRES_CSS, unsafe_allow_html=True)
    st.markdown("""
<div class="p-page">
<div style="text-align:right;margin-bottom:12px;display:flex;align-items:center;justify-content:flex-end;gap:8px">
  <svg width="22" height="22" viewBox="0 0 130 130" xmlns="http://www.w3.org/2000/svg">
    <rect width="130" height="130" rx="30" fill="#1a2540"/>
    <path d="M65 10 L108 28 V65 C108 88 88 106 65 116 C42 106 22 88 22 65 V28 Z" fill="#1f6feb" fill-opacity="0.2" stroke="#388bfd" stroke-width="3"/>
    <circle cx="65" cy="66" r="26" stroke="#388bfd" stroke-width="3" fill="none"/>
    <circle cx="65" cy="66" r="10" fill="#388bfd" opacity="0.8"/>
    <circle cx="65" cy="66" r="5" fill="#79c0ff"/>
  </svg>
  <span style="font-size:15px;font-weight:800;color:#30363d;letter-spacing:1px">VISOR<span style="color:#1f6feb">AI</span></span>
</div>

<div class="prob-hero" style="margin-bottom:32px">
  <div class="ph-title" style="font-size:46px">Stack <span>Tecnológico</span></div>
  <div class="ph-sub">
    Cada herramienta fue elegida por su alineación con los conceptos teóricos de la materia
    y su capacidad para demostrar los principios de los Sistemas Expertos e IA Híbrida.
  </div>
</div>

<div class="sec-hdr">Componentes del sistema</div>

<div style="display:flex;flex-direction:column;gap:18px;margin-bottom:32px">

  <div class="engine-card" style="border-left:4px solid #bc8cff">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">🐍</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#bc8cff">LENGUAJE PRINCIPAL</div>
        <div class="ec-name">Python 3.11</div>
        <div class="ec-desc">
          Elegido por ser el estándar de facto en IA y Ciencia de Datos. Su ecosistema permite
          integrar en un único proyecto componentes de IA simbólica (<b>Experta</b>) y subsimbólica
          (<b>CLIP/PyTorch</b>) sin fricciones, lo que es esencial para construir el sistema híbrido
          propuesto por la materia.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Ecosistema IA/ML</span>
          <span class="ec-tag">Integración simbólica + subsimbólica</span>
          <span class="ec-tag">Prototipado rápido</span>
        </div>
      </div>
    </div>
  </div>

  <div class="engine-card" style="border-left:4px solid #bc8cff">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">⚙️</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#bc8cff">IA SIMBÓLICA — RBES</div>
        <div class="ec-name">Experta</div>
        <div class="ec-desc">
          Framework Python de Sistemas Basados en Reglas, derivado de <b>CLIPS</b> (NASA).
          Implementa el paradigma central de la materia: <b>motor de inferencia con Forward Chaining</b>,
          base de hechos y base de conocimiento. Cada regla es trazable, auditable y modificable
          sin reentrenamiento — principio clave de los SE explicables. La <b>Salience</b> implementa
          la resolución de conflictos entre reglas que compiten, tal como se estudia en la teoría
          de agenda y ciclo de ejecución de los SE.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Forward Chaining</span>
          <span class="ec-tag">Motor de inferencia</span>
          <span class="ec-tag">Base de hechos (Facts)</span>
          <span class="ec-tag">Salience / resolución de conflictos</span>
          <span class="ec-tag">Trazabilidad</span>
          <span class="ec-tag">Explicabilidad</span>
        </div>
      </div>
    </div>
  </div>

  <div class="engine-card" style="border-left:4px solid #58a6ff">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">🧠</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#58a6ff">IA SUBSIMBÓLICA — DEEP LEARNING</div>
        <div class="ec-name">CLIP ViT-B/32 (OpenAI)</div>
        <div class="ec-desc">
          Modelo de visión-lenguaje preentrenado sobre 400 millones de pares imagen-texto.
          Representa la componente <b>subsimbólica</b> del sistema: aprende representaciones
          distribuidas que no pueden expresarse como reglas explícitas. Su capacidad de
          <b>zero-shot classification</b> permite clasificar imágenes contra descripciones en
          lenguaje natural sin necesidad de datos etiquetados propios — clave para el dominio
          de e-commerce donde no había dataset previo. Conecta con la teoría de <b>redes
          neuronales y aprendizaje profundo</b> como contrapunto a los SE simbólicos.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Vision Transformer (ViT)</span>
          <span class="ec-tag">Zero-shot learning</span>
          <span class="ec-tag">Embeddings multimodales</span>
          <span class="ec-tag">IA Subsimbólica</span>
          <span class="ec-tag">Scores independientes · 13 labels</span>
        </div>
      </div>
    </div>
  </div>

  <div class="engine-card" style="border-left:4px solid #f0883e">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">🔥</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#f0883e">BACKEND DE DEEP LEARNING</div>
        <div class="ec-name">PyTorch</div>
        <div class="ec-desc">
          Motor de cómputo tensorial que ejecuta el modelo CLIP. Gestiona la codificación
          de imágenes en embeddings vectoriales y el cálculo de similitudes coseno
          calibradas con <b>sigmoid</b>. Su uso es transparente al motor de reglas — los scores
          que produce son números entre 0 y 1 que Experta consume como hechos. Esto ilustra
          la separación de capas en la arquitectura híbrida: PyTorch + CLIP producen
          <em>señales numéricas</em>, Experta aplica <em>política simbólica</em>.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Tensores</span>
          <span class="ec-tag">Inferencia CPU/GPU</span>
          <span class="ec-tag">Embeddings vectoriales</span>
          <span class="ec-tag">Separación de capas</span>
        </div>
      </div>
    </div>
  </div>

  <div class="engine-card" style="border-left:4px solid #3fb950">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">🖼️</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#3fb950">PREPROCESAMIENTO DE IMÁGENES</div>
        <div class="ec-name">Pillow (PIL)</div>
        <div class="ec-desc">
          Biblioteca de procesamiento de imágenes que maneja la ingesta desde múltiples
          fuentes (archivo, cámara, URL) y prepara cada imagen para CLIP. Normaliza formato,
          espacio de color y dimensiones. Representa la <b>capa de adquisición de conocimiento
          perceptual</b> — análogo al sensor de entrada de un SE clásico que transforma
          información del entorno en datos procesables por el sistema.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Adquisición de datos</span>
          <span class="ec-tag">Normalización RGB</span>
          <span class="ec-tag">Multi-fuente</span>
        </div>
      </div>
    </div>
  </div>

  <div class="engine-card" style="border-left:4px solid #f85149">
    <div style="display:flex;align-items:flex-start;gap:20px">
      <div style="font-size:44px;flex-shrink:0">🚀</div>
      <div style="flex:1">
        <div class="ec-type" style="color:#f85149">INTERFAZ DE USUARIO</div>
        <div class="ec-name">Streamlit</div>
        <div class="ec-desc">
          Framework web para prototipos de IA en Python puro. Elegido porque permite
          <b>demostrar el razonamiento del SE en tiempo real</b>: scores CLIP visibles,
          reglas disparadas trazables, decisión explicada. Esto cumple con el principio
          de <b>explicabilidad</b> fundamental en los Sistemas Expertos — el usuario
          puede auditar por qué el sistema tomó cada decisión, algo imposible en un
          modelo de caja negra puro.
        </div>
        <div class="ec-tags">
          <span class="ec-tag">Explicabilidad</span>
          <span class="ec-tag">Trazabilidad en tiempo real</span>
          <span class="ec-tag">Auditoría de decisiones</span>
          <span class="ec-tag">Deploy gratuito</span>
        </div>
      </div>
    </div>
  </div>

</div>

<div class="sec-hdr">Conexión con la teoría de la materia</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">

  <div class="cycle-card">
    <div class="cc-title">🎓 IA Híbrida</div>
    <div class="cc-desc">
      La materia distingue entre IA <b>simbólica</b> (razonamiento explícito, reglas) e
      <b>subsimbólica</b> (redes neuronales, aprendizaje). VisorAI es un sistema
      <b>híbrido</b>: CLIP aporta percepción subsimbólica, Experta aporta razonamiento
      simbólico. Ninguno funciona solo — CLIP sin reglas no puede aplicar política;
      Experta sin CLIP no puede percibir imágenes.
    </div>
  </div>

  <div class="cycle-card">
    <div class="cc-title">📋 Sistema Basado en Reglas (RBES)</div>
    <div class="cc-desc">
      El motor Experta implementa exactamente la arquitectura RBES estudiada:
      <b>Base de Hechos</b> (scores + hechos intermedios), <b>Base de Conocimiento</b>
      (38 reglas IF-THEN), <b>Motor de Inferencia</b> (Forward Chaining) y
      <b>mecanismo de resolución de conflictos</b> (Salience). Cada componente
      tiene su equivalente directo en la teoría clásica de SE.
    </div>
  </div>

  <div class="cycle-card">
    <div class="cc-title">🔗 Forward Chaining</div>
    <div class="cc-desc">
      El sistema usa <b>encadenamiento hacia adelante</b>: parte de los hechos
      conocidos (scores CLIP) y deriva conclusiones aplicando reglas hasta llegar
      a la decisión final. Ciclo 1 genera hechos intermedios; Ciclo 2 deriva la
      decisión. Esto contrasta con Backward Chaining que partiría de una hipótesis
      a verificar.
    </div>
  </div>

  <div class="cycle-card">
    <div class="cc-title">💡 Explicabilidad</div>
    <div class="cc-desc">
      A diferencia de una red neuronal pura, VisorAI puede responder
      <em>"¿por qué rechazaste esta foto?"</em> con una cadena de reglas
      trazables. Esto es el valor diferencial de los SE: <b>transparencia
      del proceso de razonamiento</b>. Cada decisión viene acompañada de
      las reglas que la generaron, auditables por humanos.
    </div>
  </div>

</div>

</div>
""", unsafe_allow_html=True)
