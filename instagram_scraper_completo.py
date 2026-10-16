"""Export visible Instagram profile data with a local browser session.

The script stops on HTTP 429, saves completed pages as checkpoints, and can
resume them when run again. It does not retry or attempt to bypass rate limits.
"""
import json
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from urllib.parse import urlencode

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# ---------------- CONFIGURATION ----------------
USERNAME = "jhonatan.coronel"

# Cookie header is loaded from instagram_cookies.py, which is ignored by Git.
try:
    from instagram_cookies import INSTAGRAM_COOKIES
except ImportError:
    INSTAGRAM_COOKIES = ""


def read_cookies():
    parsed = SimpleCookie()
    if INSTAGRAM_COOKIES:
        parsed.load(INSTAGRAM_COOKIES)
    return {name: morsel.value for name, morsel in parsed.items()}


COOKIES = read_cookies()

OUTPUT_DIR = "instagram_export"
REQUEST_DELAY_SECONDS = 5
PAGE_SIZE = 12
MAX_POSTS = None       # None = collect every page Instagram makes available
MAX_FOLLOWERS = None   # None = collect every page Instagram makes available
DOWNLOAD_MEDIA = True
GET_COMMENTS = True
MAX_TRANSIENT_RETRIES = 2  # Only for network errors / HTTP 5xx; never for HTTP 429
# ------------------------------------------------

SITE = "https://www.instagram.com"
APP_ID = "936619743392459"
CHECKPOINT_DIR = os.path.join(OUTPUT_DIR, ".checkpoints")


class RateLimitError(RuntimeError):
    def __init__(self, endpoint, retry_after=None):
        self.endpoint = endpoint
        self.retry_after = retry_after
        super().__init__(f"Instagram respondió HTTP 429 en {endpoint}")


class InstagramRequestError(RuntimeError):
    pass


JS_FETCH = r"""
const url = arguments[0];
const csrf = arguments[1];
const done = arguments[arguments.length - 1];
fetch(url, {
    method: 'GET',
    headers: {
        'x-csrftoken': csrf,
        'x-ig-app-id': '936619743392459',
        'x-requested-with': 'XMLHttpRequest'
    },
    credentials: 'include'
})
.then(async response => ({
    status: response.status,
    body: await response.text(),
    retry_after: response.headers.get('Retry-After')
}))
.then(result => done(result))
.catch(error => done({ status: 0, body: String(error), retry_after: null }));
"""


def safe_username():
    return re.sub(r"[^A-Za-z0-9._-]+", "_", USERNAME)[:80]


def save_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def output_path(filename):
    return os.path.join(OUTPUT_DIR, filename)


def checkpoint_path(name):
    return os.path.join(CHECKPOINT_DIR, f"{safe_username()}_{name}.json")


def load_checkpoint(name, default):
    path = checkpoint_path(name)
    if not os.path.isfile(path):
        return dict(default)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        if state.get("username") != USERNAME:
            return dict(default)
        return state
    except (OSError, ValueError):
        return dict(default)


def save_checkpoint(name, state):
    state["username"] = USERNAME
    save_json(checkpoint_path(name), state)


def validate_cookies():
    required = ("sessionid", "csrftoken", "ds_user_id")
    missing = [
        name for name in required
        if not COOKIES.get(name)
    ]
    if missing:
        raise ValueError(
            "Completa localmente estas cookies en COOKIES: " + ", ".join(missing)
        )
    if not str(COOKIES["ds_user_id"]).isdigit():
        raise ValueError("ds_user_id debe ser el valor numérico de tu propia sesión.")


def create_driver():
    # Selenium normal: no usa un navegador de ocultación o evasión.
    options = Options()
    options.add_argument("--disable-popup-blocking")
    driver = webdriver.Chrome(options=options)
    driver.set_script_timeout(30)
    return driver


