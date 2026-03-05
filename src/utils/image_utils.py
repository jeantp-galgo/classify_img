from pathlib import Path
from PIL import Image, ImageFilter
import numpy as np

def center_and_resize(
    img_path: Path,
    target_size: int = 1000,
    bg_color: tuple = (255, 255, 255),
    padding_pct: float = 0.05,
    threshold: int = 240,
) -> Image.Image:
    """
    Centra la moto en un canvas cuadrado de target_size x target_size.

    Lógica:
    1. Convierte a escala de grises
    2. Threshold para encontrar píxeles no-blancos (la moto)
    3. Calcula bounding box del contenido
    4. Recorta, escala manteniendo aspect ratio con padding
    5. Pega centrado en canvas blanco

    Args:
        threshold: píxeles con valor > threshold se consideran "fondo".
                   240 funciona bien para fondos blancos/casi blancos.
        padding_pct: porcentaje del canvas que se deja como margen (0.05 = 5%)
    """
    img = Image.open(img_path).convert("RGBA")

    # Crear máscara: píxeles que NO son fondo blanco
    rgb = img.convert("RGB")

    # Aplicar leve blur para ignorar ruido/artefactos JPEG
    blurred = rgb.filter(ImageFilter.GaussianBlur(radius=2))

    # Encontrar bounding box del contenido con NumPy (mucho más rápido que pixel a pixel)
    arr = np.array(blurred)
    # Máscara: True donde CUALQUIER canal está por debajo del threshold (= contenido, no fondo)
    mask = np.any(arr < threshold, axis=2)

    if not mask.any():
        # No se encontró contenido, devolver imagen redimensionada tal cual
        return img.convert("RGB").resize((target_size, target_size), Image.LANCZOS)

    # Obtener coordenadas del bounding box desde la máscara
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    min_y, max_y = np.where(rows)[0][[0, -1]]
    min_x, max_x = np.where(cols)[0][[0, -1]]

    # Recortar al bounding box del contenido
    cropped = img.crop((int(min_x), int(min_y), int(max_x) + 1, int(max_y) + 1))

    # Calcular tamaño disponible con padding
    available = int(target_size * (1 - 2 * padding_pct))

    # Escalar manteniendo aspect ratio
    cw, ch = cropped.size
    scale = min(available / cw, available / ch)
    new_w = int(cw * scale)
    new_h = int(ch * scale)
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    # Crear canvas y pegar centrado
    canvas = Image.new("RGBA", (target_size, target_size), (*bg_color, 255))
    offset_x = (target_size - new_w) // 2
    offset_y = (target_size - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    return canvas.convert("RGB")