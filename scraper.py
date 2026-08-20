"""
Actualiza data.json con:
  1) Tasa oficial del dólar BCV        -> API pública (ve.dolarapi.com)
  2) Precios de las 29 acciones BVC    -> scraping con navegador headless

¿Por qué navegador headless y no requests/regex simple?
La tabla de precios en bolsadecaracas.com/resumen-mercado se rellena con
JavaScript DESPUÉS de cargar la página (el HTML crudo dice literalmente
"Cargando Información de símbolo"). Un fetch normal (urllib/requests) nunca
ve esos números. Playwright abre un Chromium real, deja que el JS corra,
y AHÍ SÍ lee la tabla ya poblada.

Este script se ejecuta automáticamente vía GitHub Actions
(.github/workflows/update-data.yml). Si algo falla a mitad de camino,
NUNCA se sobreescribe data.json con datos vacíos: se conserva el último
valor bueno conocido y se reporta el error en el log de la Action.
"""

import json
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

DATA_FILE = "data.json"

# ----------------------------------------------------------------------
# Nombres reales verificados de las 29 acciones activas de la BVC.
# El scraper solo necesita encontrar el PRECIO de cada ticker; el nombre
# de la empresa lo tomamos de aquí para no depender de que la tabla web
# también incluya la razón social completa.
# ----------------------------------------------------------------------
EMPRESAS = {
    "MVZ.A": "Mercantil Servicios Financieros, C.A. (Clase A)",
    "MVZ.B": "Mercantil Servicios Financieros, C.A. (Clase B)",
    "BVL":   "Banco de Venezuela, S.A. Banco Universal",
    "BPV":   "Banco Provincial, S.A. Banco Universal",
    "BNC":   "Banco Nacional de Crédito, C.A., Banco Universal",
    "RST":   "C.A. Ron Santa Teresa",
    "RST.B": "C.A. Ron Santa Teresa (Clase B)",
    "FNV":   "C.A. Fábrica Nacional de Vidrio",
    "CGQ":   "Corporación Grupo Químico, C.A.",
    "ABC.A": "Banco del Caribe, C.A., Banco Universal",
    "FNC":   "C.A. Fábrica Nacional de Cementos S.A.C.A.",
    "ENV":   "Envases Venezolanos, S.A.",
    "EFE":   "Productos EFE, S.A.",
    "PGR":   "Proagro, C.A.",
    "TDV.D": "C.A. Nacional Teléfonos de Venezuela (CANTV, Clase D)",
    "GZL":   "Grupo Zuliano, C.A.",
    "DOM":   "Domínguez & Cía., S.A.",
    "MPA":   "Manufacturas de Papel, C.A.",
    "CCR":   "Cerámica Carabobo, S.A.C.A.",
    "PTN":   "Protinal, C.A.",
    "PCP.B": "Fondo Petrolia, C.A. (Clase B)",
    "SVS":   "Siderúrgica Venezolana \"Sivensa\", S.A.",
    "2TPG":  "Telares de Palo Grande, C.A.",
    "BVCC":  "Bolsa de Valores de Caracas, C.A.",
    "ICP.B": "Inversiones Crecepymes, C.A. (Clase B)",
    "CRM.A": "Corimon, C.A.",
    "PIV.B": "Pivca Promotora de Inversiones y Valores, C.A. (Clase B)",
    "2CIE":  "Corp. Industrial de Energía, C.A. SACA",
    "IMP.B": "Impulsa Agronegocios, C.A. (Clase B)",
}

TICKER_RE = re.compile(r'^[A-Z0-9]{2,6}(\.[A-Z])?$')
PRICE_RE = re.compile(r'^-?\d{1,3}(\.\d{3})*(,\d{1,4})?$|^-?\d+(,\d{1,4})?$')


# ----------------------------------------------------------------------
# 1. Dólar BCV
# ----------------------------------------------------------------------
def obtener_tasa_bcv():
    url = "https://ve.dolarapi.com/v1/dolares/oficial"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return round(float(data["promedio"]), 2)


# ----------------------------------------------------------------------
# 2. Acciones BVC — requiere navegador porque la tabla se llena con JS
# ----------------------------------------------------------------------
def _parsear_precio(texto):
    limpio = texto.strip().replace(".", "").replace(",", ".")
    return float(limpio)


def obtener_acciones_bvc():
    from playwright.sync_api import sync_playwright

    encontrados = {}  # ticker -> {precio, cambio}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(
            "https://www.bolsadecaracas.com/resumen-mercado/",
            wait_until="networkidle",
            timeout=30000,
        )
        # Le damos tiempo extra a los widgets que cargan datos por AJAX
        page.wait_for_timeout(4000)

        # Intentamos expandir el listado completo de símbolos si el link existe
        for texto_link in ["Ver todos los símbolos", "Ver más símbolos"]:
            try:
                page.click(f"text={texto_link}", timeout=3000)
                page.wait_for_timeout(2000)
                break
            except Exception:
                continue

        filas = page.query_selector_all("table tr")
        for fila in filas:
            celdas = [c.inner_text().strip() for c in fila.query_selector_all("td")]
            if len(celdas) < 2:
                continue

            ticker = celdas[0].upper()
            if not TICKER_RE.match(ticker) or ticker not in EMPRESAS:
                continue  # solo nos interesan tickers que sabemos que existen

            precio = None
            cambio = None
            for celda in celdas[1:]:
                if precio is None and PRICE_RE.match(celda):
                    try:
                        precio = _parsear_precio(celda)
                        continue
                    except ValueError:
                        pass
                if "%" in celda:
                    try:
                        cambio = float(celda.replace("%", "").replace(",", ".").strip())
                    except ValueError:
                        pass

            if precio is not None:
                encontrados[ticker] = {"precio": precio, "cambio": cambio}

        browser.close()

    return encontrados


# ----------------------------------------------------------------------
# 3. Orquestación
# ----------------------------------------------------------------------
def cargar_data_actual():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"bcv_rate": None, "stocks": []}


def main():
    data = cargar_data_actual()

    # --- Dólar BCV ---
    try:
        data["bcv_rate"] = obtener_tasa_bcv()
        print(f"[OK] Tasa BCV: {data['bcv_rate']}")
    except Exception as e:
        print(f"[ERROR] No se pudo obtener la tasa BCV, se conserva la anterior: {e}")

    # --- Acciones BVC ---
    stocks_previos = {s["ticker"]: s for s in data.get("stocks", [])}

    try:
        encontrados = obtener_acciones_bvc()
        print(f"[OK] {len(encontrados)} de {len(EMPRESAS)} tickers encontrados en vivo")
    except Exception as e:
        print(f"[ERROR] Falló el scraping de la BVC, se conservan los precios anteriores: {e}")
        encontrados = {}

    nuevos_stocks = []
    for ticker, nombre in EMPRESAS.items():
        if ticker in encontrados:
            nuevos_stocks.append({
                "ticker": ticker,
                "name": nombre,
                "price": encontrados[ticker]["precio"],
                "change_pct": encontrados[ticker]["cambio"],
                "live": True,
            })
        elif ticker in stocks_previos:
            # No se encontró hoy: mantenemos el último precio conocido
            anterior = stocks_previos[ticker]
            anterior["live"] = False
            nuevos_stocks.append(anterior)
        else:
            # Nunca se ha obtenido este ticker todavía
            nuevos_stocks.append({
                "ticker": ticker, "name": nombre,
                "price": None, "change_pct": None, "live": False,
            })

    data["stocks"] = nuevos_stocks
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("data.json actualizado")


if __name__ == "__main__":
    main()  
