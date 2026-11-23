"""Sala de situacion: vigila fuentes publicas y envia avisos a ntfy."""
import hashlib, html, json, os, re, sys, time
from urllib.parse import quote_plus
import feedparser, requests, yaml
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (SalaSituacion)"
ESTADO = "estado.json"
TAGS = {"emergencias": "rotating_light", "seguridad": "shield", "transporte": "vertical_traffic_light",
        "meteo": "cloud_with_lightning_and_rain", "sismos": "volcano", "catastrofes": "cyclone",
        "noticias": "newspaper", "telegram": "satellite", "drones": "helicopter"}

# Lugares para situar las alertas en el mapa (nombre normalizado: lat, lon)
LUGARES = {
    "madrid": (40.42, -3.70), "barcelona": (41.39, 2.17), "valencia": (39.47, -0.38), "sevilla": (37.39, -5.99),
    "zaragoza": (41.65, -0.89), "malaga": (36.72, -4.42), "murcia": (37.99, -1.13), "palma": (39.57, 2.65),
    "bilbao": (43.26, -2.93), "alicante": (38.35, -0.48), "cordoba": (37.88, -4.78), "valladolid": (41.65, -4.72),
    "vigo": (42.24, -8.72), "gijon": (43.54, -5.66), "oviedo": (43.36, -5.85), "granada": (37.18, -3.60),
    "a coruna": (43.36, -8.41), "vitoria": (42.85, -2.67), "pamplona": (42.81, -1.64), "santander": (43.46, -3.81),
    "san sebastian": (43.32, -1.98), "toledo": (39.86, -4.03), "badajoz": (38.88, -6.97), "salamanca": (40.97, -5.66),
    "cadiz": (36.53, -6.29), "huelva": (37.26, -6.95), "almeria": (36.84, -2.46), "jaen": (37.78, -3.79),
    "castellon": (39.99, -0.05), "tarragona": (41.12, 1.25), "girona": (41.98, 2.82), "lleida": (41.62, 0.62),
    "burgos": (42.34, -3.70), "logrono": (42.47, -2.45), "albacete": (38.99, -1.86),
    "las palmas": (28.12, -15.43), "tenerife": (28.29, -16.63), "canarias": (28.29, -15.6), "ibiza": (38.91, 1.43),
    "mallorca": (39.6, 2.9), "ceuta": (35.89, -5.32), "melilla": (35.29, -2.94), "alcobendas": (40.54, -3.64),
    "getafe": (40.31, -3.73), "mostoles": (40.32, -3.86), "alcala de henares": (40.48, -3.36), "fuenlabrada": (40.28, -3.80),
    "leganes": (40.33, -3.76), "barajas": (40.49, -3.57), "cataluna": (41.8, 1.5), "andalucia": (37.5, -4.7),
    "galicia": (42.8, -8.0), "pais vasco": (43.0, -2.6), "asturias": (43.3, -5.9), "aragon": (41.5, -0.7),
    "lisboa": (38.72, -9.14), "oporto": (41.15, -8.61), "portugal": (39.6, -8.0), "paris": (48.86, 2.35),
    "marsella": (43.30, 5.37), "lyon": (45.76, 4.84), "francia": (46.6, 2.4), "berlin": (52.52, 13.40),
    "munich": (48.14, 11.58), "hamburgo": (53.55, 9.99), "francfort": (50.11, 8.68),
    "alemania": (51.2, 10.4), "roma": (41.90, 12.50), "milan": (45.46, 9.19), "napoles": (40.85, 14.27),
    "italia": (42.8, 12.6), "bruselas": (50.85, 4.35), "belgica": (50.6, 4.6), "amsterdam": (52.37, 4.90),
    "paises bajos": (52.2, 5.5), "copenhague": (55.68, 12.57), "dinamarca": (56.0, 9.5), "estocolmo": (59.33, 18.07),
    "suecia": (62.0, 15.0), "oslo": (59.91, 10.75), "noruega": (61.0, 9.0), "helsinki": (60.17, 24.94),
    "finlandia": (63.0, 26.0), "varsovia": (52.23, 21.01), "polonia": (52.0, 19.4), "viena": (48.21, 16.37),
    "austria": (47.6, 14.1), "praga": (50.08, 14.44), "budapest": (47.50, 19.04), "atenas": (37.98, 23.73),
    "grecia": (39.0, 22.0), "kiev": (50.45, 30.52), "ucrania": (49.0, 31.0), "moscu": (55.76, 37.62),
    "rusia": (55.8, 37.6), "lituania": (55.2, 23.9), "letonia": (56.9, 24.6), "estonia": (58.6, 25.0),
    "rumania": (45.9, 25.0), "bulgaria": (42.7, 25.5), "serbia": (44.0, 20.9), "turquia": (39.0, 35.2),
    "estambul": (41.01, 28.98), "suiza": (46.8, 8.2), "irlanda": (53.3, -7.7), "dublin": (53.35, -6.26),
    "londres": (51.51, -0.13), "london": (51.51, -0.13), "manchester": (53.48, -2.24), "birmingham": (52.49, -1.89),
    "liverpool": (53.41, -2.98), "glasgow": (55.86, -4.25), "edimburgo": (55.95, -3.19), "edinburgh": (55.95, -3.19),
    "belfast": (54.60, -5.93), "gatwick": (51.15, -0.18), "heathrow": (51.47, -0.45), "reino unido": (52.5, -1.5),
    "england": (52.5, -1.5), "inglaterra": (52.5, -1.5), "escocia": (56.5, -4.2), "scotland": (56.5, -4.2), "uk": (52.5, -1.5),
    "washington": (38.91, -77.04), "nueva york": (40.71, -74.01), "new york": (40.71, -74.01), "los angeles": (34.05, -118.24),
    "chicago": (41.88, -87.63), "miami": (25.76, -80.19), "houston": (29.76, -95.37), "texas": (31.0, -99.0),
    "california": (37.0, -120.0), "florida": (28.0, -82.0), "san francisco": (37.77, -122.42), "boston": (42.36, -71.06),
    "atlanta": (33.75, -84.39), "las vegas": (36.17, -115.14), "nueva orleans": (29.95, -90.07), "estados unidos": (39.8, -98.6),
    "eeuu": (39.8, -98.6), "ciudad de mexico": (19.43, -99.13), "cdmx": (19.43, -99.13), "guadalajara": (20.66, -103.35),
    "monterrey": (25.69, -100.32), "tijuana": (32.51, -117.04), "cancun": (21.16, -86.85), "acapulco": (16.85, -99.82),
    "sinaloa": (25.0, -107.5), "culiacan": (24.81, -107.39), "jalisco": (20.6, -103.6), "michoacan": (19.2, -101.9),
    "oaxaca": (17.07, -96.73), "veracruz": (19.17, -96.13), "chiapas": (16.5, -92.5),
    "sonora": (29.3, -110.3), "chihuahua": (28.63, -106.07), "ciudad juarez": (31.69, -106.42), "puebla": (19.04, -98.21),
    "tamaulipas": (24.3, -98.8), "mexico": (23.6, -102.5), "israel": (31.5, 34.9), "gaza": (31.42, 34.37),
    "libano": (33.9, 35.9), "iran": (32.4, 53.7), "teheran": (35.69, 51.39), "irak": (33.2, 43.7), "siria": (35.0, 38.5),
    "yemen": (15.6, 48.0), "arabia saudi": (24.0, 45.0), "marruecos": (31.8, -7.1), "argelia": (28.0, 2.6),
    "egipto": (26.8, 30.8), "china": (35.9, 104.2), "taiwan": (23.7, 121.0), "japon": (36.2, 138.3),
    "corea del norte": (40.3, 127.5), "corea del sur": (36.5, 127.8), "india": (21.0, 78.0), "pakistan": (30.4, 69.3),
    "afganistan": (33.9, 67.7), "colombia": (4.6, -74.1), "bogota": (4.71, -74.07), "argentina": (-38.4, -63.6),
    "chile": (-35.7, -71.5), "peru": (-9.2, -75.0), "ecuador": (-1.8, -78.2), "brasil": (-14.2, -51.9),
    "cuba": (21.5, -77.8), "haiti": (18.97, -72.29),
}
_LUGARES_ORDEN = sorted(LUGARES, key=len, reverse=True)


