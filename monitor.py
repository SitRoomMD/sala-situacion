"""Sala de situacion: vigila fuentes publicas y envia avisos a ntfy."""
import hashlib, html, json, os, re, sys, time
from urllib.parse import quote_plus
import feedparser, requests, yaml
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (SalaSituacion)"
ESTADO = "estado.json"
TAGS = {"emergencias": "rotating_light", "seguridad": "shield", "transporte": "vertical_traffic_light",
        "meteo": "cloud_with_lightning_and_rain", "sismos": "volcano", "catastrofes": "cyclone",
        "noticias": "newspaper", "telegram": "satellite"}


def norm(t):
    t = (t or "").lower()
    for a, b in zip("áéíóúüàèò", "aeiouuaeo"):
        t = t.replace(a, b)
    return t


def limpio(t, n=300):
    t = re.sub(r"\s+", " ", BeautifulSoup(t or "", "html.parser").get_text(" ", strip=True))
    return t[: n - 1] + "…" if len(t) > n else t


def get(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    r.raise_for_status()
    return r


def leer_rss(url):
    out = []
    for e in feedparser.parse(get(url).content).entries:
        tit = limpio(e.get("title"), 200)
        m = re.search(r"\b(?:M|Mag(?:nitud|nitude)?\.?)\s*[:=]?\s*(\d+(?:[.,]\d+)?)", tit)
        out.append({"id": e.get("id") or e.get("link") or tit, "titulo": tit,
                    "resumen": limpio(e.get("summary")), "enlace": e.get("link", ""), "geo": None,
                    "mag": float(m.group(1).replace(",", ".")) if m else None})
    return out


def leer(f):
    tipo = f["lector"]
    if tipo == "rss":
        return leer_rss(f["url"])
    if tipo == "google_news":
        hl, gl = f.get("hl", "es"), f.get("gl", "ES")
        url = (f"https://news.google.com/rss/search?q={quote_plus(f['query'] + ' when:' + f.get('window', '1h'))}"
               f"&hl={hl}&gl={gl}&ceid={gl}:{hl}")
        items = leer_rss(url)
        for i in items:
            i["resumen"] = ""
        return items
    if tipo in ("usgs", "emsc"):
        out = []
        for x in get(f["url"]).json().get("features", []):
            p = x.get("properties", {})
            c = (x.get("geometry") or {}).get("coordinates") or [None, None]
            if tipo == "usgs":
                out.append({"id": x.get("id"), "titulo": p.get("title", ""), "resumen": "",
                            "enlace": p.get("url", ""), "geo": (c[1], c[0]), "mag": p.get("mag")})
            else:
                uid = p.get("unid") or x.get("id")
                out.append({"id": uid, "titulo": f"Terremoto M{p.get('mag')}, {(p.get('flynn_region') or '').title()}",
                            "resumen": f"Profundidad {p.get('depth')} km.",
                            "enlace": f"https://www.seismicportal.eu/eventdetails.html?unid={uid}",
                            "geo": (p.get("lat"), p.get("lon")), "mag": p.get("mag")})
        return out
    if tipo == "telegram":
        canal = f["channel"].lstrip("@")
        soup = BeautifulSoup(get(f"https://t.me/s/{canal}").text, "html.parser")
        out = []
        for m in soup.select("div.tgme_widget_message"):
            post, body = m.get("data-post"), m.select_one("div.tgme_widget_message_text")
            if post and body:
                txt = body.get_text(" ", strip=True)
                out.append({"id": post, "titulo": limpio(txt, 200), "resumen": "",
                            "enlace": f"https://t.me/{post}", "geo": None, "mag": None})
        return out
    raise ValueError("lector desconocido: " + tipo)


def pasa(i, f, cfg):
    txt = norm(i["titulo"] + " " + i["resumen"])
    if any(norm(k) in txt for k in cfg.get("excluir_siempre", []) + f.get("excluir", [])):
        return False
    inc = [norm(k) for k in f.get("incluir", [])]
    if inc and not any(k in txt for k in inc):
        return False
    if f.get("magnitud_minima") is not None and (i["mag"] is None or float(i["mag"]) < float(f["magnitud_minima"])):
        return False
    if f.get("zonas"):
        dentro = False
        if i["geo"] and i["geo"][0] is not None:
            for z in f["zonas"]:
                w, s, e, n = cfg["zonas"][z]
                if s <= i["geo"][0] <= n and w <= i["geo"][1] <= e:
                    dentro = True
        grande = f.get("magnitud_fuera_de_zona")
        if not dentro and not (grande and i["mag"] is not None and float(i["mag"]) >= float(grande)):
            return False
    return True


def enviar(topic, titulo, mensaje, enlace=None, tipo="", silenciosa=False):
    body = {"topic": topic, "title": titulo[:250], "message": mensaje or " ",
            "tags": [TAGS.get(tipo, "information_source")],
            "priority": 2 if silenciosa else (4 if tipo in ("emergencias", "sismos", "catastrofes") else 3)}
    if enlace:
        body["click"] = enlace
    for _ in range(3):
        try:
            r = requests.post("https://ntfy.sh/", json=body, timeout=20)
            if r.ok:
                return True
            print("ntfy", r.status_code, r.text[:150])
            time.sleep(5)
        except requests.RequestException as e:
            print("ntfy error", e)
            time.sleep(3)
    return False


def main():
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        sys.exit("Falta el secreto NTFY_TOPIC")
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    try:
        estado = json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        estado = {}
    visto = estado.setdefault("visto", {})
    iniciadas = set(estado.setdefault("fuentes", []))
    ahora = int(time.time())
    if not estado.get("bienvenida"):
        enviar(topic, "Sala de situación conectada", "A partir de ahora recibirás aquí las alertas.")
        estado["bienvenida"] = True

    pendientes = []
    for f in cfg["fuentes"]:
        if not f.get("activa", True):
            continue
        try:
            items = leer(f)
        except Exception as e:
            print(f"{f['nombre']}: no responde ({e})")
            continue
        primera = f["nombre"] not in iniciadas
        for i in items:
            k = hashlib.sha1(f"{f['nombre']}|{i['id']}".encode()).hexdigest()[:16]
            if k in visto:
                continue
            visto[k] = ahora
            if primera or not pasa(i, f, cfg):
                continue
            t = hashlib.sha1(re.sub(r"\s+-\s+[^-]+$", "", norm(i["titulo"]))[:90].encode()).hexdigest()[:16]
            if t in visto:
                continue
            visto[t] = ahora
            pendientes.append((i, f))
        iniciadas.add(f["nombre"])

    tope = cfg.get("max_alertas_por_ciclo", 10)
    for i, f in pendientes[:tope]:
        enviar(topic, i["titulo"], " ".join(x for x in (i["resumen"], f"({f['nombre']})") if x),
               i["enlace"], f.get("tipo", ""), f.get("silenciosa", False))
        time.sleep(1)
    if len(pendientes) > tope:
        enviar(topic, "Más alertas", f"{len(pendientes) - tope} alertas más no enviadas para no saturar.", silenciosa=True)
    print(f"{len(pendientes)} nuevas, {min(len(pendientes), tope)} enviadas")

    limite = ahora - 14 * 86400
    estado["visto"] = {k: v for k, v in visto.items() if v > limite}
    estado["fuentes"] = sorted(iniciadas)
    json.dump(estado, open(ESTADO, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
