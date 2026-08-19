import json
import re
import urllib.request

def obtener_datos_bvc():
    # Headers para simular un navegador real y saltar el bloqueo de Cloudflare
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8'
    }

    # 1. Obtener Dólar BCV
    tasa_bcv = None
    try:
        url_bcv = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = urllib.request.Request(url_bcv, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if 'monedas' in data and 'dollar' in data['monedas']:
                tasa_bcv = str(round(float(data['monedas']['dollar']['price']), 2))
            elif 'price' in data:
                tasa_bcv = str(round(float(data['price']), 2))
        print(f"BCV Obtenido: {tasa_bcv}")
    except Exception as e:
        print(f"Error BCV: {e}")

    # 2. Obtener Acciones de la BVC (Extracción HTML directa de la tabla oficial)
    cotizaciones = []
    try:
        url_bvc = "https://www.bolsadecaracas.com/resumen-mercado/"
        req_bvc = urllib.request.Request(url_bvc, headers=headers)
        html = urllib.request.urlopen(req_bvc, timeout=15).read().decode('utf-8')

        # Expresión regular para buscar filas de tickers y precios de la BVC
        # Captura: [Ticker, Precio]
        pattern = r'<td>\s*([A-Z0-9\.]+)\s*</td>\s*<td[^>]*>\s*([\d\.,]+)\s*</td>'
        matches = re.findall(pattern, html)

        if matches:
            for symbol, price_str in matches:
                try:
                    # Formatear el precio de Venezuela (1.649,01 -> 1649.01)
                    clean_price = price_str.replace('.', '').replace(',', '.')
                    price_val = float(clean_price)
                    
                    cotizaciones.append({
                        "ticker": symbol,
                        "name": symbol,
                        "price": price_val,
                        "change": 0.0,
                        "pct": 0.0
                    })
                except ValueError:
                    continue
            print(f"Acciones BVC encontradas: {len(cotizaciones)}")
        else:
            print("No se encontraron patrones de la BVC en el HTML.")

    except Exception as e:
        print(f"Error BVC Scraping: {e}")

    # 3. Guardar cambios en index.html
    if tasa_bcv or cotizaciones:
        actualizar_index(tasa_bcv, cotizaciones)

def actualizar_index(tasa_bcv, cotizaciones):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # Actualizar BCV
        if tasa_bcv:
            content = re.sub(r'id="bcvRate"\s+value="[^"]*"', f'id="bcvRate" value="{tasa_bcv}"', content)

        # Actualizar Arreglo de Acciones BVC
        if cotizaciones:
            json_stocks = json.dumps(cotizaciones, indent=6)
            content = re.sub(
                r'const bvcStocks = \[[\s\S]*?\];',
                f'const bvcStocks = {json_stocks};',
                content
            )

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)

        print("¡index.html actualizado exitosamente!")
    except Exception as e:
        print(f"Error modificando index.html: {e}")

if __name__ == "__main__":
    obtener_datos_bvc()
