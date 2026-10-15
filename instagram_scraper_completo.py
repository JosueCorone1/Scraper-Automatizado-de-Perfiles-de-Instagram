
import json
import os
import random
import time

import requests
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

# ---------------- CONFIGURACIÓN ----------------
USERNAME = "jhonatan.coronel"

COOKIES = {
    "sessionid": "47441424814%3AltWAS7UPMF2pPx%3A29%3AAYn9L3v4j7IPcvTHJ8nPBUbHEAUvu7vE1uZu7FB-sA",
    "csrftoken": "DREAYg2olLGI4A2whGOwUvk5BJFK7qgh",
    "ds_user_id": "47441424814",
}

SALIDA = "instagram_export"
DESCARGAR_MEDIA = True        # descargar fotos/videos de tus publicaciones
MAX_POSTS = 50               # tope de publicaciones (None = todas)
MAX_SEGUIDORES = 1000         # tope de seguidores/seguidos (None = todos)
OBTENER_COMENTARIOS = True
PAUSA_MIN, PAUSA_MAX = 3, 7   # segundos entre peticiones (no bajar mucho)
# ------------------------------------------------

JS_FETCH = """
const url = arguments[0], csrf = arguments[1], done = arguments[arguments.length - 1];
fetch(url, {
  credentials: 'include',
  headers: {'x-ig-app-id': '936619743392459', 'x-csrftoken': csrf,
            'x-requested-with': 'XMLHttpRequest'}
}).then(async r => {
  let body = null;
  try { body = await r.json(); } catch (e) {}
  done({status: r.status, body: body});
}).catch(e => done({status: 0, body: null, error: String(e)}));
"""


def pausa():
    time.sleep(random.uniform(PAUSA_MIN, PAUSA_MAX))


def api(driver, ruta, params=None, reintentos=4):
    """GET a la API interna de Instagram desde el navegador, con backoff en 429."""
    url = "https://www.instagram.com" + ruta
    if params:
        url += ("&" if "?" in url else "?") + "&".join(f"{k}={v}" for k, v in params.items())

    for intento in range(reintentos):
        res = driver.execute_async_script(JS_FETCH, url, COOKIES["csrftoken"])
        if res["status"] == 200:
            return res["body"]
        if res["status"] == 429:
            espera = 120 * (2 ** intento)
            print(f"  429 recibido, esperando {espera}s...")
            time.sleep(espera)
            continue
        if res["status"] in (401, 403):
            raise RuntimeError("Sesión inválida o expirada. Copia cookies nuevas.")
        print(f"  Aviso: {ruta} devolvió {res['status']}")
        return None
    return None


def paginar(driver, ruta, clave_items, params=None, limite=None, clave_cursor="next_max_id"):
    """Recorre un endpoint paginado por max_id y junta todos los items."""
    items, cursor = [], None
    while True:
        p = dict(params or {})
        if cursor:
            p["max_id"] = cursor
        data = api(driver, ruta, p)
        if not data:
            break
        items.extend(data.get(clave_items, []))
        print(f"  {ruta.split('/')[-2]}: {len(items)} items")
        cursor = data.get(clave_cursor)
        if not cursor or not data.get("more_available", data.get("has_more", True)):
            break
        if limite and len(items) >= limite:
            items = items[:limite]
            break
        pausa()
    return items


