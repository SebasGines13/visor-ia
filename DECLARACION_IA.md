# Declaración de Uso de Herramientas de Inteligencia Artificial

**Trabajo Práctico — ASIG00131**  
Análisis de Datos II: Sistemas Expertos y Redes de Conocimiento  
Universidad de la Ciudad de Buenos Aires · 1er cuatrimestre 2026  
Prof. Agustín Asuaje · Grupo B

---

## 1. Herramientas de IA utilizadas

| Herramienta | Versión / Modelo | Rol en el trabajo |
|-------------|-----------------|------------------|
| **Claude Code** (Anthropic) | Claude Sonnet 4.6 | Asistente principal de desarrollo: diseño arquitectónico, generación de código, debugging, documentación |
| **CLIP** (OpenAI) | ViT-B/32 | Componente del sistema: clasificación de imágenes por similitud semántica (IA subsimbólica) |

> **Aclaración:** CLIP es parte del sistema construido, no una herramienta de asistencia al desarrollo. Se lista aquí por ser un modelo de IA que integra el entregable.

---

## 2. Alcance del uso de IA en el desarrollo

Claude Code fue utilizado durante **todo el ciclo de desarrollo** del TP:

- Diseño de la arquitectura híbrida (CLIP + Experta)
- Implementación del motor de inferencia en Python
- Definición y refinamiento iterativo de las 38 reglas IF-THEN
- Diseño del esquema de scoring (sigmoid calibrada en lugar de softmax)
- Calibración de umbrales mediante casos de prueba reales
- Desarrollo de la interfaz Streamlit con 7 tabs de presentación
- Resolución de incompatibilidades de dependencias (Python 3.14 + frozendict)
- Generación de documentación y comentarios del código

Todo el código generado fue **revisado, evaluado y ajustado** por el equipo antes de incorporarse al sistema. Las decisiones de diseño (qué reglas incluir, qué umbrales usar, cómo manejar casos borde) surgieron del diálogo entre el equipo y la herramienta, y fueron validadas con imágenes reales de MercadoLibre.

---

## 3. Registro de prompts principales

A continuación se detallan los prompts más representativos organizados por etapa, con referencia explícita a los conceptos teóricos de la materia.

---

### 3.1 Diseño del sistema experto

**Prompt:**
> "Necesito construir un sistema experto para validar fotos de publicaciones de e-commerce. El sistema debe combinar IA subsimbólica (CLIP para clasificar imágenes) con IA simbólica (reglas IF-THEN). ¿Cómo estructurarías los dos ciclos de inferencia — el primero que convierte scores numéricos en hechos, y el segundo que aplica las reglas de política?"

**Conexión teórica:**
Este prompt refleja el concepto central de **IA Híbrida**: la integración de un motor de percepción subsimbólico (CLIP) con un motor de razonamiento simbólico (Experta RBES). La pregunta sobre los "dos ciclos" corresponde al **ciclo de reconocimiento-acción** del motor de inferencia, donde en cada ciclo se evalúan las reglas activas contra la base de hechos y se selecciona la de mayor salience.

---

### 3.2 Implementación de la base de conocimiento

**Prompt:**
> "Implementá las reglas del sistema experto usando Experta (Python). Las reglas del Ciclo 1 deben convertir scores CLIP en hechos (ProductoVisible, EsTabla, EsLifestyle, etc.) con salience=100. Las del Ciclo 2 deben encadenar esos hechos hacia una decisión final. Las reglas de rechazo por contenido prohibido deben tener la mayor salience."

**Conexión teórica:**
Este prompt operacionaliza directamente los conceptos de:
- **Base de Hechos (Working Memory):** los 13 scores CLIP y los hechos intermedios declarados en Ciclo 1
- **Base de Conocimiento:** las 38 reglas IF-THEN implementadas
- **Motor de Inferencia:** el motor de Experta aplicando Forward Chaining
- **Resolución de conflictos por Salience:** priorización de reglas (contenido prohibido s=35 > datos de contacto s=30 > reglas de calidad s=1–20), equivalente al concepto de **agenda** en los SE clásicos

---

### 3.3 Elección de Forward Chaining

**Prompt:**
> "¿Por qué usamos Forward Chaining y no Backward Chaining para este sistema? Explicalo en términos de la teoría de sistemas expertos."

