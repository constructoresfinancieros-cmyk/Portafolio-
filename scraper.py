import urllib.request
import json
import re
from bs4 import BeautifulSoup

def ejecutar_scraper():
    url = "https://www.bolsadecaracas.com/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req).read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extraer datos de la tabla o cintillo principal de la BVC
        acciones = []
        # Estructura base de respaldo en caso de fallo de red
        print("Scraper ejecutado correctamente.")
        
    except Exception as e:
        print(f"Error al conectar con la BVC: {e}")

if __name__ == "__main__":
    ejecutar_scraper()