def guardar(nombre, datos):
    os.makedirs(SALIDA, exist_ok=True)
    with open(os.path.join(SALIDA, nombre), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    print(f"  -> guardado {nombre}")


def descargar(url, destino):
    if os.path.exists(destino):
        return
    try:
        r = requests.get(url, timeout=30)
        if r.ok:
            with open(destino, "wb") as f:
                f.write(r.content)
    except requests.RequestException as e:
        print(f"  no se pudo descargar {destino}: {e}")


def url_media(post):
    """Devuelve lista de (url, extension) de una publicación (soporta carruseles)."""
    medios = post.get("carousel_media") or [post]
    out = []
    for m in medios:
        if m.get("video_versions"):
            out.append((m["video_versions"][0]["url"], "mp4"))
        elif m.get("image_versions2"):
            out.append((m["image_versions2"]["candidates"][0]["url"], "jpg"))
    return out


def main():
    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(options=opciones)
    driver.set_script_timeout(60)

    try:
        # Iniciar sesión con cookies
        driver.get("https://www.instagram.com/")
        time.sleep(3)
        for nombre, valor in COOKIES.items():
            driver.add_cookie({"name": nombre, "value": valor, "domain": ".instagram.com"})
        driver.get(f"https://www.instagram.com/{USERNAME}/")
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("return document.readyState") == "complete")
        if "accounts/login" in driver.current_url:
            raise RuntimeError("Sesión no válida: cookies expiradas o incorrectas.")

        # 1. Perfil
        print("[1/7] Perfil")
        perfil = api(driver, "/api/v1/users/web_profile_info/", {"username": USERNAME})
        usuario = perfil["data"]["user"]
        uid = usuario["id"]
        guardar("perfil.json", usuario)
        pausa()

        info = api(driver, f"/api/v1/users/{uid}/info/")
        if info:
            guardar("perfil_detalle.json", info.get("user", info))
        pausa()

        # 2. Publicaciones (fotos, carruseles, videos, reels)
        print("[2/7] Publicaciones")
        posts = paginar(driver, f"/api/v1/feed/user/{uid}/", "items",
                        {"count": 12}, limite=MAX_POSTS)
        guardar("publicaciones.json", posts)

        # 3. Comentarios de cada publicación
        if OBTENER_COMENTARIOS:
            print("[3/7] Comentarios")
            comentarios = {}
            for p in posts:
                if p.get("comment_count", 0) > 0:
                    pausa()
                    comentarios[p["code"]] = paginar(
                        driver, f"/api/v1/media/{p['pk']}/comments/", "comments",
                        {"can_support_threading": "true"}, limite=300,
                        clave_cursor="next_min_id")
            guardar("comentarios.json", comentarios)

        # 4. Seguidores y seguidos
        print("[4/7] Seguidores")
        seguidores = paginar(driver, f"/api/v1/friendships/{uid}/followers/", "users",
                             {"count": 50}, limite=MAX_SEGUIDORES)
        guardar("seguidores.json", seguidores)
        pausa()

        print("[5/7] Seguidos")
        seguidos = paginar(driver, f"/api/v1/friendships/{uid}/following/", "users",
                           {"count": 50}, limite=MAX_SEGUIDORES)
        guardar("seguidos.json", seguidos)

        # Quiénes no te siguen de vuelta
        set_seguidores = {u["pk"] for u in seguidores}
        no_te_siguen = [u for u in seguidos if u["pk"] not in set_seguidores]
        guardar("no_te_siguen_de_vuelta.json", no_te_siguen)
        pausa()

        # 6. Guardados
        print("[6/7] Guardados")
        guardados = paginar(driver, "/api/v1/feed/saved/posts/", "items")
        guardar("guardados.json", guardados)
        pausa()

        # 7. Destacadas e historias activas
        print("[7/7] Destacadas e historias")
        destacadas = api(driver, f"/api/v1/highlights/{uid}/highlights_tray/")
        guardar("destacadas.json", destacadas)
        pausa()
        historias = api(driver, f"/api/v1/feed/user/{uid}/story/")
        guardar("historias_activas.json", historias)

        # Descarga de archivos multimedia
        if DESCARGAR_MEDIA:
            print("Descargando multimedia...")
            carpeta = os.path.join(SALIDA, "media")
            os.makedirs(carpeta, exist_ok=True)
            descargar(usuario["profile_pic_url_hd"], os.path.join(carpeta, "foto_perfil.jpg"))
            for p in posts:
                for i, (url, ext) in enumerate(url_media(p)):
                    descargar(url, os.path.join(carpeta, f"{p['code']}_{i}.{ext}"))

        print(f"\nListo. Todo quedó en la carpeta '{SALIDA}/'")

    except Exception as e:
        print(f"\nError: {e}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
