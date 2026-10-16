# Exportador de datos visibles de Instagram

Script en Python para exportar información visible de un perfil de Instagram usando una sesión local autenticada en Chrome. Guarda los resultados en JSON, puede descargar fotos y videos de las publicaciones y conserva checkpoints para continuar una ejecución interrumpida.

> Usa el script solo con tu propia cuenta o con autorización para consultar esos datos. El script consulta endpoints internos de Instagram, que pueden cambiar y dejar de funcionar. Respeta las condiciones de uso de Instagram y la privacidad de las personas cuyos datos se procesen.

## Qué recopila

- Datos del perfil.
- Publicaciones disponibles para la sesión.
- Seguidores y cuentas seguidas disponibles para la sesión.
- Comentarios de las publicaciones, si `GET_COMMENTS = True`.
- Fotos y videos de las publicaciones, si `DOWNLOAD_MEDIA = True`.

La cantidad depende de lo que Instagram permita ver a la cuenta autenticada y de los límites configurados en el script.

## Requisitos

- Python instalado.
- Google Chrome instalado.
- Una sesión de Instagram válida con las cookies `sessionid`, `csrftoken` y `ds_user_id`.
- Paquetes Python `requests` y `selenium`.

## Instalación

Abre una terminal en la carpeta donde guardaste el script y crea un entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install requests selenium
```

Selenium inicia Chrome mediante WebDriver. En instalaciones actuales, Selenium Manager suele encargarse de localizar o preparar el controlador necesario.

## Configuración

1. En el script, cambia `USERNAME` por el usuario que quieres consultar.
2. En la misma carpeta del script, crea `instagram_cookies.py` con las cookies de una sesión autorizada:

```python
INSTAGRAM_COOKIES = "sessionid=VALOR; csrftoken=VALOR; ds_user_id=123456789"
```

El valor debe ser una cadena de cookies separadas por punto y coma. `ds_user_id` debe ser numérico. No compartas este archivo: las cookies pueden dar acceso a tu cuenta.

3. Añade al `.gitignore` del proyecto:

```gitignore
instagram_cookies.py
instagram_export/
```

El script no genera ni extrae las cookies por sí mismo; las lee del archivo local `instagram_cookies.py`.

## Ejecución

Guarda el código, por ejemplo, como `export_instagram.py`, y ejecútalo desde su carpeta:

```powershell
python export_instagram.py
```

Chrome se abrirá mientras el script realiza las consultas. Al terminar o detenerse, se cierra automáticamente.

## Archivos generados

Por defecto, el script guarda los resultados en `instagram_export/`:

| Archivo o carpeta | Contenido |
| --- | --- |
| `1_perfil.json` | Respuesta de datos del perfil |
| `2_publicaciones.json` | Publicaciones recopiladas |
| `4_seguidores.json` | Seguidores recopilados |
| `5_seguidos.json` | Cuentas seguidas recopiladas |
| `6_comentarios.json` | Comentarios agrupados por ID de publicación |
| `7_resumen.json` | Conteos, páginas y estado de finalización |
| `media/<usuario>/` | Fotos y videos descargados |
| `media_report.json` | Resultado de la descarga de medios y errores encontrados |
| `.checkpoints/` | Estado para reanudar las páginas y comentarios pendientes |

Los JSON se escriben en UTF-8. Las publicaciones, seguidores y cuentas seguidas se guardan a medida que avanzan las páginas.

## Reanudar una ejecución

Si el proceso se interrumpe o recibe un límite, vuelve a ejecutarlo desde la misma carpeta y conserva `instagram_export/.checkpoints/`. El script carga el cursor guardado y continúa las páginas pendientes; también omite comentarios ya procesados y medios que ya existan en disco.

Para empezar una exportación nueva, elimina manualmente `instagram_export/` antes de ejecutar el script. Esto también borra los datos exportados y los checkpoints anteriores.

## Límites y errores

- El script espera `REQUEST_DELAY_SECONDS` entre solicitudes a la API y un segundo entre descargas de medios.
- Ante HTTP 429 de la API, detiene la recopilación, informa el valor `Retry-After` si Instagram lo envía y conserva el progreso. No reintenta automáticamente esa solicitud.
- Ante HTTP 429 del servidor de medios, detiene las descargas de medios pendientes y registra el resultado en `media_report.json`.
- Los errores de red y las respuestas HTTP 5xx pueden reintentarse hasta `MAX_TRANSIENT_RETRIES` veces. Los errores 401 o 403 detienen el proceso para que se revise la sesión.
- Los endpoints consultados no son una API pública estable. Un cambio de Instagram puede requerir actualizar el script.

## Opciones principales

Puedes modificar estas constantes al inicio del script:

| Constante | Valor predeterminado | Efecto |
| --- | --- | --- |
| `OUTPUT_DIR` | `instagram_export` | Carpeta de salida |
| `REQUEST_DELAY_SECONDS` | `5` | Pausa entre solicitudes a la API |
| `PAGE_SIZE` | `12` | Elementos solicitados por página |
| `MAX_POSTS` | `None` | Límite de publicaciones; `None` intenta recorrer todas las páginas disponibles |
| `MAX_FOLLOWERS` | `None` | Límite por lista de seguidores y seguidos; `None` intenta recorrer todas las páginas disponibles |
| `DOWNLOAD_MEDIA` | `True` | Activa o desactiva las descargas de fotos y videos |
| `GET_COMMENTS` | `True` | Activa o desactiva la recopilación de comentarios |

Si estableces un límite máximo, el resumen indicará que la recopilación es parcial cuando queden más páginas disponibles.