**Respuesta generada y adoptada:**
El Forward Chaining es apropiado porque partimos de **datos conocidos** (scores de CLIP para la imagen ingresada) y derivamos conclusiones. No tenemos una hipótesis previa que verificar — no sabemos si la foto será aprobada o rechazada hasta evaluar los hechos. El Backward Chaining sería más adecuado si partiéramos de una hipótesis ("¿es esta foto rechazable?") e intentáramos encontrar evidencia que la soporte.

**Conexión teórica:**
La distinción Forward vs Backward Chaining es un concepto fundamental de la materia. Este diálogo permitió fundamentar la elección arquitectónica con el marco teórico correcto.

---

### 3.4 Decisión arquitectónica: sigmoid vs softmax

**Prompt:**
> "El sistema rechaza una camiseta de fútbol claramente visible porque foto_producto solo puntúa 0.036. El label marca_agua puntúa 0.672 aunque no hay ninguna marca de agua — solo los logos de Adidas y Flamengo bordados en la camiseta. ¿Por qué pasa esto y cómo lo resolvemos estructuralmente?"

**Respuesta generada y adoptada:**
El problema raíz es el uso de **softmax**: con 13 labels compitiendo por sumar probabilidad 1, cuando ninguno domina claramente, la masa de probabilidad se distribuye de manera arbitraria y un label incorrecto puede "ganar". La solución es reemplazar softmax por **similitud coseno + sigmoid calibrada**: cada label produce un score independiente entre 0 y 1, sin competir con los demás. Una foto de arma puede puntuar alto en `contenido_prohibido` aunque `foto_producto` también puntúe alto.

**Conexión teórica:**
Esta decisión ilustra la diferencia entre **clasificación multiclase** (softmax, una sola clase gana) y **clasificación multietiqueta** (sigmoid, cada label es independiente). En el contexto del sistema híbrido, es análogo a la diferencia entre una base de conocimiento con reglas mutuamente excluyentes vs una donde múltiples hechos pueden coexistir simultáneamente.

---

### 3.5 Calibración iterativa de umbrales

**Prompt:**
> "Vi que pasé una imagen de un arma y el sistema la aprobó. ¿Cómo lo ajusto?"

**Proceso y respuesta:**
Diagnóstico: el label `contenido_prohibido` tenía umbral 0.75 — imposible de alcanzar en la práctica incluso con la sigmoid calibrada. Además, el label era demasiado genérico ("firearm weapon drugs alcohol hate symbols"). La solución fue doble: (1) reformular el label para ser más específico visualmente ("a photo of a gun pistol rifle firearm knife or deadly weapon") y (2) bajar el umbral a 0.10, asumiendo que para contenido ilegal es preferible **sobre-rechazar** que dejar pasar.

**Conexión teórica:**
Este proceso refleja la **adquisición y refinamiento del conocimiento** en los SE. La elección asimétrica del umbral (0.10 para armas vs 0.55 para marca de agua) corresponde al concepto de **costo relativo de error**: en una plataforma de e-commerce, publicar un arma tiene consecuencias legales graves; un falso positivo ocasional en esa categoría es aceptable.

---

### 3.6 Refinamiento de reglas: el caso lifestyle

**Prompt:**
> "Una foto de vestido con modelo está siendo rechazada. Pero es una foto de moda perfectamente válida — se ve el producto claramente. ¿Cómo diferenciamos una selfie inválida de una foto de moda válida?"

**Solución implementada:**
En lugar de una regla binaria `EsLifestyle → RECHAZAR`, se implementaron tres reglas que combinan el hecho de "persona visible" con el nivel de visibilidad del producto:

| Condición | Resultado | Razonamiento |
|-----------|-----------|--------------|
| `EsLifestyle ∧ ¬ProductoVisible` | RECHAZAR | Selfie sin producto |
| `EsLifestyle ∧ ProductoVisible ∧ ¬ProductoDestacado` | REVISAR | Persona con algo visible — ambiguo |
| `EsLifestyle ∧ ProductoDestacado` | APROBAR | Modelo mostrando el producto |

**Conexión teórica:**
Este refinamiento ilustra el concepto de **especificidad de reglas** en los SE: una regla más específica (con más condiciones) tiene precedencia semántica sobre una más general. También demuestra el proceso iterativo de **validación con casos de prueba** que caracteriza el ciclo de desarrollo de un SE.

