"""
Motor del Sistema Experto — CLIP + Experta
TP Análisis de Datos II · 2026
"""

from io import BytesIO
import urllib.request
import collections
import collections.abc

# Patch para Python 3.10+ — frozendict 1.2 (dependencia de experta) usa
# collections.Mapping que fue movido a collections.abc en Python 3.10
for _name in ("Mapping", "MutableMapping", "Callable", "Iterable",
              "Iterator", "Sequence", "MutableSequence", "Set", "MutableSet"):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))

import torch
import clip
from PIL import Image
from experta import *


# ─────────────────────────────────────────────
# 1. CLIP — IA Subsimbólica
# ─────────────────────────────────────────────

CLIP_LABELS = [
    "a photo of a single product item garment or object shown for sale",                  # [0] foto_producto
    "a size chart or measurements table with numbers",                                    # [1] tabla_talles
    "a photo of a person model or human figure wearing clothes or appearing in the image",  # [2] lifestyle
    "a photo with a semi-transparent watermark text or copyright logo overlaid on top",   # [3] marca_agua
    "a product on white or neutral background",                                           # [4] fondo_blanco
    "a blurry dark low quality photo",                                                    # [5] baja_calidad
    "a close-up macro photo showing product detail or texture",                           # [6] foto_detalle
    "a collage with multiple products visible",                                           # [7] multiple_productos
    "an infographic showing product features and specifications",                         # [8] es_infografia
    "a screenshot of a website or online store page",                                     # [9] es_screenshot
    "a close-up of text showing a phone number email address or WhatsApp contact info",   # [10] datos_contacto
    "a photo of a firearm weapon drugs alcohol hate symbols or prohibited illegal item",  # [11] contenido_prohibido
    "a photo of a receipt invoice bill document or paper with printed text",             # [12] es_documento
]

_model, _preprocess, _text_tokens = None, None, None

