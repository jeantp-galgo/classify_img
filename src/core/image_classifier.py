import time
import json
import base64
from pathlib import Path
from src.utils.prompts_utils import read_prompt

# Defaults por provider
_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-flash",
}

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "data" / "input" / "prompts"
_REF_IMG_DIR = Path(__file__).resolve().parent.parent / "data" / "input" / "img_example"


# ---------------------------------------------------------------------------
# Llamadas al API
# ---------------------------------------------------------------------------

def _call_anthropic(images: list[dict], prompt_text: str, model: str, max_retries: int, system_prompt: str = "") -> str:
    import anthropic
    client = anthropic.Anthropic()

    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": img["media_type"], "data": img["base64"]},
        })
        content.append({"type": "text", "text": f"Archivo: {img['filename']}"})
    content.append({"type": "text", "text": prompt_text})

    estimated_tokens = max(4096, len(images) * 80)
    kwargs = {
        "model": model,
        "max_tokens": estimated_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    for attempt in range(max_retries):
        try:
            response = client.messages.create(**kwargs)
            break
        except anthropic.APIStatusError as e:
            if e.status_code in (529, 500):
                wait = 10 * (attempt + 1)
                print(f"  [WARN] Error Anthropic ({e.status_code}), esperando {wait}s...")
                time.sleep(wait)
            else:
                raise
        except anthropic.APIConnectionError:
            wait = 5 * (attempt + 1)
            print(f"  [WARN] Error de conexión (intento {attempt+1}/{max_retries}), esperando {wait}s...")
            time.sleep(wait)
    else:
        raise RuntimeError(f"No se pudo conectar a la API de Anthropic después de {max_retries} intentos")

    if response.stop_reason != "end_turn":
        raise RuntimeError(f"Respuesta Anthropic truncada (stop_reason={response.stop_reason})")

    return response.content[0].text.strip()


def _call_gemini(images: list[dict], prompt_text: str, model: str, max_retries: int, system_prompt: str = "") -> str:
    import os
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    parts = []
    for img in images:
        raw_bytes = base64.standard_b64decode(img["base64"])
        parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=img["media_type"]))
        parts.append(types.Part.from_text(text=f"Archivo: {img['filename']}"))
    parts.append(types.Part.from_text(text=prompt_text))

    config = types.GenerateContentConfig(system_instruction=system_prompt) if system_prompt else None

    response = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(model=model, contents=parts, config=config)

            # Verificar si la respuesta tiene contenido
            if response.text and response.text.strip():
                return response.text.strip()

            # Si la respuesta viene vacía, verificar si hay bloqueos de seguridad
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason'):
                    finish_reason = candidate.finish_reason
                    if finish_reason in ('SAFETY', 'RECITATION', 'OTHER'):
                        print(f"  [WARN] Respuesta bloqueada por seguridad (finish_reason={finish_reason}), reintentando...")
                        if attempt < max_retries - 1:
                            time.sleep(5 * (attempt + 1))
                            continue

            # Si llegamos aquí y no hay texto, reintentar
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  [WARN] Respuesta vacía de Gemini (intento {attempt+1}/{max_retries}), esperando {wait}s...")
                time.sleep(wait)
            else:
                # Último intento falló, intentar obtener más información
                error_info = ""
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        error_info = f" (finish_reason: {candidate.finish_reason})"
                raise RuntimeError(f"La respuesta de Gemini vino vacía después de {max_retries} intentos{error_info}")

        except Exception as e:
            err_str = str(e).lower()
            if any(c in err_str for c in ["503", "429", "500", "overloaded", "quota", "connection"]):
                wait = 10 * (attempt + 1)
                print(f"  [WARN] Error Gemini (intento {attempt+1}/{max_retries}), esperando {wait}s... ({e})")
                time.sleep(wait)
            else:
                # Si es el último intento, relanzar el error
                if attempt == max_retries - 1:
                    raise
                # Si no, esperar y reintentar
                wait = 5 * (attempt + 1)
                print(f"  [WARN] Error inesperado (intento {attempt+1}/{max_retries}), esperando {wait}s... ({e})")
                time.sleep(wait)

    # Si llegamos aquí sin respuesta válida
    raise RuntimeError(f"No se pudo obtener respuesta válida de Gemini después de {max_retries} intentos")


# ---------------------------------------------------------------------------
# Referencias y clasificación individual
# ---------------------------------------------------------------------------

def _load_reference_images() -> list[dict]:
    """Carga las 3 imágenes de referencia etiquetadas como PRINCIPAL."""
    ref_images = []
    for i in range(1, 4):
        path = _REF_IMG_DIR / f"image{i}.jpg"
        raw = path.read_bytes()
        ref_images.append({
            "filename": f"REFERENCIA: Esta es una IMAGEN PRINCIPAL correcta.",
            "base64": base64.standard_b64encode(raw).decode(),
            "media_type": "image/jpeg",
        })
    return ref_images


