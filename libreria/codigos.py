"""Códigos de barras de la librería: códigos internos para lo que no trae código y búsqueda en internet
del nombre de un producto a partir de su código (para no tener que escribirlo)."""
import json
import re
import urllib.parse
import urllib.request

from AppInventario.views import digito_control_ean13

from .models import Producto

# Los EAN-13 que empiezan con 200-299 son de uso interno de cada tienda. Los uniformes usan 200;
# la librería usa 201, así nunca se repiten entre las dos.
PREFIJO = '201'


def generar_codigos(cantidad=1):
    """`cantidad` códigos EAN-13 internos que no estén en uso."""
    existentes = set(Producto.objects.values_list('codigo_barras', flat=True))
    usados = [int(c[3:12]) for c in existentes if len(c) == 13 and c.isdigit() and c.startswith(PREFIJO)]
    n = max(usados, default=0) + 1
    codigos = []
    while len(codigos) < cantidad:
        base = PREFIJO + str(n).zfill(9)
        codigo = base + digito_control_ean13(base)
        if codigo not in existentes:
            codigos.append(codigo)
        n += 1
    return codigos


# Bases de datos públicas de productos. Para útiles escolares la cobertura es parcial: si no se encuentra,
# se escribe el nombre a mano.
FUENTES = [
    ('https://world.openproductsfacts.org/api/v2/product/{codigo}.json?fields=product_name,brands', 'openfacts'),
    ('https://world.openfoodfacts.org/api/v2/product/{codigo}.json?fields=product_name,brands', 'openfacts'),
    ('https://api.upcitemdb.com/prod/trial/lookup?upc={codigo}', 'upcitemdb'),
]


def _leer(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ChloePOS/1.6 (libreria; contacto: tienda)'})
    with urllib.request.urlopen(req, timeout=4) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def _es_basura(nombre):
    """Registros de prueba que algunas bases públicas tienen cargados (ej. «Diagnostic Test Product DELETE ME»)."""
    n = nombre.lower()
    return 'delete me' in n or 'test product' in n or n in {'test', 'prueba'}


def buscar_en_internet(codigo):
    """{'nombre', 'marca'} si alguna base pública conoce el código; si no (o no hay internet), None."""
    codigo = (codigo or '').strip()
    if not re.fullmatch(r'\d{8,14}', codigo):
        return None
    for plantilla, tipo in FUENTES:
        try:
            datos = _leer(plantilla.format(codigo=urllib.parse.quote(codigo)))
        except (OSError, ValueError):
            continue
        if tipo == 'openfacts' and datos.get('status') == 1:
            p = datos.get('product') or {}
            nombre = (p.get('product_name') or '').strip()
            if nombre and not _es_basura(nombre):
                return {'nombre': nombre, 'marca': (p.get('brands') or '').split(',')[0].strip()}
        if tipo == 'upcitemdb':
            items = datos.get('items') or []
            if items and (items[0].get('title') or '').strip() and not _es_basura(items[0]['title']):
                return {'nombre': items[0]['title'].strip(), 'marca': (items[0].get('brand') or '').strip()}
    return None