def situar(titulo):
    """Busca un lugar conocido en el titular para situarlo en el mapa."""
    t = " " + re.sub(r"[^a-z0-9ñ ]", " ", norm(titulo)) + " "
    for nombre in _LUGARES_ORDEN:
        if f" {nombre} " in t:
            return LUGARES[nombre]
    return None


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
        geo = None
        try:
            if e.get("geo_lat") and e.get("geo_long"):
                geo = (float(e["geo_lat"]), float(e["geo_long"]))
            elif e.get("georss_point"):
                geo = tuple(map(float, e["georss_point"].split()[:2]))
        except (TypeError, ValueError):
            geo = None
        out.append({"id": e.get("id") or e.get("link") or tit, "titulo": tit,
                    "resumen": limpio(e.get("summary")), "enlace": e.get("link", ""), "geo": geo,
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
            "priority": 2 if silenciosa else (4 if tipo in ("emergencias", "sismos", "catastrofes", "drones") else 3)}
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
        geo = i["geo"] if i["geo"] and i["geo"][0] is not None else situar(i["titulo"])
        if geo:
            prio = 2 if f.get("silenciosa") else (4 if f.get("tipo") in ("emergencias", "sismos", "catastrofes", "drones") else 3)
            try:
                requests.post("https://ntfy.sh/", timeout=20, json={
                    "topic": topic + "-mapa", "priority": 1,
                    "message": json.dumps({"lat": round(float(geo[0]), 3), "lon": round(float(geo[1]), 3),
                                           "t": i["titulo"], "u": i["enlace"], "f": f["nombre"],
                                           "c": f.get("tipo", ""), "p": prio}, ensure_ascii=False)})
            except requests.RequestException:
                pass
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
    _fin = time.time() + float(os.environ.get("DURACION_MIN", "0")) * 60
    while time.time() + int(os.environ.get("INTERVALO_S", "120")) < _fin:
        time.sleep(int(os.environ.get("INTERVALO_S", "120")))
        main()
