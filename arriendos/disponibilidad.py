"""Cuántas piezas quedan libres cada día.

Un arriendo activo (reservado o entregado) ocupa sus piezas desde el día de retiro hasta el de devolución,
ambos incluidos. Si se atrasa, las sigue ocupando hasta que vuelva. Un traje completo ocupa cada una de
sus piezas (× cantidad). Lo disponible en un rango de días es el stock menos el día más ocupado del rango."""
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from .models import Arriendo, Pieza, Traje


def dias(desde, hasta):
    d = desde
    while d <= hasta:
        yield d
        d += timedelta(days=1)


def piezas_de_lineas(lineas):
    """{pieza_id: unidades} de una lista de (traje o None, pieza o None, cantidad)."""
    uso = defaultdict(int)
    for traje, pieza, cantidad in lineas:
        if traje is not None:
            for c in traje.componentes.all():
                uso[c.pieza_id] += c.cantidad * cantidad
        elif pieza is not None:
            uso[pieza.id] += cantidad
    return uso


def _fin_ocupacion(arriendo, hoy):
    # Un arriendo entregado que no ha vuelto ocupa sus piezas hasta hoy aunque se haya pasado la fecha
    return max(arriendo.fecha_devolucion, hoy) if arriendo.estado == 'entregado' else arriendo.fecha_devolucion


def arriendos_activos(desde, hasta, excluir=None):
    """Arriendos que ocupan piezas en algún día entre desde y hasta."""
    hoy = timezone.localdate()
    qs = (Arriendo.objects.filter(estado__in=Arriendo.ACTIVOS, fecha_retiro__lte=hasta)
          .select_related('cliente').prefetch_related('lineas__traje__componentes', 'lineas__pieza'))
    if excluir:
        qs = qs.exclude(pk=excluir)
    return [a for a in qs if _fin_ocupacion(a, hoy) >= desde]


def uso_por_dia(desde, hasta, excluir=None):
    """{dia: {pieza_id: unidades ocupadas}} y {dia: [arriendos]} para cada día del rango."""
    hoy = timezone.localdate()
    uso = {d: defaultdict(int) for d in dias(desde, hasta)}
    quienes = {d: [] for d in uso}
    for a in arriendos_activos(desde, hasta, excluir):
        piezas = piezas_de_lineas((l.traje, l.pieza, l.cantidad) for l in a.lineas.all())
        for d in dias(max(a.fecha_retiro, desde), min(_fin_ocupacion(a, hoy), hasta)):
            quienes[d].append(a)
            for pid, n in piezas.items():
                uso[d][pid] += n
    return uso, quienes


def disponibles(desde, hasta, excluir=None):
    """{pieza_id: unidades libres en TODO el rango} (puede ser negativo si hay reservas de más)."""
    uso, _ = uso_por_dia(desde, hasta, excluir)
    libres = {}
    for p in Pieza.objects.all():
        pico = max((uso[d].get(p.id, 0) for d in uso), default=0)
        libres[p.id] = p.stock - pico
    return libres


def traje_disponible(traje, libres):
    """Cuántos trajes completos se pueden armar con las piezas libres."""
    comps = list(traje.componentes.all())
    if not comps:
        return 0
    return max(min(libres.get(c.pieza_id, 0) // c.cantidad for c in comps), 0)


def problemas(lineas, desde, hasta, excluir=None):
    """Mensajes si el pedido no cabe en el stock libre de esas fechas (lista vacía si todo cabe).
    lineas = [(traje o None, pieza o None, cantidad)]"""
    pedido = piezas_de_lineas(lineas)
    if not pedido:
        return []
    uso, quienes = uso_por_dia(desde, hasta, excluir)
    piezas = Pieza.objects.in_bulk(list(pedido))
    mensajes = []
    for pid, necesita in pedido.items():
        p = piezas[pid]
        peor = max(uso, key=lambda d: uso[d].get(pid, 0))
        libres = p.stock - uso[peor].get(pid, 0)
        if necesita > libres:
            otros = [a for a in quienes[peor] if any(
                (l.pieza_id == pid) or (l.traje_id and any(c.pieza_id == pid for c in l.traje.componentes.all())) for l in a.lineas.all())]
            detalle = ', '.join(f'{a.cliente} ({a.folio})' for a in otros[:4])
            mensajes.append(
                f'«{p}»: se necesitan {necesita} y el {peor:%d/%m} quedan {max(libres, 0)} de {p.stock}'
                + (f' (ya arrendados a {detalle})' if detalle else '') + '.')
    return mensajes


def sobre_reservas(desde, hasta):
    """{dia: [(pieza, ocupadas, stock)]} de los días en que se arrendó más de lo que hay."""
    uso, _ = uso_por_dia(desde, hasta)
    piezas = Pieza.objects.in_bulk()
    malos = {}
    for d, por_pieza in uso.items():
        exceso = [(piezas[pid], n, piezas[pid].stock) for pid, n in por_pieza.items() if pid in piezas and n > piezas[pid].stock]
        if exceso:
            malos[d] = exceso
    return malos


def resumen_trajes(desde, hasta, excluir=None):
    """Disponibilidad de cada traje y pieza activos en el rango, para mostrar y para el formulario de arriendo."""
    libres = disponibles(desde, hasta, excluir)
    trajes = [{'id': t.id, 'nombre': str(t), 'categoria': t.categoria.nombre if t.categoria_id else '', 'precio': int(t.precio),
               'disponibles': traje_disponible(t, libres),
               'piezas': [{'id': c.pieza_id, 'nombre': str(c.pieza), 'cantidad': c.cantidad} for c in t.componentes.all()]}
              for t in Traje.objects.filter(activo=True).select_related('categoria').prefetch_related('componentes__pieza')]
    piezas = [{'id': p.id, 'nombre': str(p), 'categoria': p.categoria.nombre if p.categoria_id else '', 'precio': int(p.precio),
               'stock': p.stock, 'disponibles': libres.get(p.id, p.stock), 'figurin': p.figurin}
              for p in Pieza.objects.filter(activo=True).select_related('categoria')]
    return {'trajes': trajes, 'piezas': piezas}
