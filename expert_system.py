"""
Motor del Sistema Experto — VisorAI
Validador de fotos de e-commerce mediante IA Híbrida:
  - IA Subsimbólica: CLIP ViT-B/32 (percepción visual)
  - IA Simbólica:    Experta RBES   (razonamiento y política)

TP Análisis de Datos II · ASIG00131 · UCBA · 2026
"""

from io import BytesIO
import urllib.request
import collections
import collections.abc

# ── Compatibilidad Python 3.10+ ──────────────────────────────────────────────
# frozendict==1.2 (dependencia de experta) usa collections.Mapping, que fue
# movido a collections.abc en Python 3.10 y eliminado en 3.14.
# Este patch restaura los nombres antes de importar experta.
for _name in ("Mapping", "MutableMapping", "Callable", "Iterable",
              "Iterator", "Sequence", "MutableSequence", "Set", "MutableSet"):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))

import torch
import clip
from PIL import Image
from experta import *


# ─────────────────────────────────────────────────────────────────────────────
# 1. CLIP — IA Subsimbólica
#    13 descripciones en lenguaje natural que representan las dimensiones
#    de análisis del sistema. CLIP calcula la similitud coseno entre la imagen
#    y cada descripción, produciendo un score independiente por label.
# ─────────────────────────────────────────────────────────────────────────────

CLIP_LABELS = [
    "a photo of a single product item garment or object shown for sale",                  # [0]  foto_producto
    "a size chart or measurements table with numbers",                                    # [1]  tabla_talles
    "a photo of a person model or human figure wearing clothes or appearing in the image",# [2]  lifestyle
    "a photo with a semi-transparent watermark text or copyright logo overlaid on top",   # [3]  marca_agua
    "a product on white or neutral background",                                           # [4]  fondo_blanco
    "a blurry dark low quality photo",                                                    # [5]  baja_calidad
    "a close-up macro photo showing product detail or texture",                           # [6]  foto_detalle
    "a collage with multiple products visible",                                           # [7]  multiple_productos
    "an infographic showing product features and specifications",                         # [8]  es_infografia
    "a screenshot of a website or online store page",                                     # [9]  es_screenshot
    "a close-up of text showing a phone number email address or WhatsApp contact info",   # [10] datos_contacto
    "a photo of a gun pistol rifle firearm knife or deadly weapon",                       # [11] contenido_prohibido
    "a photo of a receipt invoice bill document or paper with printed text",              # [12] es_documento
]

# ── Carga lazy del modelo ─────────────────────────────────────────────────────
# Se carga en la primera llamada a score_from_pil() para no bloquear el inicio
# de la app. Los pesos de ViT-B/32 ocupan ~350MB.
_model, _preprocess, _text_tokens = None, None, None

# ── Calibración de scores ─────────────────────────────────────────────────────
# En lugar de softmax (donde los 13 labels compiten entre sí), usamos sigmoid
# con centros calibrados: cada label produce un score independiente en [0,1].
# Ventaja: una foto de arma puede puntuar alto en contenido_prohibido SIN
# que ese score se reduzca porque foto_producto también puntúa alto.
#
# SCORE_CENTERS: similitud coseno esperada para imágenes genéricas (sin match).
# SCORE_SCALE:   qué tan abrupta es la transición alrededor del centro.
SCORE_CENTERS = torch.tensor([
    0.210,  # foto_producto       — baseline bajo (muchas fotos no son de producto)
    0.275,  # tabla_talles
    0.260,  # lifestyle
    0.285,  # marca_agua
    0.235,  # fondo_blanco
    0.260,  # baja_calidad
    0.265,  # foto_detalle
    0.280,  # multiple_productos
    0.285,  # es_infografia
    0.280,  # es_screenshot
    0.260,  # datos_contacto
    0.280,  # contenido_prohibido
    0.270,  # es_documento
])
SCORE_SCALE = 35.0  # factor de amplificación de la sigmoid


def load_clip():
    """Carga el modelo CLIP y tokeniza los labels (solo la primera vez)."""
    global _model, _preprocess, _text_tokens
    if _model is None:
        _model, _preprocess = clip.load("ViT-B/32", device="cpu")
        _text_tokens = clip.tokenize(CLIP_LABELS)


