"""Conjuntos (por ejemplo, 'Buzo completo'): precio especial cuando se venden juntas varias prendas.

La misma lógica existe en JavaScript (App.armarConjuntos en app.js) para mostrar el precio en el POS
al instante; el precio oficial es siempre el que calcula esta función en el servidor.

Reglas:
  - Un conjunto se arma cuando en la venta hay una unidad de cada prenda que lo forma, del mismo colegio
    (y del colegio del conjunto, si tiene uno).
  - Para cada pieza se prefiere la misma talla que la primera; si no hay, sirve otra talla.
  - Precio: el de la talla (si se definió) o el general. Si las piezas son de tallas distintas, se usa
    el precio más alto entre esas tallas, para no cobrar de menos.
  - Solo se aplica si el conjunto sale más barato que las prendas por separado.
  - El precio del conjunto se reparte entre sus piezas en proporción a su precio normal, para que el
    análisis por producto refleje lo realmente cobrado.
"""
from decimal import Decimal

from .models import Conjunto


def conjuntos_activos():
    datos = []
    for c in Conjunto.objects.filter(activo=True).prefetch_related('componentes', 'precios_talla').order_by('id'):
        componentes = sorted(u.id for u in c.componentes.all())
        if len(componentes) < 2:
            continue
        datos.append({
            'id': c.id,
            'nombre': c.nombre,
            'colegio_id': c.colegio_id,
            'componentes': componentes,
            'precio': int(c.precio),
            'precios_talla': {str(p.talla_id): int(p.precio) for p in c.precios_talla.all()},
        })
    return datos


def armar(lineas, conjuntos):
    """lineas: [{'id', 'uniforme_id', 'talla_id', 'colegio_id', 'precio', 'cantidad'}] (precio normal por unidad).

    Devuelve (sets, cobrado) donde sets es la lista de conjuntos armados
    [{'conjunto_id', 'nombre', 'precio', 'piezas': [linea_id, ...], 'tallas': [talla_id, ...]}]
    y cobrado es {linea_id: monto total cobrado por esa línea}.
    """
    unidades = []
    for l in lineas:
        for _ in range(int(l['cantidad'])):
            unidades.append({**l, 'usada': False})

    sets = []
    for c in conjuntos:
        while True:
            armado = _buscar_set(unidades, c)
            if armado is None:
                break
            piezas, precio = armado
            normal = sum(int(u['precio']) for u in piezas)
            if precio >= normal:
                break   # no conviene: se cobran por separado
            for u in piezas:
                u['usada'] = True
            sets.append({
                'conjunto_id': c['id'],
                'nombre': c['nombre'],
                'precio': precio,
                'piezas': [u['id'] for u in piezas],
                'tallas': [u['talla_id'] for u in piezas],
                '_unidades': piezas,
            })

    cobrado = {l['id']: 0 for l in lineas}
    for u in unidades:
        if not u['usada']:
            cobrado[u['id']] += int(u['precio'])
    for s in sets:
        piezas = s.pop('_unidades')
        normal = sum(int(u['precio']) for u in piezas) or 1
        repartido = 0
        for i, u in enumerate(piezas):
            parte = s['precio'] - repartido if i == len(piezas) - 1 else round(s['precio'] * int(u['precio']) / normal)
            repartido += parte
            cobrado[u['id']] += parte
    return sets, cobrado


def _buscar_set(unidades, c):
    libres = [u for u in unidades if not u['usada']]
    primeras = [u for u in libres if u['uniforme_id'] == c['componentes'][0]
                and (c['colegio_id'] is None or u['colegio_id'] == c['colegio_id'])]
    for primera in primeras:
        piezas = [primera]
        for comp in c['componentes'][1:]:
            # se compara por identidad: dos unidades del mismo producto son dicts iguales
            candidatas = [u for u in libres if u['uniforme_id'] == comp and u['colegio_id'] == primera['colegio_id']
                          and all(u is not p for p in piezas)]
            if not candidatas:
                piezas = None
                break
            misma_talla = [u for u in candidatas if u['talla_id'] == primera['talla_id']]
            piezas.append((misma_talla or candidatas)[0])
        if piezas:
            precios = [c['precios_talla'].get(str(u['talla_id']), c['precio']) for u in piezas]
            return piezas, max(precios)
    return None


def total(lineas, conjuntos):
    _, cobrado = armar(lineas, conjuntos)
    return Decimal(sum(cobrado.values()))