def install_cookies(driver):
    driver.get(SITE + "/")
    time.sleep(2)
    for name, value in COOKIES.items():
        driver.add_cookie({
            "name": name,
            "value": value,
            "domain": ".instagram.com",
            "path": "/",
            "secure": True,
        })
    driver.get(f"{SITE}/{USERNAME}/")
    time.sleep(4)


def retry_after_message(value):
    if not value:
        return "Instagram no indicó cuánto esperar en Retry-After."
    try:
        seconds = max(0, int(value))
        return f"Instagram indicó esperar al menos {seconds} segundos."
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            seconds = max(0, int((retry_at - datetime.now(timezone.utc)).total_seconds()))
            return f"Instagram indicó esperar hasta {value} (aprox. {seconds} segundos)."
        except (TypeError, ValueError, OverflowError):
            return f"Retry-After recibido: {value}"


def api(driver, endpoint, params=None):
    url = f"{SITE}{endpoint}"
    if params:
        url += "?" + urlencode(params)

    for attempt in range(MAX_TRANSIENT_RETRIES + 1):
        # A steady pause reduces request volume; it does not bypass rate limits.
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            result = driver.execute_async_script(
                JS_FETCH, url, COOKIES["csrftoken"]
            )
        except Exception as exc:
            if attempt >= MAX_TRANSIENT_RETRIES:
                raise InstagramRequestError(
                    f"Falló la petición de red a {endpoint}: {type(exc).__name__}"
                ) from None
            time.sleep(2 ** (attempt + 1))
            continue

        status = int(result.get("status") or 0)
        body = result.get("body") or ""
        if status == 429:
            # No recursive retry: preserve progress and let the caller stop.
            raise RateLimitError(endpoint, result.get("retry_after"))
        if status == 0 and attempt < MAX_TRANSIENT_RETRIES:
            time.sleep(2 ** (attempt + 1))
            continue
        if status in (401, 403):
            raise InstagramRequestError(
                f"Instagram rechazó la sesión (HTTP {status}) en {endpoint}. "
                "Revisa la sesión en el navegador; no se intentó saltar el bloqueo."
            )
        if status >= 500 and attempt < MAX_TRANSIENT_RETRIES:
            time.sleep(2 ** (attempt + 1))
            continue
        if status < 200 or status >= 400:
            raise InstagramRequestError(
                f"Instagram respondió HTTP {status} en {endpoint}."
            )
        try:
            return json.loads(body)
        except (TypeError, ValueError):
            raise InstagramRequestError(
                f"Instagram no devolvió JSON válido para {endpoint}."
            ) from None

    raise InstagramRequestError(f"No se pudo completar la petición a {endpoint}.")


def item_key(item):
    return str(item.get("id") or item.get("pk") or item.get("username") or
               json.dumps(item, sort_keys=True, ensure_ascii=False))


def collect_pages(driver, name, endpoint, params, response_key, filename,
                  has_more_key=None, max_items=None):
    state = load_checkpoint(name, {
        "items": [], "cursor": None, "complete": False, "pages": 0
    })
    items = state.get("items") or []
    cursor = state.get("cursor")
    complete = bool(state.get("complete"))
    seen = {item_key(item) for item in items if isinstance(item, dict)}
    save_json(output_path(filename), items)

    while not complete:
        if max_items is not None and len(items) >= max_items:
            break

        page_params = dict(params)
        if cursor:
            page_params["max_id"] = cursor
        data = api(driver, endpoint, page_params)
        batch = data.get(response_key) or []
        if not isinstance(batch, list):
            raise InstagramRequestError(
                f"La respuesta de {endpoint} no contenía una lista válida."
            )

        remaining = None if max_items is None else max(0, max_items - len(items))
        if remaining is not None:
            batch = batch[:remaining]
        for item in batch:
            if not isinstance(item, dict):
                continue
            key = item_key(item)
            if key not in seen:
                seen.add(key)
                items.append(item)

        next_cursor = data.get("next_max_id")
        has_more = (bool(data.get(has_more_key)) if has_more_key
                    else bool(next_cursor))
        if has_more and not next_cursor:
            state.update({"items": items, "cursor": None, "complete": False})
            save_checkpoint(name, state)
            save_json(output_path(filename), items)
            raise InstagramRequestError(
                f"{endpoint} indicó más páginas, pero no entregó next_max_id."
            )

        complete = not has_more
        if max_items is not None and len(items) >= max_items and has_more:
            complete = False
        cursor = next_cursor if has_more else None
        state.update({
            "items": items,
            "cursor": cursor,
            "complete": complete,
            "pages": int(state.get("pages") or 0) + 1,
        })
        save_checkpoint(name, state)
        save_json(output_path(filename), items)
        print(f"{name}: {len(items)} elementos; páginas guardadas: {state['pages']}")

        if complete or (max_items is not None and len(items) >= max_items):
            break
        if not batch:
            raise InstagramRequestError(
                f"{endpoint} devolvió una página vacía con más páginas pendientes."
            )
        cursor = next_cursor

    return items, complete


