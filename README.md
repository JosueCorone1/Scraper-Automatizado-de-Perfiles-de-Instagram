# Instagram Scraper (adaptación local)

Herramienta de línea de comandos en Python para recopilar y guardar localmente información que Instagram entrega para un perfil. Exporta los resultados en JSON y puede descargar fotos y videos disponibles.

Este proyecto adapta el código de [`omkarcloud/instagram-scraper`](https://github.com/omkarcloud/instagram-scraper). Esta versión se ejecuta localmente con `main.py`; no inicia el servidor REST del proyecto original ni usa Meta Graph API o una clave de RapidAPI. Para consultar Instagram emplea endpoints web y móviles internos, que pueden cambiar o limitar las solicitudes.

## Funciones

- Guarda información básica del perfil.
- Recopila publicaciones y reels disponibles, siguiendo la paginación que entregue Instagram.
- Intenta recopilar seguidores, seguidos, destacados y comentarios.
- Descarga los medios disponibles de publicaciones, reels y destacados.
- Genera un resumen con el estado y el número de elementos de cada colección.

La cantidad de datos depende de la visibilidad del perfil, de la sesión configurada y de las respuestas de Instagram. Una colección puede quedar parcial o fallar; el scraper no garantiza una exportación completa.

## Requisitos

- Python 3.12 (la imagen Docker del proyecto está basada en Python 3.12).
- Conexión a Internet.
- Una sesión propia de Instagram y sus cookies, configuradas localmente.
- `curl_cffi`, la dependencia externa usada para las solicitudes HTTP.

## Instalación

Desde la carpeta raíz del proyecto, crea y activa un entorno virtual.

```powershell
# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install curl_cffi
```

En macOS o Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install curl_cffi
```

## Configuración

### Cookies

En la raíz del proyecto, crea o edita `instagram_cookies.py` con el encabezado Cookie de tu propia sesión:

```python
INSTAGRAM_COOKIES = "sessionid=TU_SESSIONID; csrftoken=TU_CSRFTOKEN; ds_user_id=TU_ID"
```

Sustituye los valores de ejemplo por los de tu sesión. Las cookies son credenciales: no las publiques, no las incluyas en capturas ni las compartas. El archivo `instagram_cookies.py` está excluido de Git por `.gitignore`. Antes de subir el proyecto, confirma que no aparece en `git status` ni quedó incluido en un commit anterior. Si una cookie se expone, cierra esa sesión de Instagram y vuelve a iniciar sesión para invalidarla.

El scraper lee las cookies de `instagram_cookies.py`; también puede leerlas de la variable de entorno `INSTAGRAM_COOKIES`. No es necesario ponerlas en `config.py` ni en el código fuente.

### Perfil objetivo

En `main.py`, cambia `TARGET_USERNAME` por el nombre de usuario que quieras consultar:

```python
TARGET_USERNAME = "jhonatan.coronel"
```

## Ejecución

Ejecuta el programa desde la carpeta raíz:

```bash
python main.py
```

También se puede usar el punto de entrada compatible:

```bash
python run.py
```

## Resultados

Los archivos se escriben en `output/`, que está excluida de Git:

```text
output/
├── profile_<usuario>.json
├── posts_<usuario>.json
├── reels_<usuario>.json
├── followers_<usuario>.json
├── following_<usuario>.json
├── highlights_<usuario>.json
├── comments_<usuario>.json
├── summary_<usuario>.json
└── media/<usuario>/
    ├── posts/
    ├── reels/
    └── highlights/
```

Los JSON indican si la recopilación quedó completa, parcial o falló, e incluyen información del error cuando está disponible. `summary_<usuario>.json` reúne el estado y el conteo de las colecciones.

## Límites y errores

Instagram puede responder con `429 Too Many Requests`, pedir una verificación, bloquear temporalmente una solicitud o cambiar sus endpoints. Si ocurre, el resultado puede quedar parcial. Detén la ejecución y espera antes de volver a intentarlo; repetir solicitudes rápidamente puede prolongar el bloqueo. El programa no puede garantizar que una cookie permita acceder a todos los datos.

Utiliza el scraper solo con datos a los que tengas autorización para acceder. Respeta la privacidad, los derechos de las personas, las condiciones de Instagram y la legislación aplicable.

## Atribución y licencia

Este repositorio adapta código de [`omkarcloud/instagram-scraper`](https://github.com/omkarcloud/instagram-scraper), cuyo autor y titular del aviso de copyright indicado en el proyecto original es Chetan Jain. Se conserva el aviso de copyright y la licencia MIT en [`LICENSE`](LICENSE). Consulta también la [licencia del repositorio original](https://github.com/omkarcloud/instagram-scraper/blob/master/LICENSE).

Al redistribuir esta adaptación, conserva `LICENSE` y los avisos de atribución correspondientes al código original.
