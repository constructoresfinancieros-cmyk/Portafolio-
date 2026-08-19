 import json
import re
import urllib.request

def obtener_datos():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. Obtener Dólar BCV desde la API pública de PyDolarVenezuela / VeDolar
    tasa_bcv = "68.45"
    try:
        url_bcv_api = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = urllib.request.Request(url_bcv_api, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if 'monedas' in data and 'dollar' in data['monedas']:
                tasa_bcv = str(round(float(data['monedas']['dollar']['price']), 2))
            elif 'price' in data:
                tasa_bcv = str(round(float(data['price']), 2))
        print(f"Tasa BCV obtenida: {tasa_bcv}")
    except Exception as e:
        print(f"Error consultando API BCV: {e}")

    # 2. Consultar API / Scraper BVC
    cotizaciones = []
    try:
        # Intentar extraer directamente el JSON embebido de la BVC
        url_bvc = "https://www.bolsadecaracas.com/"
        req_bvc = urllib.request.Request(url_bvc, headers=headers)
        html = urllib.request.urlopen(req_bvc, timeout=10).read().decode('utf-8')
        
        # Buscar el bloque JS que contiene las acciones
        matches = re.findall(r'\{"ticker":"([^"]+)","price":([\d\.]+),"change":([\d\.-]+),"pct":([\d\.-]+)\}', html)
        
        if matches:
            for m in matches:
                cotizaciones.append({
                    "ticker": m[0],
                    "name": m[0],
                    "price": float(m[1]),
                    "change": float(m[2]),
                    "pct": float(m[3])
                })
        print(f"Cotizaciones BVC obtenidas: {len(cotizaciones)}")
    except Exception as e:
        print(f"Error obteniendo BVC: {e}")

    # 3. Inyectar datos en index.html si la extracción fue exitosa
    if tasa_bcv != "68.45" or cotizaciones:
        actualizar_index(tasa_bcv, cotizaciones)

def actualizar_index(tasa_bcv, cotizaciones):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # Actualizar Tasa BCV
        if tasa_bcv:
            content = re.sub(r'id="bcvRate"\s+value="[^"]*"', f'id="bcvRate" value="{tasa_bcv}"', content)

        # Actualizar lista de acciones si se obtuvieron nuevas
        if cotizaciones:
            json_stocks = json.dumps(cotizaciones, indent=6)
            content = re.sub(
                r'const bvcStocks = \[[\s\S]*?\];',
                f'const bvcStocks = {json_stocks};',
                content
            )

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("index.html guardado exitosamente con los nuevos datos.")
    except Exception as e:
        print(f"Error modificando index.html: {e}")

if __name__ == "__main__":
    obtener_datos()
