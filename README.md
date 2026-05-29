# VisorAI — Validador de Fotos de E-commerce

**TP Análisis de Datos II: Sistemas Expertos y Redes de Conocimiento**  
ASIG00131 · Universidad de la Ciudad de Buenos Aires · 1/2026  
Prof. Agustín Asuaje · Grupo B

---

## Descripción

Sistema Experto Híbrido que evalúa si una foto de publicación de e-commerce cumple con los estándares de publicación.

- **IA Subsimbólica**: CLIP ViT-B/32 — clasificación zero-shot sobre 13 labels
- **IA Simbólica**: Experta RBES — 32 reglas con Forward Chaining en 2 ciclos
- **Decisiones**: APROBAR ⭐⭐ / APROBAR ⭐ / APROBAR / REVISAR / RECHAZAR

## Archivos

```
tp/
├── app.py              # Interfaz Streamlit (7 tabs de presentación + evaluación)
├── expert_system.py    # Motor: CLIP + Experta (13 labels, 32 reglas)
├── requirements.txt    # Dependencias
└── .streamlit/
    └── config.toml     # Tema oscuro
```

## Correr localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy en Streamlit Community Cloud (gratis)

1. Crear repo en GitHub y subir la carpeta `tp/` completa
2. Ir a [https://streamlit.io/cloud](https://streamlit.io/cloud) → Sign in con GitHub
3. **New app** → elegir repo → rama `main` → archivo: `app.py`
4. Deploy — URL pública lista en ~3 minutos

> **Nota:** el primer deploy tarda más porque descarga los pesos de CLIP (~350MB).  
> Los deploys siguientes son instantáneos.

## Tabs de la aplicación

| Tab | Contenido |
|-----|-----------|
| 🎯 Portada | Carátula con equipo y universidad |
| 💡 Problema & Objetivo | Problema de e-commerce y objetivos |
| ⚙️ Arquitectura | Diagrama híbrido CLIP + Experta |
| 📋 El Sistema | Labels, reglas y decisiones |
| 📸 Evaluar Foto | Demo en vivo: archivo / cámara / URL |
| ⚙️ Reglas | Tabla completa de reglas |
| 🛠️ Stack | Tecnologías y conexión con teoría |

## Labels CLIP (13)

`foto_producto` · `tabla_talles` · `lifestyle` · `marca_agua` · `fondo_blanco` ·
`baja_calidad` · `foto_detalle` · `multiple_productos` · `es_infografia` ·
`es_screenshot` · `datos_contacto` · `contenido_prohibido` · `es_documento`

## Equipo

Sebastián Gines · Carina Acosta · Tomás Ramírez · Carlos Mercuri · Lourdes Reynaldo · Alex Surco Garnica
