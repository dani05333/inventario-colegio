"""Secciones del programa: la tienda de uniformes, la librería, el arriendo de trajes y los egresos.

Cada una tiene su nombre, su logo, su color (ver app.css: html[data-seccion]) y su menú lateral.
Se sabe en cuál se está por el espacio de nombres de la URL ('libreria:…', 'egresos:…')."""

SECCIONES = [
    {'clave': 'uniformes', 'nombre': 'Chloe Creaciones', 'sub': 'Uniformes escolares', 'etiqueta': 'Uniformes',
     'logo': 'AppInventario/logo.png', 'inicio': 'punto_de_venta', 'menu': 'partials/nav_uniformes.html'},
    {'clave': 'libreria', 'nombre': 'Chloe Librería', 'sub': 'Útiles escolares', 'etiqueta': 'Librería',
     'logo': 'AppInventario/logo-libreria.svg', 'inicio': 'libreria:pos', 'menu': 'libreria/nav.html'},
    {'clave': 'arriendos', 'nombre': 'Chloe Arriendos', 'sub': 'Trajes folclóricos', 'etiqueta': 'Arriendos',
     'logo': 'AppInventario/logo-arriendos.svg', 'inicio': 'arriendos:agenda', 'menu': 'arriendos/nav.html'},
    {'clave': 'egresos', 'nombre': 'Chloe Egresos', 'sub': 'Gastos y sueldos', 'etiqueta': 'Egresos',
     'logo': 'AppInventario/logo-egresos.svg', 'inicio': 'egresos:resumen', 'menu': 'egresos/nav.html'},
]
POR_CLAVE = {s['clave']: s for s in SECCIONES}


def actual(request):
    rm = getattr(request, 'resolver_match', None)
    espacio = rm.namespace if rm else ''
    return POR_CLAVE.get(espacio, POR_CLAVE['uniformes'])
