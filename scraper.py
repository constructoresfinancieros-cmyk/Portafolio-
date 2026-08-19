import json
import re
import urllib.request

def obtener_datos():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 1. Obtener Dólar BCV
    tasa_bcv = "68.45"
    try:
        url_bcv = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = urllib.request.Request(url_bcv, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if 'monedas' in data and 'dollar' in data['monedas']:
                tasa_bcv = str(round(float(data['monedas']['dollar']['price']), 2))
            elif 'price' in data:
                tasa_bcv = str(round(float(data['price']), 2))
        print(f"Tasa BCV obtenida: {tasa_bcv}")
    except Exception as e:
        print(f"Error BCV: {e}")

    # 2. Obtener precios BVC desde la web oficial de la BVC
    cotizaciones = []
    try:
        url_bvc = "https://www.bolsadecaracas.com/resumen-mercado/"
        req_bvc = urllib.request.Request(url_bvc, headers=headers)
        html = urllib.request.urlopen(req_bvc, timeout=15).read().decode('utf-8')

        # Buscar filas de acciones en el HTML
        pattern = r'<td>\s*([A-Z0-9\.]+)\s*</td>\s*<td[^>]*>\s*([\d\.,]+)\s*</td>'
        matches = re.findall(pattern, html)

        for ticker, price_str in matches:
            try:
                # Convertir formato de precio venezolano (ej: "1.649,01" -> 1649.01)
                clean_price = float(price_str.replace('.', '').replace(',', '.'))
                cotizaciones.append({
                    "ticker": ticker,
                    "name": ticker,
                    "price": clean_price,
                    "change": 0.0,
                    "pct": 0.0
                })
            except ValueError:
                continue

        print(f"Acciones BVC encontradas: {len(cotizaciones)}")
    except Exception as e:
        print(f"Error extrayendo BVC: {e}")

    # 3. Actualizar index.html
    actualizar_index(tasa_bcv, cotizaciones)

def actualizar_index(tasa_bcv, cotizaciones):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # Actualizar BCV en HTML
        content = re.sub(r'id="bcvRate"\s+value="[^"]*"', f'id="bcvRate" value="{tasa_bcv}"', content)

        # Actualizar arreglo bvcStocks si se obtuvieron datos
        if cotizaciones:
            json_stocks = json.dumps(cotizaciones, indent=4)
            # Reemplazar la variable const bvcStocks = [...];
            content = re.sub(
                r'const bvcStocks = \[[\s\S]*?\];',
                f'const bvcStocks = {json_stocks};',
                content
            )
            print("Arreglo bvcStocks actualizado con las nuevas cotizaciones.")

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)

        print("index.html guardado exitosamente.")
    except Exception as e:
        print(f"Error modificando index.html: {e}")

if __name__ == "__main__":
    obtener_datos() 
