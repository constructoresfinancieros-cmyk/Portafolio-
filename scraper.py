import json
import re
import urllib.request

def obtener_datos():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. Obtenemos el Dólar BCV actualizado desde la API pública de PyDolar
    tasa_bcv = "68.45"
    try:
        url_bcv = "https://pydolarvenezuela-api.vercel.app/api/v1/dollar?page=bcv"
        req = urllib.request.Request(url_bcv, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Extraer el valor según la estructura de la API
            if 'monedas' in data and 'dollar' in data['monedas']:
                tasa_bcv = str(round(float(data['monedas']['dollar']['price']), 2))
            elif 'price' in data:
                tasa_bcv = str(round(float(data['price']), 2))
            print(f"Éxito obteniendo BCV: {tasa_bcv}")
    except Exception as e:
        print(f"Aviso en BCV: {e}")

    # 2. Modificamos el index.html
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # Reemplazamos el valor del BCV
        content = re.sub(r'id="bcvRate"\s+value="[^"]*"', f'id="bcvRate" value="{tasa_bcv}"', content)

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("index.html actualizado correctamente.")
    except Exception as e:
        print(f"Error escribiendo archivo: {e}")

if __name__ == "__main__":
    obtener_datos() 