def score_from_pil(img: Image.Image) -> dict:
    """
    Recibe una imagen PIL y devuelve un score independiente [0,1] por label.
    Usa similitud coseno + sigmoid calibrada, no softmax.
    """
    load_clip()
    img_t = _preprocess(img.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        # Codificar imagen y textos en el espacio de embeddings de CLIP
        image_features = _model.encode_image(img_t)
        text_features  = _model.encode_text(_text_tokens)
        # Normalizar para obtener similitud coseno pura en [-1, 1]
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features  = text_features  / text_features.norm(dim=-1, keepdim=True)
        similarities = (image_features @ text_features.T)[0].float()
        # Sigmoid calibrada: score > 0.5 significa "por encima del baseline"
        probs = torch.sigmoid((similarities - SCORE_CENTERS) * SCORE_SCALE).tolist()
    return {
        "foto_producto":      probs[0],
        "tabla_talles":       probs[1],
        "lifestyle":          probs[2],
        "marca_agua":         probs[3],
        "fondo_blanco":       probs[4],
        "baja_calidad":       probs[5],
        "foto_detalle":       probs[6],
        "multiple_productos": probs[7],
        "es_infografia":      probs[8],
        "es_screenshot":      probs[9],
        "datos_contacto":     probs[10],
        "contenido_prohibido":probs[11],
        "es_documento":       probs[12],
    }


def score_from_url(url: str) -> dict:
    """Descarga imagen de URL y devuelve scores CLIP."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        img = Image.open(BytesIO(resp.read()))
    return score_from_pil(img)


# ─────────────────────────────────────────────────────────────────────────────
# 2. HECHOS — Base de Hechos (Working Memory)
#    Cada clase representa un hecho que puede estar presente o ausente.
#    Ciclo 1 los declara a partir de scores; Ciclo 2 los consume para decidir.
# ─────────────────────────────────────────────────────────────────────────────

class Scores(Fact):
    """Hecho inicial: contiene los 13 scores CLIP de la imagen evaluada."""
    pass

# ── Hechos de percepción del producto ────────────────────────────────────────
class ProductoDestacado(Fact):
    """Producto claramente dominante en la imagen (foto_producto > 0.25)."""
    pass

class ProductoVisible(Fact):
    """Producto presente pero no necesariamente dominante (> 0.12)."""
    pass

class ProductoParcial(Fact):
    """Producto apenas visible — foto recortada o lejana (0.04–0.12)."""
    pass

# ── Hechos de tipo de imagen ──────────────────────────────────────────────────
class EsTabla(Fact):
    """La imagen es una tabla de talles o medidas."""
    pass

class EsLifestyle(Fact):
    """Hay una persona o modelo claramente en la imagen (lifestyle > 0.40)."""
    pass

class EsLifestyleSoft(Fact):
    """Señal débil de persona — forma humanoide, mano, silueta (0.10 < lifestyle ≤ 0.40).
    No es suficiente para afirmar que hay un modelo, pero sí para desconfiar
    de un APROBAR sin fondo profesional."""
    pass

class TieneWatermark(Fact):
    """Tiene marca de agua o copyright translúcido superpuesto."""
    pass

class BajaCalidad(Fact):
    """Foto borrosa, oscura o de calidad insuficiente."""
    pass

class FondoProfesional(Fact):
    """Fondo blanco o neutro — indica foto de producto profesional."""
    pass

class FotoDetalle(Fact):
    """Primer plano de detalle o textura — bonus de calidad."""
    pass

class EsInfografia(Fact):
    """Infográfico de características, no foto del producto."""
    pass

class EsScreenshot(Fact):
    """Captura de pantalla de un sitio web."""
    pass

class MultipleProductos(Fact):
    """Collage con varios productos visibles."""
    pass

# ── Hechos de violación de política ──────────────────────────────────────────
class EsDocumento(Fact):
    """Factura, ticket o documento impreso."""
    pass

class TieneDatosContacto(Fact):
    """Teléfono, WhatsApp, email o redes sociales visibles en la imagen."""
    pass

class ContenidoProhibido(Fact):
    """Señal de contenido prohibido (score > 0.10). Usado cuando no hay persona."""
    pass

class ContenidoProhibidoAlto(Fact):
    """Señal fuerte de contenido prohibido (score > 0.30). Usado cuando hay persona
    para evitar que gestos de mano (puño, pulgar) activen un falso positivo."""
    pass

class Decision(Fact):
    """Hecho terminal: contiene resultado (str) y motivo (str)."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# 3. MOTOR DE INFERENCIA — Experta RBES (Rule-Based Expert System)
#
#    Arquitectura en dos ciclos con Forward Chaining:
#
#    CICLO 1 (salience=100): Scores → Hechos intermedios
#      Convierte los valores numéricos de CLIP en hechos simbólicos del dominio.
#      Todas las reglas tienen la misma salience para que se ejecuten primero,
#      antes de que empiece el Ciclo 2.
#
#    CICLO 2 (salience 1–35): Hechos → Decisión
#      Aplica la política de la plataforma sobre los hechos declarados.
#      La salience define la prioridad en caso de conflicto:
#        35 = contenido prohibido (máxima prioridad — riesgo legal)
#        30 = datos de contacto   (evasión de comisión)
#        25 = screenshot          (posible copia de otro sitio)
#        20 = tabla/lifestyle/calidad (política básica)
#         1 = aprobar             (mínima — solo si no hay ningún problema)
# ─────────────────────────────────────────────────────────────────────────────

class ValidadorFotos(KnowledgeEngine):

    # ══════════════════════════════════════════════════════════════════════════
    # CICLO 1 — Scores CLIP → Hechos intermedios (salience=100)
    # ══════════════════════════════════════════════════════════════════════════

    # ── Visibilidad del producto ──────────────────────────────────────────────
    # Tres niveles: Destacado (alta confianza) > Visible > Parcial.
    # Usados en Ciclo 2 para distinguir "foto de moda con modelo" de "selfie".

    @Rule(Scores(foto_producto=P(lambda x: x > 0.25)), salience=100)
    def r1_destacado(self):
        self.declare(ProductoDestacado())
        self._log("R1p", "ProductoDestacado", "foto_producto > 0.25")

    @Rule(Scores(foto_producto=P(lambda x: x > 0.12)), salience=100)
    def r1(self):
        self.declare(ProductoVisible())
        self._log("R1", "ProductoVisible", "foto_producto > 0.12")

    @Rule(Scores(foto_producto=P(lambda x: 0.04 < x <= 0.12)), salience=100)
    def r1b(self):
        self.declare(ProductoParcial())
        self._log("R1b", "ProductoParcial", "0.04 < foto_producto <= 0.12")

    # ── Tipo de imagen ────────────────────────────────────────────────────────

    @Rule(Scores(tabla_talles=P(lambda x: x > 0.50)), salience=100)
    def r2(self):
        self.declare(EsTabla())
        self._log("R2", "EsTabla", "tabla_talles > 0.50")

    @Rule(Scores(lifestyle=P(lambda x: x > 0.40)), salience=100)
    def r3(self):
        # Umbral 0.40: persona claramente visible (modelo, selfie, etc.)
        self.declare(EsLifestyle())
        self._log("R3", "EsLifestyle", "lifestyle > 0.40")

    @Rule(Scores(lifestyle=P(lambda x: 0.10 < x <= 0.40)), salience=100)
    def r3_soft(self):
        # Zona gris (0.10–0.40): señal débil de elemento humanoide.
        # Cubre manos, siluetas de ropa drapeada sin fondo profesional,
        # extremidades parcialmente visibles. No es un rechazo directo,
        # pero previene aprobaciones automáticas sin suficiente contexto.
        self.declare(EsLifestyleSoft())
        self._log("R3s", "EsLifestyleSoft", "0.10 < lifestyle ≤ 0.40")

    @Rule(Scores(marca_agua=P(lambda x: x > 0.55)), salience=100)
    def r4(self):
        # Umbral alto (0.55) para evitar confundir logos bordados en productos
        # (ej: Adidas en camiseta) con marcas de agua superpuestas.
        self.declare(TieneWatermark())
        self._log("R4", "TieneWatermark", "marca_agua > 0.55")

    @Rule(Scores(baja_calidad=P(lambda x: x > 0.20)), salience=100)
    def r5(self):
        self.declare(BajaCalidad())
        self._log("R5", "BajaCalidad", "baja_calidad > 0.50")

    @Rule(Scores(fondo_blanco=P(lambda x: x > 0.35)), salience=100)
    def r6(self):
        # Umbral 0.35: captura fondos neutros y blancos sin ser demasiado estricto.
        # La zapatilla oscura sobre fondo blanco puntúa ~0.37; la bata blanca ~0.78.
        self.declare(FondoProfesional())
        self._log("R6", "FondoProfesional", "fondo_blanco > 0.35")

    @Rule(Scores(foto_detalle=P(lambda x: x > 0.25)), salience=100)
    def r7(self):
        self.declare(FotoDetalle())
        self._log("R7", "FotoDetalle", "foto_detalle > 0.25")

    @Rule(Scores(es_infografia=P(lambda x: x > 0.35)), salience=100)
    def r7b(self):
        self.declare(EsInfografia())
        self._log("R7b", "EsInfografia", "es_infografia > 0.35")

    @Rule(Scores(es_screenshot=P(lambda x: x > 0.35)), salience=100)
    def r7c(self):
        self.declare(EsScreenshot())
        self._log("R7c", "EsScreenshot", "es_screenshot > 0.35")

    @Rule(Scores(multiple_productos=P(lambda x: x > 0.50)), salience=100)
    def r8(self):
        self.declare(MultipleProductos())
        self._log("R8", "MultipleProductos", "multiple_productos > 0.50")

    # ── Violaciones de política ───────────────────────────────────────────────

    @Rule(Scores(datos_contacto=P(lambda x: x > 0.60)), salience=100)
    def r8b(self):
        # Umbral 0.60 para evitar falsos positivos en fotos de moda donde
        # el fondo o los patrones del producto puedan confundir a CLIP.
        self.declare(TieneDatosContacto())
        self._log("R8b", "TieneDatosContacto", "datos_contacto > 0.60")

    @Rule(Scores(es_documento=P(lambda x: x > 0.30)), salience=100)
    def r8d(self):
        self.declare(EsDocumento())
        self._log("R8d", "EsDocumento", "es_documento > 0.30")

    @Rule(Scores(contenido_prohibido=P(lambda x: x > 0.20)), salience=100)
    def r8c(self):
        # Umbral 0.20: señal moderada de contenido prohibido.
        # Se usa cuando no hay persona y el producto no es claramente dominante
        # (ver condiciones en R_PROHIBIDO del Ciclo 2).
        # 0.10 generaba demasiados falsos positivos con productos normales.
        self.declare(ContenidoProhibido())
        self._log("R8c", "ContenidoProhibido", "contenido_prohibido > 0.20")

    @Rule(Scores(contenido_prohibido=P(lambda x: x > 0.30)), salience=100)
    def r8c_alto(self):
        # Umbral alto (0.30): señal fuerte de contenido prohibido.
        # Este nivel dispara RECHAZAR incluso cuando hay persona en la foto.
        # Un pulgar arriba o puño raramente supera 0.30; un arma real sí.
        self.declare(ContenidoProhibidoAlto())
        self._log("R8c_alto", "ContenidoProhibidoAlto", "contenido_prohibido > 0.30")

    # ══════════════════════════════════════════════════════════════════════════
    # CICLO 2 — Hechos → Decisión (Forward Chaining)
    #
    # Principio de diseño: cada regla debe declarar exactamente UNA Decision.
    # Para lograrlo, las reglas de menor salience incluyen condiciones NOT()
    # que las inhiben cuando una regla de mayor salience ya actuó.
    #
    # Jerarquía de salience:
    #   35  ContenidoProhibido  (riesgo legal — máxima prioridad)
    #   30  DatosContacto       (evasión de comisión)
    #   25  Screenshot          (copia de otro sitio)
    #   22  Documento           (no es foto de producto)
    #   20  Tabla/Persona/Calidad/Infografía  (política básica)
    #   19  Persona + producto parcial/visible (casos ambiguos con persona)
    #   18  Persona + producto destacado / producto parcial solo
    #   15  Múltiples productos / catch-all sin producto
    #   10  Producto + watermark
    #    7  Aprobación premium ⭐⭐
    #    5  Aprobación estándar ⭐
    #    2  Aprobación base (ProductoDestacado sin fondo)
    #    1  Aprobación base (ProductoVisible sin destacar)
    # ══════════════════════════════════════════════════════════════════════════

    # ── BLOQUE 1: Rechazos absolutos por política (s=22–35) ───────────────────
    # Estas reglas tienen prioridad sobre cualquier consideración de calidad
    # fotográfica. Un arma siempre rechaza, aunque la foto sea perfecta.

    @Rule(ContenidoProhibidoAlto(), salience=35)
    def r_prohibido_alto(self):
        # s=35: señal fuerte (>0.30) — rechaza aunque haya persona.
        # Cubre el caso de alguien sosteniendo un arma real frente a cámara.
        self.declare(Decision(resultado="RECHAZAR", motivo="Contenido prohibido — armas, drogas, alcohol, odio o desnudez"))
        self._log("R_PROHIBIDO_ALTO", "RECHAZAR", "ContenidoProhibidoAlto")

    @Rule(ContenidoProhibido(), NOT(EsLifestyle()), NOT(ProductoDestacado()), salience=34)
    def r_prohibido(self):
        # s=34: señal moderada (>0.20) sin persona y sin producto dominante.
        # NOT(EsLifestyle()): con persona, gestos pueden dar falso positivo.
        # NOT(ProductoDestacado()): si el producto tiene score muy alto (>0.25),
        # un score de arma de 0.20 es casi seguro ruido del modelo.
        self.declare(Decision(resultado="RECHAZAR", motivo="Contenido prohibido — armas, drogas, alcohol, odio o desnudez"))
        self._log("R_PROHIBIDO", "RECHAZAR", "ContenidoProhibido ∧ ¬EsLifestyle ∧ ¬ProductoDestacado")

    @Rule(TieneDatosContacto(), NOT(EsLifestyle()), salience=30)
    def r_contacto(self):
        # NOT(EsLifestyle()): en fotos de moda, los patrones o texturas de la
        # ropa pueden confundir a CLIP y darle score alto a datos_contacto
        # incorrectamente. Si hay persona, ignoramos esa señal.
        self.declare(Decision(resultado="RECHAZAR", motivo="Datos de contacto en la imagen — evasión de plataforma"))
        self._log("R_CONTACTO", "RECHAZAR", "TieneDatosContacto ∧ ¬EsLifestyle")

    @Rule(EsScreenshot(), salience=25)
    def r14b(self):
        # Un screenshot puede ser una foto robada de otra plataforma o
        # una publicación falsa mostrando un producto que no es el real.
        self.declare(Decision(resultado="RECHAZAR", motivo="Screenshot de página web — posible copia de foto de otro sitio"))
        self._log("R14b", "RECHAZAR", "EsScreenshot")

    @Rule(EsDocumento(), salience=22)
    def r_documento(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Factura, ticket o documento — no es foto del producto"))
        self._log("R_DOC", "RECHAZAR", "EsDocumento")

    # ── BLOQUE 2: Rechazos por tipo de imagen (s=20) ──────────────────────────
    # Estos rechazos corresponden a imágenes que no muestran el producto,
    # independientemente de su calidad fotográfica.

    @Rule(EsTabla(), salience=20)
    def r9(self):
        # Una tabla de talles es información útil para la publicación, pero no
        # puede ser la foto principal del producto.
        self.declare(Decision(resultado="RECHAZAR", motivo="Es tabla de talles, no foto del producto"))
        self._log("R9", "RECHAZAR", "EsTabla")

    @Rule(EsLifestyle(), NOT(ProductoDestacado()), NOT(ProductoVisible()), NOT(ProductoParcial()),
          NOT(ContenidoProhibido()), salience=20)
    def r10(self):
        # Persona detectada SIN ningún nivel de producto visible → selfie o foto personal.
        # Los NOT() garantizan que esta regla solo dispara cuando:
        #   - el producto no es visible en ningún grado (ni parcial)
        #   - no hay contenido prohibido (en ese caso R_PROHIBIDO ya actuó con s=35)
        self.declare(Decision(resultado="RECHAZAR", motivo="Foto de persona sin producto identificable"))
        self._log("R10", "RECHAZAR", "EsLifestyle ∧ ¬ProductoDestacado ∧ ¬ProductoVisible ∧ ¬ProductoParcial")

    @Rule(BajaCalidad(), salience=20)
    def r11(self):
        # La baja calidad rechaza independientemente de si el producto es visible,
        # porque una foto borrosa u oscura no sirve para que el comprador evalúe el producto.
        self.declare(Decision(resultado="RECHAZAR", motivo="Foto borrosa o de baja calidad"))
        self._log("R11", "RECHAZAR", "BajaCalidad")

    @Rule(EsInfografia(), salience=20)
    def r15(self):
        # Un infográfico puede acompañar una publicación, pero no reemplaza la foto del producto.
        self.declare(Decision(resultado="RECHAZAR", motivo="Es un infográfico de características, no una foto del producto"))
        self._log("R15", "RECHAZAR", "EsInfografia")

    # ── BLOQUE 3: Casos con persona → árbol de decisión (s=18–20) ────────────
    # Las reglas R10/R10b/R10c/R10d forman un árbol según la visibilidad del producto:
    #
    #   EsLifestyle
    #   ├── SIN producto (ni parcial)      → RECHAZAR (R10, s=20)  selfie
    #   ├── ProductoParcial (apenas)       → REVISAR  (R10d, s=19) ambiguo
    #   ├── ProductoVisible (pero no >0.25)→ REVISAR  (R10b, s=19) posible moda
    #   └── ProductoDestacado (>0.25)      → APROBAR  (R10c, s=18) foto de moda válida

    @Rule(EsLifestyle(), ProductoParcial(), NOT(ProductoDestacado()), NOT(ProductoVisible()), salience=19)
    def r10d(self):
        # Persona + producto apenas visible (score 0.04–0.12): no es selfie pura
        # pero tampoco hay suficiente evidencia de que el producto sea el sujeto.
        # Un moderador decide.
        self.declare(Decision(resultado="REVISAR", motivo="Persona con producto apenas visible — requiere revisión"))
        self._log("R10d", "REVISAR", "EsLifestyle ∧ ProductoParcial ∧ ¬ProductoVisible")

    @Rule(EsLifestyle(), NOT(ProductoDestacado()), ProductoVisible(), salience=19)
    def r10b(self):
        # Persona + producto visible (score >0.12) pero no dominante (<0.25):
        # puede ser una foto de moda legítima o una lifestyle ambigua.
        # Se envía a revisión humana para decidir.
        self.declare(Decision(resultado="REVISAR", motivo="Persona con producto visible — posible foto de moda o lifestyle"))
        self._log("R10b", "REVISAR", "EsLifestyle ∧ ProductoVisible ∧ ¬ProductoDestacado")

    @Rule(EsLifestyle(), ProductoDestacado(), salience=18)
    def r10c(self):
        # Persona + producto DOMINANTE (score >0.25): el producto es claramente
        # el sujeto principal — típico de fotos de moda o ropa en e-commerce.
        # Se aprueba sin necesidad de revisión humana.
        self.declare(Decision(resultado="APROBAR", motivo="Modelo mostrando el producto claramente"))
        self._log("R10c", "APROBAR", "EsLifestyle ∧ ProductoDestacado")

    # ── BLOQUE 4: Revisiones por otros motivos (s=10–18) ─────────────────────

    @Rule(ProductoParcial(), NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), salience=18)
    def r12b(self):
        # Producto apenas visible SIN persona: foto recortada, lejana o mal encuadrada.
        # Se envía a revisión porque podría ser válida con mejor contexto.
        self.declare(Decision(resultado="REVISAR", motivo="Producto parcialmente visible — foto recortada o poco clara"))
        self._log("R12b", "REVISAR", "ProductoParcial")

    @Rule(MultipleProductos(), NOT(EsTabla()), NOT(EsLifestyle()), salience=15)
    def r12(self):
        # Múltiples productos: puede ser un kit/combo legítimo o una foto
        # de catálogo incorrecta. Se envía a revisión.
        self.declare(Decision(resultado="REVISAR", motivo="Múltiples productos en la foto"))
        self._log("R12", "REVISAR", "MultipleProductos")

    @Rule(
        NOT(ProductoVisible()),
        NOT(ProductoParcial()),
        NOT(EsTabla()),
        NOT(EsLifestyle()),
        NOT(ContenidoProhibido()), NOT(ContenidoProhibidoAlto()),  # ya rechazados por R_PROHIBIDO
        NOT(EsDocumento()),          # ya rechazado por R_DOC (s=22)
        NOT(EsScreenshot()),         # ya rechazado por R14b (s=25)
        NOT(BajaCalidad()),          # ya rechazado por R11 (s=20)
        NOT(EsInfografia()),         # ya rechazado por R15 (s=20)
        NOT(TieneDatosContacto()),   # ya rechazado por R_CONTACTO (s=30)
        NOT(MultipleProductos()),    # ya revisado por R12 (s=15)
        salience=15,
    )
    def r13(self):
        # CATCH-ALL: ninguna evidencia de producto y ningún tipo de imagen reconocible.
        # Ejemplo: foto de ambiente vacío, imagen completamente negra/blanca, etc.
        #
        # Los NOT() son esenciales para que esta regla solo dispare cuando
        # NINGUNA otra regla del Ciclo 2 haya actuado antes. Sin ellos,
        # R13 declararía una Decision redundante con motivo incorrecto
        # (ej: "Producto no identificable" cuando en realidad era "Arma detectada").
        self.declare(Decision(resultado="RECHAZAR", motivo="Producto no identificable en la foto"))
        self._log("R13", "RECHAZAR", "NOT ProductoVisible ∧ sin tipo identificable")

    @Rule(ProductoVisible(), TieneWatermark(),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), salience=10)
    def r14(self):
        # Producto visible pero con marca de agua superpuesta: la foto podría
        # ser robada o tener copyright de otro vendedor. Revisión humana.
        self.declare(Decision(resultado="REVISAR", motivo="Tiene marca de agua"))
        self._log("R14", "REVISAR", "ProductoVisible ∧ TieneWatermark")

    # ── BLOQUE 5: Aprobaciones premium y base (s=1–7) ────────────────────────
    # Solo llegan aquí imágenes donde ninguna regla de rechazo/revisión aplicó.
    # Las condiciones NOT() en R17b y R17 son guardas de seguridad: evitan
    # declarar APROBAR si alguna regla de mayor salience ya actuó pero dejó
    # un hecho de violación en la memoria de trabajo.

    @Rule(ProductoDestacado(), FotoDetalle(), FondoProfesional(),
          NOT(TieneWatermark()), NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          salience=7)
    def r16b(self):
        # Trifecta de calidad: producto dominante + primer plano macro + fondo neutro.
        # La combinación más valorada en fotografía de producto profesional.
        self.declare(Decision(resultado="APROBAR ⭐⭐", motivo="Foto de detalle profesional — calidad premium"))
        self._log("R16b", "APROBAR ⭐⭐", "ProductoDestacado ∧ FotoDetalle ∧ FondoProfesional")

    @Rule(ProductoDestacado(), FondoProfesional(),
          NOT(FotoDetalle()),        # si hay detalle, aplica R16b (s=7), no esta
          NOT(TieneWatermark()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), NOT(MultipleProductos()),
          salience=5)
    def r16(self):
        # Producto dominante + fondo profesional (sin detalle macro).
        # NOT(FotoDetalle()) evita declarar APROBAR ⭐ cuando R16b ya declaró APROBAR ⭐⭐.
        self.declare(Decision(resultado="APROBAR ⭐", motivo="Foto profesional con fondo neutro — calidad óptima"))
        self._log("R16", "APROBAR ⭐", "ProductoDestacado ∧ FondoProfesional ∧ ¬FotoDetalle")

    @Rule(EsLifestyleSoft(), ProductoDestacado(), NOT(FondoProfesional()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          NOT(ContenidoProhibido()), NOT(ContenidoProhibidoAlto()),
          salience=4)
    def r_soft_revisar(self):
        # Señal débil de persona/silueta (mano, ropa drapeada, extremidad)
        # sin fondo profesional → no podemos confirmar que es solo el producto.
        # La bata con fondo blanco no llega aquí: FondoProfesional declarado
        # hace que R16 (s=5) dispare antes que esta regla (s=4).
        self.declare(Decision(resultado="REVISAR", motivo="Posible elemento humano en la foto — requiere revisión"))
        self._log("R_SOFT", "REVISAR", "EsLifestyleSoft ∧ ProductoDestacado ∧ ¬FondoProfesional")

    @Rule(ProductoDestacado(),
          NOT(FondoProfesional()),
          NOT(EsLifestyleSoft()),    # con señal de persona, aplica R_SOFT_REVISAR (s=4)
          NOT(TieneWatermark()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          NOT(ContenidoProhibido()), NOT(ContenidoProhibidoAlto()), NOT(EsScreenshot()), NOT(EsDocumento()),
          NOT(EsInfografia()), NOT(TieneDatosContacto()),
          salience=2)
    def r17b(self):
        # Producto dominante sin fondo profesional, sin señal de persona, sin rechazos.
        self.declare(Decision(resultado="APROBAR", motivo="Foto válida del producto"))
        self._log("R17b", "APROBAR", "ProductoDestacado ∧ ¬FondoProfesional ∧ ¬EsLifestyleSoft")

    @Rule(ProductoVisible(),
          NOT(ProductoDestacado()),  # con ProductoDestacado aplican R16b/R16/R17b
          NOT(TieneWatermark()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          NOT(ContenidoProhibido()), NOT(ContenidoProhibidoAlto()), NOT(EsScreenshot()), NOT(EsDocumento()),
          NOT(EsInfografia()), NOT(TieneDatosContacto()),
          salience=1)
    def r17(self):
        # Caso más básico: producto visible (score 0.12–0.25) sin ningún problema.
        # NOT(ProductoDestacado()) garantiza que R17b/R16/R16b tienen prioridad
        # cuando el producto es más prominente.
        self.declare(Decision(resultado="APROBAR", motivo="Foto válida del producto"))
        self._log("R17", "APROBAR", "ProductoVisible ∧ ¬ProductoDestacado ∧ sin rechazos")

    # ── Helpers internos ──────────────────────────────────────────────────────

    def _log(self, rule_id, hecho, condicion):
        """Registra cada regla disparada para mostrar trazabilidad en la UI."""
        self._fired.append({"regla": rule_id, "hecho": hecho, "condicion": condicion})

    def reset(self):
        """Reinicia el motor entre evaluaciones, limpiando hechos y log."""
        self._fired = []
        super().reset()


# ─────────────────────────────────────────────────────────────────────────────
# 4. FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def evaluar(img: Image.Image) -> dict:
    """
    Evalúa una imagen PIL completa:
      1. Calcula los 13 scores CLIP (IA subsimbólica)
      2. Declara los scores como hechos iniciales
      3. Ejecuta el motor de inferencia (Forward Chaining)
      4. Retorna la decisión, motivo, scores y reglas disparadas

    Retorna dict con claves: resultado, motivo, scores, reglas
    """
    # Paso 1: percepción visual mediante CLIP
    scores = score_from_pil(img)

    # Paso 2-3: razonamiento simbólico mediante Experta
    engine = ValidadorFotos()
    engine.reset()
    engine.declare(Scores(**scores))  # inyectar hechos iniciales
    engine.run()                      # ejecutar todas las reglas hasta estabilizar

    # Paso 4: extraer la decisión de mayor prioridad
    decisiones = [f for f in engine.facts.values() if isinstance(f, Decision)]
    if decisiones:
        d = decisiones[0]
        return {
            "resultado": d["resultado"],
            "motivo":    d["motivo"],
            "scores":    scores,
            "reglas":    engine._fired,
        }
    # No debería llegar aquí si las reglas están bien definidas
    return {
        "resultado": "SIN DECISIÓN",
        "motivo":    "Sin regla aplicable — revisá los umbrales",
        "scores":    scores,
        "reglas":    engine._fired,
    }
