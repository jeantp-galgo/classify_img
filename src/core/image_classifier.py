import anthropic
import time
import json
from pathlib import Path
from src.utils.prompts_utils import read_prompt

def classify_and_select(
    images: list[dict],
    model: str = "claude-sonnet-4-6",
    max_retries: int = 3,
) -> list[dict]:
    """
    Envía todas las imágenes a Claude Vision para clasificación y selección.
    Incluye retry con backoff para errores transitorios (overloaded, network, etc.)
    y validación de que la respuesta no se haya truncado.
    """
    client = anthropic.Anthropic()  # Lee ANTHROPIC_API_KEY del .env

    # Armar el contenido: intercalar cada imagen con su nombre
    content = []
    for img in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": img["media_type"],
                "data": img["base64"],
            }
        })
        content.append({
            "type": "text",
            "text": f"Archivo: {img['filename']}"
        })

    content.append({"type": "text", "text": read_prompt(str(Path(__file__).resolve().parent.parent / "data" / "input" / "prompts" / "image-classifier.md"))})

    # max_tokens: ~120 tokens por imagen es suficiente para el JSON de clasificación
    estimated_tokens = max(4096, len(images) * 120)

    # Retry con backoff exponencial
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=estimated_tokens,
                messages=[{"role": "user", "content": content}]
            )
            break  # éxito, salir del retry loop
        except anthropic.APIStatusError as e:
            if e.status_code == 529:  # overloaded
                wait = 10 * (attempt + 1)
                print(f"  [WARN] Servidor saturado (intento {attempt+1}/{max_retries}), esperando {wait}s...")
                time.sleep(wait)
            elif e.status_code >= 500:  # errores internos del servidor
                wait = 5 * (attempt + 1)
                print(f"  [WARN] Error del servidor ({e.status_code}), reintentando en {wait}s...")
                time.sleep(wait)
            else:
                raise  # errores 4xx (auth, bad request, etc.) no reintentar
        except anthropic.APIConnectionError:
            wait = 5 * (attempt + 1)
            print(f"  [WARN] Error de conexión (intento {attempt+1}/{max_retries}), reintentando en {wait}s...")
            time.sleep(wait)
    else:
        raise RuntimeError(f"No se pudo conectar a la API después de {max_retries} intentos")

    # Verificar que la respuesta no fue truncada por límite de tokens
    if response.stop_reason != "end_turn":
        print(f"[ERROR] Respuesta truncada (stop_reason={response.stop_reason})")
        print(f"  Tokens usados: {response.usage.output_tokens}/{estimated_tokens}")
        raise RuntimeError("La respuesta de Claude se cortó. Intenta con menos imágenes.")

    # Parsear respuesta JSON
    raw = response.content[0].text.strip()
    # Limpiar por si viene con backticks
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        results = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[ERROR] No se pudo parsear la respuesta de Claude:\n{raw}")
        raise e

    # Validar que los filenames devueltos por Claude coincidan con los reales
    real_filenames = {img["filename"] for img in images}
    for item in results:
        if item["filename"] not in real_filenames:
            print(f"  [WARN] Claude inventó un filename: '{item['filename']}' — se ignora")
    results = [r for r in results if r["filename"] in real_filenames]

    # Deduplicar: si Claude devolvió el mismo filename más de una vez, quedarse con la primera
    seen = set()
    deduplicated = []
    for item in results:
        if item["filename"] not in seen:
            seen.add(item["filename"])
            deduplicated.append(item)
        else:
            print(f"  [WARN] Claude duplicó el filename: '{item['filename']}' — se ignora la entrada extra")
    results = deduplicated

    return results