SCORE_CENTERS = torch.tensor([
    0.210,  # foto_producto
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
SCORE_SCALE = 35.0


def load_clip():
    global _model, _preprocess, _text_tokens
    if _model is None:
        _model, _preprocess = clip.load("ViT-B/32", device="cpu")
        _text_tokens = clip.tokenize(CLIP_LABELS)


def score_from_pil(img: Image.Image) -> dict:
    """Recibe una imagen PIL y devuelve scores CLIP independientes por label."""
    load_clip()
    img_rgb = img.convert("RGB")
    img_t = _preprocess(img_rgb).unsqueeze(0)
    with torch.no_grad():
        image_features = _model.encode_image(img_t)
        text_features = _model.encode_text(_text_tokens)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        similarities = (image_features @ text_features.T)[0].float()
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
        "es_screenshot":       probs[9],
        "datos_contacto":      probs[10],
        "contenido_prohibido": probs[11],
        "es_documento":        probs[12],
    }


def score_from_url(url: str) -> dict:
    """Descarga imagen de URL y devuelve scores CLIP."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        img = Image.open(BytesIO(resp.read()))
    return score_from_pil(img)


# ─────────────────────────────────────────────
# 2. HECHOS — memoria de trabajo
# ─────────────────────────────────────────────

class Scores(Fact):
    pass

class ProductoVisible(Fact):
    pass

class ProductoParcial(Fact):
    pass

class EsTabla(Fact):
    pass

class EsLifestyle(Fact):
    pass

class TieneWatermark(Fact):
    pass

class BajaCalidad(Fact):
    pass

class FondoProfesional(Fact):
    pass

class FotoDetalle(Fact):
    pass

class EsInfografia(Fact):
    pass

class EsScreenshot(Fact):
    pass

class ProductoDestacado(Fact):
    pass

class MultipleProductos(Fact):
    pass

class EsDocumento(Fact):
    pass

class TieneDatosContacto(Fact):
    pass

class ContenidoProhibido(Fact):
    pass

class Decision(Fact):
    pass


# ─────────────────────────────────────────────
# 3. MOTOR DE INFERENCIA — Experta RBES
# ─────────────────────────────────────────────

class ValidadorFotos(KnowledgeEngine):
    """
    Sistema Experto con Forward Chaining.
    Ciclo 1: Scores → Hechos intermedios
    Ciclo 2: Hechos intermedios → Decisión
    """

    # ── Ciclo 1: Scores → Hechos ──

    @Rule(Scores(foto_producto=P(lambda x: x > 0.80)), salience=100)
    def r1_destacado(self):
        self.declare(ProductoDestacado())
        self._log("R1p", "ProductoDestacado", "foto_producto > 0.80")

    @Rule(Scores(foto_producto=P(lambda x: x > 0.55)), salience=100)
    def r1(self):
        self.declare(ProductoVisible())
        self._log("R1", "ProductoVisible", "foto_producto > 0.55")

    @Rule(Scores(foto_producto=P(lambda x: 0.45 < x <= 0.55)), salience=100)
    def r1b(self):
        self.declare(ProductoParcial())
        self._log("R1b", "ProductoParcial", "0.45 < foto_producto <= 0.55")

    @Rule(Scores(tabla_talles=P(lambda x: x > 0.75)), salience=100)
    def r2(self):
        self.declare(EsTabla())
        self._log("R2", "EsTabla", "tabla_talles > 0.75")

    @Rule(Scores(lifestyle=P(lambda x: x > 0.75)), salience=100)
    def r3(self):
        self.declare(EsLifestyle())
        self._log("R3", "EsLifestyle", "lifestyle > 0.75")

    @Rule(Scores(marca_agua=P(lambda x: x > 0.75)), salience=100)
    def r4(self):
        self.declare(TieneWatermark())
        self._log("R4", "TieneWatermark", "marca_agua > 0.75")

    @Rule(Scores(baja_calidad=P(lambda x: x > 0.75)), salience=100)
    def r5(self):
        self.declare(BajaCalidad())
        self._log("R5", "BajaCalidad", "baja_calidad > 0.75")

    @Rule(Scores(fondo_blanco=P(lambda x: x > 0.60)), salience=100)
    def r6(self):
        self.declare(FondoProfesional())
        self._log("R6", "FondoProfesional", "fondo_blanco > 0.60")

    @Rule(Scores(foto_detalle=P(lambda x: x > 0.75)), salience=100)
    def r7(self):
        self.declare(FotoDetalle())
        self._log("R7", "FotoDetalle", "foto_detalle > 0.75")

    @Rule(Scores(es_infografia=P(lambda x: x > 0.75)), salience=100)
    def r7b(self):
        self.declare(EsInfografia())
        self._log("R7b", "EsInfografia", "es_infografia > 0.75")

    @Rule(Scores(es_screenshot=P(lambda x: x > 0.75)), salience=100)
    def r7c(self):
        self.declare(EsScreenshot())
        self._log("R7c", "EsScreenshot", "es_screenshot > 0.75")

    @Rule(Scores(multiple_productos=P(lambda x: x > 0.75)), salience=100)
    def r8(self):
        self.declare(MultipleProductos())
        self._log("R8", "MultipleProductos", "multiple_productos > 0.75")

    @Rule(Scores(datos_contacto=P(lambda x: x > 0.75)), salience=100)
    def r8b(self):
        self.declare(TieneDatosContacto())
        self._log("R8b", "TieneDatosContacto", "datos_contacto > 0.75")

    @Rule(Scores(es_documento=P(lambda x: x > 0.75)), salience=100)
    def r8d(self):
        self.declare(EsDocumento())
        self._log("R8d", "EsDocumento", "es_documento > 0.75")

    @Rule(Scores(contenido_prohibido=P(lambda x: x > 0.75)), salience=100)
    def r8c(self):
        self.declare(ContenidoProhibido())
        self._log("R8c", "ContenidoProhibido", "contenido_prohibido > 0.75")

    # ── Ciclo 2: Hechos → Decisión (encadenamiento) ──

    @Rule(ContenidoProhibido(), salience=35)
    def r_prohibido(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Contenido prohibido — armas, drogas, alcohol, odio o desnudez"))
        self._log("R_PROHIBIDO", "RECHAZAR", "ContenidoProhibido")

    @Rule(TieneDatosContacto(), NOT(EsLifestyle()), salience=30)
    def r_contacto(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Datos de contacto en la imagen — evasión de plataforma"))
        self._log("R_CONTACTO", "RECHAZAR", "TieneDatosContacto ∧ ¬EsLifestyle")

    @Rule(EsDocumento(), salience=22)
    def r_documento(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Factura, ticket o documento — no es foto del producto"))
        self._log("R_DOC", "RECHAZAR", "EsDocumento")

    @Rule(EsTabla(), salience=20)
    def r9(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Es tabla de talles, no foto del producto"))
        self._log("R9", "RECHAZAR", "EsTabla")

    @Rule(EsLifestyle(), NOT(ProductoDestacado()), NOT(ProductoVisible()), salience=20)
    def r10(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Foto de persona sin producto identificable"))
        self._log("R10", "RECHAZAR", "EsLifestyle ∧ ¬ProductoDestacado ∧ ¬ProductoVisible")

    @Rule(EsLifestyle(), NOT(ProductoDestacado()), ProductoVisible(), salience=19)
    def r10b(self):
        self.declare(Decision(resultado="REVISAR", motivo="Persona con producto visible — posible foto de moda o lifestyle"))
        self._log("R10b", "REVISAR", "EsLifestyle ∧ ProductoVisible ∧ ¬ProductoDestacado")

    @Rule(EsLifestyle(), ProductoDestacado(), salience=18)
    def r10c(self):
        self.declare(Decision(resultado="APROBAR", motivo="Modelo mostrando el producto claramente"))
        self._log("R10c", "APROBAR", "EsLifestyle ∧ ProductoDestacado")

    @Rule(BajaCalidad(), salience=20)
    def r11(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Foto borrosa o de baja calidad"))
        self._log("R11", "RECHAZAR", "BajaCalidad")

    @Rule(MultipleProductos(), NOT(EsTabla()), NOT(EsLifestyle()), salience=15)
    def r12(self):
        self.declare(Decision(resultado="REVISAR", motivo="Múltiples productos en la foto"))
        self._log("R12", "REVISAR", "MultipleProductos")

    @Rule(ProductoParcial(), NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), salience=18)
    def r12b(self):
        self.declare(Decision(resultado="REVISAR", motivo="Producto parcialmente visible — foto recortada o poco clara"))
        self._log("R12b", "REVISAR", "ProductoParcial")

    @Rule(
        NOT(ProductoVisible()),
        NOT(ProductoParcial()),
        NOT(EsTabla()),
        NOT(EsLifestyle()),
        salience=15,
    )
    def r13(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Producto no identificable en la foto"))
        self._log("R13", "RECHAZAR", "NOT ProductoVisible")

    @Rule(ProductoVisible(), TieneWatermark(),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), salience=10)
    def r14(self):
        self.declare(Decision(resultado="REVISAR", motivo="Tiene marca de agua"))
        self._log("R14", "REVISAR", "ProductoVisible ∧ TieneWatermark")

    @Rule(EsScreenshot(), salience=25)
    def r14b(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Screenshot de página web — posible copia de foto de otro sitio"))
        self._log("R14b", "RECHAZAR", "EsScreenshot")

    @Rule(EsInfografia(), salience=20)
    def r15(self):
        self.declare(Decision(resultado="RECHAZAR", motivo="Es un infográfico de características, no una foto del producto"))
        self._log("R15", "RECHAZAR", "EsInfografia")

    @Rule(ProductoDestacado(), FotoDetalle(), FondoProfesional(),
          NOT(TieneWatermark()), NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          salience=7)
    def r16b(self):
        self.declare(Decision(resultado="APROBAR ⭐⭐", motivo="Foto de detalle profesional — calidad premium"))
        self._log("R16b", "APROBAR ⭐⭐", "ProductoDestacado ∧ FotoDetalle ∧ FondoProfesional")

    @Rule(ProductoDestacado(), FondoProfesional(),
          NOT(TieneWatermark()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()), NOT(MultipleProductos()),
          salience=5)
    def r16(self):
        self.declare(Decision(resultado="APROBAR ⭐", motivo="Foto profesional con fondo neutro — calidad óptima"))
        self._log("R16", "APROBAR ⭐", "ProductoDestacado ∧ FondoProfesional")

    @Rule(ProductoVisible(),
          NOT(TieneWatermark()),
          NOT(EsTabla()), NOT(EsLifestyle()), NOT(BajaCalidad()),
          salience=1)
    def r17(self):
        self.declare(Decision(resultado="APROBAR", motivo="Foto válida del producto"))
        self._log("R17", "APROBAR", "ProductoVisible")

    # ── Helpers ──

    def _log(self, rule_id, hecho, condicion):
        self._fired.append({"regla": rule_id, "hecho": hecho, "condicion": condicion})

    def reset(self):
        self._fired = []
        super().reset()


# ─────────────────────────────────────────────
# 4. FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────

def evaluar(img: Image.Image) -> dict:
    """
    Evalúa una imagen PIL.
    Retorna: { resultado, motivo, scores, reglas_disparadas }
    """
    scores = score_from_pil(img)

    engine = ValidadorFotos()
    engine.reset()
    engine.declare(Scores(**scores))
    engine.run()

    decisiones = [f for f in engine.facts.values() if isinstance(f, Decision)]
    if decisiones:
        d = decisiones[0]
        return {
            "resultado": d["resultado"],
            "motivo":    d["motivo"],
            "scores":    scores,
            "reglas":    engine._fired,
        }
    return {
        "resultado": "SIN DECISIÓN",
        "motivo":    "Revisá los umbrales",
        "scores":    scores,
        "reglas":    engine._fired,
    }