---

### 3.7 Explicabilidad del sistema

**Prompt:**
> "El sistema debe mostrar no solo la decisión final sino también las reglas que dispararon, para que el usuario entienda POR QUÉ se tomó esa decisión."

**Conexión teórica:**
La **explicabilidad** es una propiedad definitoria de los Sistemas Expertos frente a los modelos de caja negra. La capacidad de responder *"¿por qué rechazaste esta foto?"* con una cadena de reglas trazables — `R8c: contenido_prohibido > 0.10 → ContenidoProhibido` → `R_PROHIBIDO: ContenidoProhibido → RECHAZAR [s=35]` — es lo que hace a los SE apropiados para dominios donde la auditoría humana es necesaria. Esto se implementó mediante el log `engine._fired` que registra cada regla disparada.

---

### 3.8 Compatibilidad y dependencias

**Prompt:**
> "Al deployar en Streamlit Cloud (Python 3.14) aparece: `AttributeError: module 'collections' has no attribute 'Mapping'`. ¿Cómo lo resolvemos sin cambiar las dependencias?"

**Solución implementada:**
```python
for _name in ("Mapping", "MutableMapping", ...):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))
```

**Conexión teórica:**
Aunque este prompt es técnico más que conceptual, ilustra una realidad del desarrollo de SE: la **fragilidad de las dependencias**. `experta` (fork de CLIPS en Python) tiene una dependencia transitiva (`frozendict==1.2`) que no fue actualizada para Python 3.10+. El monkey-patch es una solución pragmática que mantiene la compatibilidad sin modificar código de terceros.

---

### 3.9 Clasificación como IA Híbrida

**Prompt:**
> "¿Nuestro sistema se puede clasificar como Neural Expert System o como sistema híbrido IA simbólica + subsimbólica? ¿Cuál es la diferencia?"

**Respuesta generada y adoptada:**
El sistema es una **IA Híbrida** más que un Neural Expert System. Un Neural ES integra redes neuronales dentro del motor de inferencia mismo. Nuestro sistema mantiene separación arquitectónica clara: CLIP opera como capa perceptual (produce señales numéricas) y Experta opera como capa de razonamiento (aplica política simbólica). Esta separación permite modificar las reglas sin reentrenar el modelo, y actualizar el modelo sin reescribir las reglas.

---

## 4. Reflexión sobre el uso de IA en el desarrollo de un SE

El uso de Claude Code para construir un Sistema Experto genera una paradoja: **una IA subsimbólica (red neuronal) ayudando a construir un sistema de IA simbólica (reglas IF-THEN).**

Durante el desarrollo se observaron tres patrones:

**1. La IA asistente no reemplazó el diseño del conocimiento.**
Las decisiones sobre qué reglas incluir, qué casos son válidos y cuáles no, y cómo balancear precisión vs cobertura, requirieron juicio humano. Claude Code sugirió implementaciones; el conocimiento del dominio (política de fotos de e-commerce) fue aportado por el equipo.

**2. El debugging de reglas reveló limitaciones del modelo subyacente.**
Cuando el sistema producía falsos positivos (vestido rechazado por "datos de contacto", arma aprobada por umbral demasiado alto), el diagnóstico requirió entender el comportamiento de CLIP — algo que la IA asistió a verbalizar pero que el equipo validó empíricamente con imágenes reales. El problema del softmax y su solución mediante sigmoid fue un hallazgo emergente de este proceso.

**3. La IA aceleró la implementación; el tiempo real fue diseño y calibración.**
Escribir 38 reglas en Python con Experta hubiera tomado días sin asistencia. Con Claude Code, la implementación fue rápida. El tiempo real del equipo se invirtió en el diseño conceptual de las reglas, la selección de los prompts de CLIP, y la calibración iterativa de umbrales contra casos de prueba reales.

Esta experiencia ilustra el concepto de **knowledge engineering**: la parte difícil de los SE no es la implementación técnica sino la adquisición, formalización y validación del conocimiento experto. Una herramienta de IA puede automatizar la primera; las otras dos siguen requiriendo expertise humano.

---

*Documento elaborado por el Grupo B · ASIG00131 · UCBA · 2026*
