# Pipeline de Procesamiento de Imágenes para Marketplace de Motos

Automatiza la selección y procesamiento de fotos de motocicletas usando Claude Vision. Clasifica los ángulos de cada imagen, selecciona las mejores para un listing de marketplace y las entrega con fondo blanco, centradas y en un canvas cuadrado estandarizado.

---

## Requisitos

- Python 3.10 o superior
- Cuenta en [Anthropic](https://console.anthropic.com/) con una API key activa

### Dependencias

```bash
pip install anthropic Pillow python-dotenv numpy
```

---

## Configuración

Crea un archivo `.env` en la raíz del proyecto con tu API key de Anthropic:

```
ANTHROPIC_API_KEY=sk-ant-...
```

El script carga este archivo automáticamente al iniciarse. Sin esta variable, la llamada a la API fallará.

---

## Uso

El script principal se encuentra en `scripts/app.py`.

### Sintaxis

```bash
python scripts/app.py <carpeta_entrada> [opciones]
```

### Opciones disponibles

| Opcion       | Descripcion                                      | Valor por defecto     |
|--------------|--------------------------------------------------|-----------------------|
| `--output`   | Carpeta donde se guardan las imagenes procesadas | `<entrada>/output/`   |
| `--size`     | Lado del canvas cuadrado de salida (en pixeles)  | `1000`                |
| `--model`    | Modelo de Claude a usar para clasificacion       | `claude-sonnet-4-6`   |
| `--dry-run`  | Clasifica sin guardar ningun archivo             | desactivado           |

### Ejemplos

Procesar una carpeta con la configuracion por defecto:

```bash
python scripts/app.py C:/fotos/honda_cb500
```

Especificar carpeta de salida y tamaño de canvas:

```bash
python scripts/app.py C:/fotos/honda_cb500 --output C:/marketplace/honda_cb500 --size 1200
```

Solo clasificar las imagenes sin generar archivos de salida:

```bash
python scripts/app.py C:/fotos/honda_cb500 --dry-run
```

Usar un modelo diferente de Claude:

```bash
python scripts/app.py C:/fotos/honda_cb500 --model claude-opus-4-6
```

---

## Formatos de imagen soportados

El pipeline procesa archivos con las extensiones `.jpg`, `.jpeg`, `.png` y `.webp`. Los archivos en otros formatos se omiten con una advertencia en consola.

---

## Clasificacion de angulos

Claude Vision analiza cada imagen y le asigna uno de los siguientes angulos:

| Angulo          | Descripcion                                                                 | Recomendada                      |
|-----------------|-----------------------------------------------------------------------------|----------------------------------|
| `3q-front-right`| Tres cuartos frontal: faro y rueda delantera en el lado DERECHO de la imagen. Se ve el costado izquierdo de la moto. Es la foto principal ideal para marketplace. | Siempre (`true`)                 |
| `3q-front-left` | Tres cuartos frontal: faro y rueda delantera en el lado IZQUIERDO. Orientacion incorrecta para marketplace. | Nunca (`false`)                  |
| `3q-rear`       | Tres cuartos trasero: se ve la parte trasera y un costado de la moto.       | Maximo 1                         |
| `side-left`     | Perfil lateral izquierdo puro, moto completamente de lado.                  | Maximo 1 en total entre side-left y side-right |
| `side-right`    | Perfil lateral derecho puro.                                                | Maximo 1 en total entre side-left y side-right |
| `front`         | Vista completamente frontal.                                                | Maximo 1                         |
| `rear`          | Vista completamente trasera.                                                | Maximo 1                         |
| `detail`        | Acercamiento a una parte especifica: motor, tablero, llanta, etc.           | Maximo 2, deben mostrar partes distintas |
| `other`         | No encaja en ninguna categoria anterior.                                    | No recomendada                   |

Ademas del angulo, Claude asigna un `quality_score` del 1 al 10 que considera nitidez, centrado, iluminacion y si la moto aparece completa en el encuadre.

---

## Archivos de salida

Las imagenes recomendadas por Claude se dividen en dos grupos al guardarse:

**Imagenes principales** (`principal_01.jpg`, `principal_02.jpg`, ...):
- Son las fotos clasificadas como `3q-front-right`.
- Pueden existir varias si el mismo modelo aparece en distintos colores.
- Se ordenan de mayor a menor `quality_score`.

**Galeria** (`galeria_01.jpg`, `galeria_02.jpg`, ...):
- Son todas las demas imagenes recomendadas que no son `3q-front-right`.
- Se guardan en el orden en que Claude las devuelve.

**Fallback sin foto principal:** Si ninguna imagen tiene angulo `3q-front-right`, el script selecciona automaticamente la imagen con el `quality_score` mas alto entre todas las recomendadas y la guarda como `principal_01.jpg`. El resto pasa a galeria normalmente.

Todas las imagenes de salida se guardan en formato JPEG con calidad 90.

---

## Procesamiento de imagen

Cada imagen seleccionada pasa por la funcion `center_and_resize`, que realiza los siguientes pasos:

1. **Deteccion de contenido**: convierte la imagen a escala de grises, aplica un blur gaussiano para reducir el ruido JPEG y detecta los pixeles que pertenecen a la moto (valor menor a 240 en cualquier canal = no es fondo blanco).
2. **Bounding box**: calcula el rectangulo minimo que encierra todos los pixeles detectados.
3. **Recorte**: elimina el fondo sobrante alrededor de la moto.
4. **Escalado**: redimensiona la moto al maximo tamaño posible dentro del canvas, preservando el aspect ratio y dejando un margen del 5% en cada lado.
5. **Centrado**: pega la moto centrada sobre un canvas blanco cuadrado (por defecto 1000x1000 px).

El resultado es una imagen cuadrada con la moto perfectamente centrada sobre fondo blanco, lista para subir a un marketplace.

---

## Flujo completo

```
Carpeta de entrada
       |
       v
 Leer imagenes (JPG, PNG, WEBP)
       |
       v
 Enviar todas las imagenes a Claude Vision
 (en una sola llamada a la API)
       |
       v
 Claude clasifica cada imagen:
   - angulo
   - quality_score
   - is_recommended
       |
       v
 Separar recomendadas en:
   principales (3q-front-right)
   galeria (resto)
       |
       v
 Para cada imagen seleccionada:
   center_and_resize()
       |
       v
 Guardar en carpeta de salida:
   principal_01.jpg, principal_02.jpg...
   galeria_01.jpg, galeria_02.jpg...
```

---

## Notas y comportamiento

### Reintentos automaticos

La llamada a la API de Anthropic incluye logica de reintentos con espera progresiva:

- **Error 529** (API sobrecargada): espera 10, 20 y 30 segundos entre intentos.
- **Errores 5xx** (error de servidor): espera 5, 10 y 15 segundos entre intentos.
- **Error de conexion**: espera 5, 10 y 15 segundos entre intentos.
- Tras 3 intentos fallidos, el script lanza una excepcion y se detiene.

### Respuesta truncada

Si Claude devuelve la respuesta con `stop_reason != "end_turn"`, significa que el JSON fue cortado antes de completarse. Esto puede ocurrir cuando se procesan muchas imagenes a la vez. En ese caso el script lanza un error con el mensaje: `"La respuesta de Claude se cortó. Intenta con menos imágenes."` La solucion es dividir las imagenes en lotes mas pequeños.

### Imagenes con fondo no blanco

La deteccion de contenido asume fondo blanco o muy claro (pixeles >= 240 se consideran fondo). Si la moto ya tiene un fondo oscuro o de color, el recorte puede no funcionar correctamente ya que todos los pixeles se interpretaran como contenido.

### Estructura del proyecto

```
image_handling/
├── scripts/
│   └── app.py          # Script principal
├── .env                # ANTHROPIC_API_KEY=sk-ant-...
└── README.md           # Este archivo
```