def collect_comments(driver, posts):
    state = load_checkpoint("comments", {
        "comments": {}, "completed_media_ids": [], "complete": False
    })
    comments_by_media = state.get("comments") or {}
    completed = set(state.get("completed_media_ids") or [])
    save_json(output_path("6_comentarios.json"), comments_by_media)

    if not GET_COMMENTS:
        state["complete"] = False
        save_checkpoint("comments", state)
        return comments_by_media, False

    for post in posts:
        media_id = str(post.get("id") or post.get("pk") or "")
        if not media_id or media_id in completed:
            continue
        data = api(driver, f"/api/v1/media/{media_id}/comments/")
        comments_by_media[media_id] = data.get("comments") or []
        completed.add(media_id)
        state.update({
            "comments": comments_by_media,
            "completed_media_ids": sorted(completed),
            "complete": False,
        })
        save_checkpoint("comments", state)
        save_json(output_path("6_comentarios.json"), comments_by_media)

    is_complete = all(
        str(post.get("id") or post.get("pk") or "") in completed
        for post in posts if post.get("id") or post.get("pk")
    )
    state["complete"] = is_complete
    save_checkpoint("comments", state)
    return comments_by_media, is_complete


def media_candidates(post):
    code = re.sub(r"[^A-Za-z0-9._-]+", "_", str(post.get("code") or post.get("id") or "post"))
    candidates = []

    def add_item(item, prefix):
        for index, image in enumerate((item.get("image_versions2") or {}).get("candidates") or []):
            if image.get("url"):
                candidates.append((f"{prefix}_image_{index + 1}", image["url"], ".jpg"))
                break
        videos = item.get("video_versions") or []
        if videos and videos[0].get("url"):
            candidates.append((f"{prefix}_video", videos[0]["url"], ".mp4"))

    add_item(post, code)
    for index, child in enumerate(post.get("carousel_media") or [], 1):
        add_item(child, f"{code}_slide_{index:02d}")
    return candidates


