import urllib.request
import re
import json
from bs4 import BeautifulSoup

def obtener_datos_bvc_y_bcv():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    # 1. Obtener Dólar BCV
    tasa_bcv = "68.45" # Valor base por respaldo
    try:
        url_bcv = "https://www.bcv.org.ve/"
        req_bcv = urllib.request.Request(url_bcv, headers=headers)
        html_bcv = urllib.request.urlopen(req_bcv, timeout=10).read().decode('utf-8')
        soup_bcv = BeautifulSoup(html_bcv, 'html.parser')
        dolar_div = soup_bcv.find('div', {'id': 'dolar'})
        if dolar_div:
            val = dolar_div.find('strong').text.strip().replace(',', '.')
            tasa_bcv = str(round(float(val), 2))
            print(f"Tasa BCV obtenida: {tasa_bcv}")
    except Exception as e:
        print(f"Error obteniendo BCV: {e}")

    # 2. Obtener Cotizaciones BVC
    try:
        url_bvc = "https://www.bolsadecaracas.com/"
        req_bvc = urllib.request.Request(url_bvc, headers=headers)
        html_bvc = urllib.request.urlopen(req_bvc, timeout=10).read().decode('utf-8')
        soup_bvc = BeautifulSoup(html_bvc, 'html.parser')
        
        # Buscar en las tablas de cotizaciones de la página oficial de la BVC
        rows = soup_bvc.find_all('tr')
        nuevas_cotizaciones = []
        
        for row in rows:
            cols = [ele.text.strip() for ele in row.find_all('td')]
            if len(cols) >= 5:
                ticker = cols[0]
                try:
                    precio = float(cols[1].replace('.', '').replace(',', '.'))
                    variacion_bs = float(cols[2].replace('.', '').replace(',', '.'))
                    variacion_pct = float(cols[3].replace('.', '').replace(',', '.').replace('%', ''))
                    
                    nuevas_cotizaciones.append({
                        'ticker': ticker,
                        'price': precio,
                        'change': variacion_bs,
                        'pct': variacion_pct
                    })
                except ValueError:
                    continue

        # 3. Inyectar los datos actualizados en el index.html
        if nuevas_cotizaciones:
            actualizar_index(tasa_bcv, nuevas_cotizaciones)
            print(f"Se actualizaron {len(nuevas_cotizaciones)} acciones en index.html")
        else:
            print("No se extrajeron acciones en esta ronda, manteniendo datos existentes.")

    except Exception as e:
        print(f"Error extrayendo BVC: {e}")

def actualizar_index(tasa_bcv, cotizaciones):
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            content = f.read()

        # Actualizar valor del BCV en el HTML
        content = re.sub(r'id="bcvRate"\s+value="[^"]*"', f'id="bcvRate" value="{tasa_bcv}"', content)

        # Convertir cotizaciones a formato JSON JS
        json_stocks = json.dumps(cotizaciones, indent=6)
        
        # Reemplazar la variable bvcStocks en el JavaScript de index.html
        content = re.sub(
            r'const bvcStocks = \[[\s\S]*?\];',
            f'const bvcStocks = {json_stocks};',
            content
        )

        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("index.html actualizado exitosamente.")
    except Exception as e:
        print(f"Error escribiendo index.html: {e}")

if __name__ == "__main__":
    obtener_datos_bvc_y_bcv()
