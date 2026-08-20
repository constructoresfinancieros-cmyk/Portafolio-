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
HISTORY_FILE = "data_history.jsonl"

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

        # IMPORTANTE: NO usar wait_until="networkidle" aquí. La página de
        # la BVC tiene tráfico de red continuo en segundo plano (polling
        # de cotizaciones, analítica, etc.), así que "networkidle" nunca
        # se cumple y siempre agota el timeout. En su lugar, esperamos
        # solo a que el HTML base cargue, y luego esperamos explícitamente
        # a que la tabla de precios tenga contenido real.
        page.goto(
            "https://www.bolsadecaracas.com/resumen-mercado/",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        # Esperamos hasta 25s a que desaparezca el texto de carga inicial
        # ("Cargando Información de símbolo"). Si no desaparece a tiempo,
        # seguimos igual e intentamos leer lo que haya en ese momento.
        try:
            page.wait_for_function(
                """() => !document.body.innerText.includes('Cargando Información de símbolo')""",
                timeout=25000,
            )
        except Exception:
            print("[AVISO] La tabla siguió mostrando 'Cargando...' tras 25s, se intenta leer igual")

        # Margen extra para que terminen de pintar los últimos números
        page.wait_for_timeout(3000)

        # Intentamos expandir el listado completo de símbolos si el link existe
        for texto_link in ["Ver todos los símbolos", "Ver más símbolos"]:
            try:
                page.click(f"text={texto_link}", timeout=3000)
                page.wait_for_timeout(2000)
                break
            except Exception:
                continue

        # --- DEPURACIÓN ---
        # Guardamos una captura de pantalla y el HTML tal cual quedó el
        # navegador en este momento. No podemos ver bolsadecaracas.com
        # desde fuera de GitHub Actions, así que esto es la única forma
        # de diagnosticar qué está pasando realmente (¿bloqueo anti-bot?,
        # ¿necesita más tiempo?, ¿la tabla está en otro lugar?).
        try:
            page.screenshot(path="debug_screenshot.png", full_page=True)
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("[DEBUG] Captura y HTML de depuración guardados")
        except Exception as e:
            print(f"[DEBUG] No se pudo guardar la depuración: {e}")

        filas = page.query_selector_all("table tr")
        for fila in filas:
            celdas = [c.inner_text().strip() for c in fila.query_selector_all("td")]
            if len(celdas) < 3:
                continue

            # En vez de asumir que el símbolo está en una columna fija
            # (la tabla real tiene NOMBRE primero y SÍMBOLO después, al
            # revés de lo que se había asumido), buscamos en TODAS las
            # celdas cuál coincide exactamente con un ticker que ya
            # conocemos de EMPRESAS.
            ticker = None
            ticker_idx = None
            for idx, celda in enumerate(celdas):
                candidato = celda.upper().strip()
                if candidato in EMPRESAS:
                    ticker = candidato
                    ticker_idx = idx
                    break
            if ticker is None:
                continue

            precio = None
            cambio = None
            for celda in celdas[ticker_idx + 1:]:
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

    # --- Historial ---
    # Guardamos un renglón por corrida (JSON Lines: un objeto JSON por
    # línea, fácil de leer sin cargar todo el archivo en memoria). Con
    # esto se puede armar más adelante un gráfico de la evolución del
    # precio de cada acción en el tiempo, y un mapa de calor histórico.
    # Solo se guardan tickers con precio EN VIVO de esta corrida (no se
    # repite el último precio conocido cuando no hubo dato nuevo), para
    # no ensuciar el historial con valores repetidos artificialmente.
    try:
        renglon = {
            "timestamp": data["updated_at"],
            "bcv_rate": data.get("bcv_rate"),
            "stocks": [
                {"ticker": s["ticker"], "price": s["price"], "change_pct": s["change_pct"]}
                for s in nuevos_stocks if s.get("live")
            ],
        }
        if renglon["stocks"]:  # no guardamos corridas sin ningún dato nuevo
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(renglon, ensure_ascii=False) + "\n")
            print(f"[OK] Historial actualizado con {len(renglon['stocks'])} tickers")
    except Exception as e:
        print(f"[ERROR] No se pudo escribir el historial: {e}")

    print("data.json actualizado")


if __name__ == "__main__":
    main()
