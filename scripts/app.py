"""
Pipeline de procesamiento de imágenes para marketplace de motos.
Requiere: pip install anthropic Pillow python-dotenv numpy

Flujo:
1. Lee imágenes de una carpeta local
2. Claude Vision clasifica ángulos y selecciona las mejores
3. Pillow centra y redimensiona sobre fondo blanco
4. Guarda con nombres estandarizados

Uso:
    python app.py /ruta/a/carpeta/imagenes --output /ruta/salida --size 1000
"""
import sys
from pathlib import Path

# Agrega la raíz del proyecto al path (un nivel arriba de /scripts/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Cargar .env antes de cualquier otra cosa
from dotenv import load_dotenv
load_dotenv()
import base64
from PIL import Image
import argparse
from src.core.image_classifier import classify_and_select
from src.utils.image_utils import center_and_resize


# --- Config ---
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

def load_images_from_folder(folder: Path) -> list[dict]:
    """Carga imágenes de una carpeta y las prepara para la API."""
    images = []
    # Mapa de formato Pillow → media type para la API de Anthropic
    format_map = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}

    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in SUPPORTED_EXT:
            # Detectar formato real con Pillow (ignora la extensión del archivo)
            with Image.open(f) as img:
                real_format = img.format  # "JPEG", "PNG", "WEBP", etc.

            media_type = format_map.get(real_format, "image/jpeg")

            if real_format not in format_map:
                print(f"  [WARN] Formato no soportado ({real_format}) en {f.name}, se omite")
                continue

            with open(f, "rb") as img_file:
                b64 = base64.standard_b64encode(img_file.read()).decode("utf-8")

            images.append({
                "filename": f.name,
                "path": f,
                "base64": b64,
                "media_type": media_type,
            })
    return images


def run_pipeline(
    input_folder: str,
    output_folder: str | None = None,
    target_size: int = 1000,
    model: str = "claude-sonnet-4-6",
    dry_run: bool = False,
):
    """
    Pipeline completo.

    Args:
        input_folder: carpeta con imágenes de UNA moto
        output_folder: carpeta de salida (default: input_folder/output)
        target_size: tamaño del canvas cuadrado
        model: modelo de Claude a usar
        dry_run: si True, solo clasifica y muestra resultados sin procesar
    """
    input_path = Path(input_folder)
    if not input_path.is_dir():
        print(f"[ERROR] {input_folder} no es una carpeta válida")
        sys.exit(1)

    output_path = Path(output_folder) if output_folder else input_path / "output"
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Cargar imágenes
    images = load_images_from_folder(input_path)
    if not images:
        print(f"[ERROR] No se encontraron imágenes en {input_folder}")
        sys.exit(1)

    print(f"Encontradas {len(images)} imágenes en {input_folder}")

    # 2. Clasificar y seleccionar con Claude Vision
    print("Clasificando con Claude Vision...")
    classifications = classify_and_select(images, model=model)

    # Mostrar resultados
    print("\n--- Clasificación ---")
    for c in classifications:
        status = "✓ RECOMENDADA" if c["is_recommended"] else "  descartada"
        print(f"  {status} | {c['filename']:30s} | {c['angle']:16s} | score: {c['quality_score']}")

    if dry_run:
        print("\n[DRY RUN] No se procesaron imágenes.")
        return classifications

    # 3. Procesar solo las recomendadas
    recommended = [c for c in classifications if c["is_recommended"]]
    if not recommended:
        print("[WARN] Claude no recomendó ninguna imagen. Revisa las originales.")
        return classifications

    # Separar principales (3q-front-right) del resto de galería
    principales = sorted(
        [c for c in recommended if c["angle"] == "3q-front-right"],
        key=lambda x: -x["quality_score"]
    )
    galeria = [c for c in recommended if c["angle"] != "3q-front-right"]

    # Si no hay ninguna 3q-front-right, usar la de mejor score general como principal
    if not principales:
        best = max(recommended, key=lambda x: x["quality_score"])
        principales = [best]
        galeria = [c for c in recommended if c["filename"] != best["filename"]]
        print(f"[WARN] No se encontró ángulo 3q-front-right. Usando {best['filename']} como principal.")

    # Construir mapa filename -> path
    path_map = {img["filename"]: img["path"] for img in images}

    # 4. Centrar, redimensionar y guardar
    total = len(principales) + len(galeria)
    print(f"\nProcesando {total} imágenes ({len(principales)} principal(es) + {len(galeria)} galería)...")

    # Guardar principales: principal_01.jpg, principal_02.jpg, ...
    for idx, c in enumerate(principales, start=1):
        fname = c["filename"]
        src_path = path_map.get(fname)
        if not src_path:
            print(f"  [WARN] No se encontró archivo: {fname}")
            continue
        out_name = f"principal_{idx:02d}.jpg"
        processed = center_and_resize(src_path, target_size=target_size)
        out_path = output_path / out_name
        processed.save(out_path, "JPEG", quality=90)
        print(f"  {fname} → {out_name} ({c['angle']}, score: {c['quality_score']})")

    # Guardar galería
    for idx, c in enumerate(galeria, start=1):
        fname = c["filename"]
        src_path = path_map.get(fname)
        if not src_path:
            print(f"  [WARN] No se encontró archivo: {fname}")
            continue
        out_name = f"galeria_{idx:02d}.jpg"
        processed = center_and_resize(src_path, target_size=target_size)
        out_path = output_path / out_name
        processed.save(out_path, "JPEG", quality=90)
        print(f"  {fname} → {out_name} ({c['angle']})")

    print(f"\n✓ Imágenes guardadas en: {output_path}")
    return classifications


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de imágenes para marketplace de motos")
    parser.add_argument("input", help="Carpeta con imágenes de una moto")
    parser.add_argument("--output", "-o", help="Carpeta de salida (default: input/output)")
    parser.add_argument("--size", "-s", type=int, default=1000, help="Tamaño del canvas cuadrado (default: 1000)")
    parser.add_argument("--model", "-m", default="claude-sonnet-4-6", help="Modelo de Claude")
    parser.add_argument("--dry-run", action="store_true", help="Solo clasificar, no procesar")
    args = parser.parse_args()

    run_pipeline(
        input_folder=args.input,
        output_folder=args.output,
        target_size=args.size,
        model=args.model,
        dry_run=args.dry_run,
    )