def _classify_single(
    ref_images: list[dict],
    target_img: dict,
    prompt_text: str,
    model: str,
    max_retries: int,
    provider: str,
) -> dict:
    """Clasifica una imagen contra las 3 referencias. Retorna dict con is_principal y quality_score."""
    # Construir lista: 3 refs + 1 target
    images = ref_images + [target_img]

    # System prompt estricto para reforzar las reglas
    system_prompt = (
        "Eres un clasificador estricto de imágenes de motos. "
        "CRÍTICO: Las imágenes principales tienen el faro en el lado DERECHO del encuadre. "
        "Si el faro está en el lado IZQUIERDO, SIEMPRE marca 'is_principal: false'. "
        "Solo marca 'is_principal: true' si la dirección y orientación coinciden EXACTAMENTE con las referencias. "
        "Si tienes CUALQUIER duda sobre la dirección, marca 'is_principal: false'. "
        "Sé extremadamente conservador y estricto en tu evaluación."
    )

    try:
        raw = (
            _call_anthropic(images, prompt_text, model, max_retries, system_prompt=system_prompt)
            if provider == "anthropic"
            else _call_gemini(images, prompt_text, model, max_retries, system_prompt=system_prompt)
        )
    except Exception as e:
        # Si falla la llamada a la API, usar valor conservador por defecto
        print(f"  [ERROR] Error al clasificar '{target_img['filename']}': {e}")
        print(f"         → Usando valor conservador: is_principal=False, quality_score=5")
        return {
            "filename": target_img["filename"],
            "is_principal": False,
            "quality_score": 5,
        }

    # Parsear respuesta JSON
    cleaned = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"  [WARN] No se pudo parsear respuesta para '{target_img['filename']}': {raw!r}")
        # Si no se puede parsear, asumir que NO es principal (conservador)
        result = {"is_principal": False, "quality_score": 5}

    # Validación de seguridad: si la respuesta menciona "izquierda" en contexto de dirección, forzar False
    raw_lower = raw.lower()
    if any(phrase in raw_lower for phrase in ["apunta a la izquierda", "hacia la izquierda", "lado izquierdo", "faro izquierdo", "orientada izquierda"]):
        if result.get("is_principal", False):
            print(f"  [WARN] Detectada mención de 'izquierda' pero is_principal=True. Forzando a False para '{target_img['filename']}'")
            result["is_principal"] = False

    # Validación adicional: asegurar que is_principal es booleano
    is_principal = result.get("is_principal", False)
    if isinstance(is_principal, str):
        is_principal = is_principal.lower() in ("true", "1", "yes", "si")
    is_principal = bool(is_principal)

    return {
        "filename": target_img["filename"],
        "is_principal": is_principal,
        "quality_score": int(result.get("quality_score", 5)),
    }


# ---------------------------------------------------------------------------
# Ensamble final
# ---------------------------------------------------------------------------

def _assemble_from_principal(results: list[dict], max_gallery: int = 5) -> list[dict]:
    """
    Convierte resultados binarios al formato que espera app.py.
      - is_principal=True  → angle="3q-front-right", is_recommended=True
      - is_principal=False → angle="other", is_recommended=True para las top max_gallery por quality_score
    """
    non_principal = sorted(
        [r for r in results if not r["is_principal"]],
        key=lambda x: -x["quality_score"],
    )
    gallery_recommended = {r["filename"] for r in non_principal[:max_gallery]}

    final = []
    for r in results:
        if r["is_principal"]:
            angle = "3q-front-right"
            is_recommended = True
        else:
            angle = "other"
            is_recommended = r["filename"] in gallery_recommended
        final.append({
            "filename": r["filename"],
            "angle": angle,
            "quality_score": r["quality_score"],
            "is_recommended": is_recommended,
        })

    final.sort(key=lambda x: x["filename"])
    return final


# ---------------------------------------------------------------------------
# Punto de entrada público
# ---------------------------------------------------------------------------

def classify_and_select(
    images: list[dict],
    provider: str = "gemini",
    model: str | None = None,
    max_retries: int = 3,
) -> list[dict]:
    """
    Clasifica imágenes de motos usando few-shot visual:
    Envía cada imagen junto con 3 referencias etiquetadas como PRINCIPAL
    y pregunta: ¿es esta imagen principal como las referencias?
    """
    if provider not in _DEFAULT_MODELS:
        raise ValueError(f"Provider desconocido: '{provider}'. Usa 'gemini' o 'anthropic'.")

    resolved_model = model or _DEFAULT_MODELS[provider]
    print(f"  Provider: {provider} | Modelo: {resolved_model}")

    ref_images = _load_reference_images()
    prompt_text = read_prompt(str(_PROMPTS_DIR / "principal-detector.md"))

    results = []
    for i, img in enumerate(images, 1):
        print(f"  [{i}/{len(images)}] Clasificando '{img['filename']}'...")
        result = _classify_single(ref_images, img, prompt_text, resolved_model, max_retries, provider)
        tag = "PRINCIPAL" if result["is_principal"] else "other"
        print(f"         → {tag} (quality={result['quality_score']})")
        results.append(result)

    return _assemble_from_principal(results)