def download_media(posts):
    media_dir = os.path.join(OUTPUT_DIR, "media", safe_username())
    os.makedirs(media_dir, exist_ok=True)
    downloaded = 0
    failures = []
    seen_urls = set()
    stopped_by_limit = False
    for post in posts:
        for name, url, extension in media_candidates(post):
            if url in seen_urls:
                continue
            seen_urls.add(url)
            path = os.path.join(media_dir, name + extension)
            if os.path.isfile(path):
                continue
            try:
                with requests.get(url, stream=True, timeout=(10, 60)) as response:
                    if response.status_code == 429:
                        failures.append({"file": name, "error": "CDN respondió HTTP 429; se detuvo la descarga."})
                        stopped_by_limit = True
                        break
                    response.raise_for_status()
                    with open(path, "wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                handle.write(chunk)
                downloaded += 1
            except requests.RequestException as exc:
                failures.append({"file": name, "error": f"{type(exc).__name__}: {str(exc)[:180]}"})
            if stopped_by_limit:
                break
            time.sleep(1)
        if stopped_by_limit:
            break
    report = {"downloaded": downloaded, "failed_count": len(failures), "failed": failures}
    save_json(output_path("media_report.json"), report)
    return report


def write_summary():
    definitions = {
        "posts": ("posts", "posts_<usuario>.json"),
        "followers": ("followers", "followers_<usuario>.json"),
        "following": ("following", "following_<usuario>.json"),
    }
    datasets = {}
    for label, (checkpoint_name, _) in definitions.items():
        state = load_checkpoint(checkpoint_name, {"items": [], "complete": False, "pages": 0})
        datasets[label] = {
            "count": len(state.get("items") or []),
            "complete": bool(state.get("complete")),
            "pages": int(state.get("pages") or 0),
        }
    comments = load_checkpoint("comments", {"comments": {}, "complete": False})
    datasets["comments"] = {
        "count": sum(len(rows) for rows in (comments.get("comments") or {}).values()),
        "complete": bool(comments.get("complete")),
        "posts_with_comments_checked": len(comments.get("completed_media_ids") or []),
    }
    summary = {"target": USERNAME, "datasets": datasets}
    save_json(output_path("7_resumen.json"), summary)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(CHECKPOINT_DIR, exist_ok=True)
    validate_cookies()
    driver = None
    try:
        driver = create_driver()
        install_cookies(driver)

        profile_data = api(
            driver, "/api/v1/users/web_profile_info/", {"username": USERNAME}
        )
        profile = ((profile_data.get("data") or {}).get("user") or {})
        if not profile:
            raise InstagramRequestError("Instagram no devolvió el perfil solicitado.")
        save_json(output_path("1_perfil.json"), profile_data)
        user_id = str(profile.get("id") or profile.get("pk") or COOKIES["ds_user_id"])

        posts, posts_complete = collect_pages(
            driver, "posts", f"/api/v1/feed/user/{USERNAME}/username/",
            {"count": PAGE_SIZE}, "items", "2_publicaciones.json",
            has_more_key="more_available", max_items=MAX_POSTS,
        )
        if DOWNLOAD_MEDIA:
            print("Descargando medios de publicaciones ya guardadas...")
            print(download_media(posts))

        followers, followers_complete = collect_pages(
            driver, "followers", f"/api/v1/friendships/{user_id}/followers/",
            {"count": PAGE_SIZE, "search_surface": "follow_list_page"},
            "users", "4_seguidores.json", max_items=MAX_FOLLOWERS,
        )
        following, following_complete = collect_pages(
            driver, "following", f"/api/v1/friendships/{user_id}/following/",
            {"count": PAGE_SIZE, "search_surface": "follow_list_page"},
            "users", "5_seguidos.json", max_items=MAX_FOLLOWERS,
        )
        comments, comments_complete = collect_comments(driver, posts)
        print(
            "Finalizado. "
            f"Publicaciones: {len(posts)} ({'completo' if posts_complete else 'parcial'}); "
            f"seguidores: {len(followers)} ({'completo' if followers_complete else 'parcial'}); "
            f"seguidos: {len(following)} ({'completo' if following_complete else 'parcial'}); "
            f"comentarios: {'completo' if comments_complete else 'parcial'}."
        )
    except RateLimitError as exc:
        print("Instagram aplicó un límite de solicitudes (HTTP 429).")
        print(retry_after_message(exc.retry_after))
        print("Se guardó el progreso. No se repetirá la solicitud automáticamente.")
        print("Espera antes de volver a ejecutar el script; continuará desde el último checkpoint.")
    except Exception as exc:
        print(f"Proceso detenido: {type(exc).__name__}: {str(exc)}")
        print("Las páginas completadas permanecen guardadas en output/.checkpoints/.")
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        write_summary()
        print(f"Resumen actualizado: {output_path('7_resumen.json')}")


if __name__ == "__main__":
    main()
