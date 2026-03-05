Analiza estas imágenes de una motocicleta para un marketplace.

---

## MARCO DE REFERENCIA: EL ESPECTRO DE ÁNGULOS

Imagina que una moto está parada y tú caminas a su alrededor. Los ángulos posibles forman un espectro continuo:

  FRENTE PURO → 3q-front → PERFIL LATERAL → 3q-rear → TRASERA PURA

Las categorías válidas, en orden de ese espectro, son:
  front → 3q-front-right / 3q-front-left → side-right / side-left → 3q-rear → rear

---

## DESCRIPCIÓN DE CADA ÁNGULO

Usa EXACTAMENTE uno de estos valores para "angle":

### "3q-front-right" — ÁNGULO PRINCIPAL DEL MARKETPLACE
Esta es la vista estrella. La moto está orientada hacia la derecha del encuadre y el espectador ve
predominantemente el COSTADO IZQUIERDO de la moto, con una leve perspectiva que muestra una pequeña
porción del frente.

Características visuales clave — TODAS deben cumplirse:
  1. La moto apunta hacia la DERECHA del encuadre (el faro mira hacia la derecha).
  2. El COSTADO IZQUIERDO completo de la moto es lo más visible: se ven claramente el chasis lateral,
     el escape (si está del lado izquierdo), los pedales y la mayor parte de la longitud de la moto.
  3. La perspectiva frontal es LEVE: el frente de la moto no domina la imagen. Si el faro y la horquilla
     frontal ocupan más de un 30% del ancho visual de la moto, el ángulo es demasiado frontal — usa
     "front" en su lugar.
  4. La rueda trasera es claramente visible (no está oculta ni cortada).
  5. NO se ve la luz trasera roja ni el escape trasero en primer plano.

Pregunta de diagnóstico de dos pasos:
  Paso 1 — Orientación: ¿La moto apunta hacia la DERECHA del encuadre? Si no → usa "3q-front-left", "side-left", "3q-rear" u otro.
  Paso 2 — Profundidad: ¿El costado izquierdo de la moto ocupa la mayor parte del campo visual (más del 60% de la longitud total de la moto es visible de perfil)? Si no, y el frente domina → usa "front".

Casos frecuentes de confusión:
  - Si la moto apunta a la derecha PERO el frente domina casi como una vista frontal → es "front", no "3q-front-right".
  - Si la moto está completamente de perfil sin ninguna perspectiva frontal visible → es "side-left", no "3q-front-right".
  - La imagen objetivo ideal está entre el perfil puro y el tres cuartos clásico: es MAYORMENTE de perfil, con una leve inclinación que muestra una pequeña porción del frente.

### "3q-front-left"
Igual que "3q-front-right" pero la moto apunta hacia la IZQUIERDA del encuadre. Se ve el costado
DERECHO de la moto con leve perspectiva frontal. Orientación incorrecta para el marketplace.

### "side-left"
Perfil lateral IZQUIERDO puro. La cámara está perpendicular al eje longitudinal de la moto.
  - La moto está completamente de lado, apuntando hacia la derecha del encuadre.
  - Se ve el costado izquierdo completo: ambas ruedas a igual distancia de sus respectivos bordes del encuadre.
  - NO hay ninguna perspectiva frontal o trasera: el faro y la luz trasera son apenas visibles o no se ven.
  - El eje de la moto es horizontal en la imagen.

Distinción clave con "3q-front-right": en side-left NO se ve ninguna porción del frente de la moto.
En "3q-front-right" SÍ se ve una pequeña porción del frente.

### "side-right"
Igual que "side-left" pero desde el costado DERECHO de la moto. La moto apunta hacia la izquierda
del encuadre. Se ven los componentes del lado derecho (escape si está a la derecha, etc.).

### "front"
Vista completamente frontal o con ángulo frontal DOMINANTE.
  - El faro y la horquilla frontal están centrados o casi centrados.
  - Las dos ruedas (delantera y trasera) se superponen visualmente o la trasera no es visible.
  - El frente de la moto ocupa la mayor parte del campo visual.

### "rear"
Vista completamente trasera o con ángulo trasero dominante.
  - La luz trasera roja está centrada o casi centrada.
  - Se ve el escape y la rueda trasera de frente.

### "3q-rear"
Tres cuartos trasero: se ve la parte trasera de la moto y un costado.
  - La luz trasera roja y el escape son visibles y prominentes.
  - Se ve un costado de la moto (lateral).
  - No es un perfil puro ni una trasera pura.

### "detail"
Acercamiento (close-up) a una parte específica: motor, tablero, llanta, manubrio, escape, etc.
La moto completa no está en el encuadre.

### "other"
No encaja en ninguna categoría anterior.

---

## CAMPOS A DEVOLVER POR IMAGEN

Para CADA imagen, devuelve:
- "filename": nombre del archivo
- "angle": uno de los valores definidos arriba (exactamente como está escrito)
- "quality_score": entero del 1 al 10, evaluando: nitidez, centrado de la moto, iluminación uniforme,
  moto completa dentro del encuadre (sin cortes en ruedas o extremos)
- "is_recommended": true o false — si esta imagen aporta valor único al listing

---

## CRITERIOS PARA is_recommended

- "3q-front-right": SIEMPRE true. Pueden existir varias (distintos colores del mismo modelo) y todas se recomiendan.
- "3q-front-left": SIEMPRE false. Orientación incorrecta para el marketplace.
- "side-left" y "side-right" en conjunto: recomienda MÁXIMO UNA imagen entre ambos tipos.
  Elige la de mayor quality_score. En caso de empate, prefiere la más perpendicular (perfil más puro).
  Razón: el comprador solo necesita ver un perfil lateral.
- "3q-rear": MÁXIMO UNA, la de mayor quality_score.
- "front" y "rear": MÁXIMO UNA de cada tipo, solo si aporta información visual que las otras vistas no cubren.
- "detail": MÁXIMO DOS, solo si son nítidas y muestran partes distintas de la moto.
- Ante la duda entre dos imágenes similares del mismo ángulo, SIEMPRE descarta la de menor quality_score.
- El listing ideal tiene: todas las 3q-front-right + 1 side + 1 3q-rear. Máximo 6-7 imágenes totales recomendadas.

---

## FORMATO DE RESPUESTA

Responde SOLO con un JSON array. Sin markdown, sin texto adicional, sin explicaciones.

Ejemplo:
[{"filename": "img1.jpg", "angle": "3q-front-right", "quality_score": 9, "is_recommended": true}]
