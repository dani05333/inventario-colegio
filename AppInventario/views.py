import json
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import F, ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .models import Colegio, DetalleVenta, Inventario, Talla, Uniforme, Venta


def inicio(request):
    return render(request, 'inicio.html')


# ---------------------------------------------------------------------------
# Eliminación protegida
# ---------------------------------------------------------------------------

# Cómo se nombra cada modelo dependiente en el mensaje de "no se puede eliminar"
NOMBRES_DEPENDENCIAS = {
    Inventario: ('producto del inventario', 'productos del inventario'),
    DetalleVenta: ('venta registrada', 'ventas registradas'),
}


def dependencias_protegidas(obj):
    """Lista de textos tipo '3 productos del inventario' que impiden borrar obj."""
    deps = []
    for rel in obj._meta.related_objects:
        if rel.on_delete is not models.PROTECT:
            continue
        n = getattr(obj, rel.get_accessor_name()).count()
        if n:
            singular, plural = NOMBRES_DEPENDENCIAS.get(
                rel.related_model,
                (rel.related_model._meta.verbose_name, rel.related_model._meta.verbose_name_plural),
            )
            deps.append(f"{n} {singular if n == 1 else plural}")
    return deps


class EliminarProtegidoMixin:
    """Muestra un aviso claro en vez de un error cuando el registro tiene datos asociados."""
    template_name = 'confirmar_eliminar.html'
    ayuda_bloqueo = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['dependencias'] = dependencias_protegidas(self.object)
        ctx['ayuda_bloqueo'] = self.ayuda_bloqueo
        ctx['volver_url'] = self.success_url
        return ctx

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            return self.render_to_response(self.get_context_data(form=form))


# ---------------------------------------------------------------------------
# Catálogos e inventario (CRUD)
# ---------------------------------------------------------------------------

class ColegioCreateView(CreateView):
    model = Colegio
    fields = ['nombre']
    template_name = 'crear_colegios.html'
    success_url = reverse_lazy('ver_colegios')


class TallaCreateView(CreateView):
    model = Talla
    fields = ['nombre']
    template_name = 'crear_tallas.html'
    success_url = reverse_lazy('ver_tallas')


class UniformeCreateView(CreateView):
    model = Uniforme
    fields = ['nombre']
    template_name = 'crear_uniformes.html'
    success_url = reverse_lazy('ver_uniformes')


class InventarioCreateView(CreateView):
    model = Inventario
    fields = ['codigo_barras', 'cantidad', 'colegio', 'talla', 'uniforme', 'precio']
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')


class ColegioUpdateView(UpdateView):
    model = Colegio
    fields = ['nombre']
    template_name = 'crear_colegios.html'
    success_url = reverse_lazy('ver_colegios')


class ColegioDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Colegio
    success_url = reverse_lazy('ver_colegios')
    ayuda_bloqueo = 'Primero elimina o cambia de colegio esos productos en el inventario.'


class TallasUpdateView(UpdateView):
    model = Talla
    fields = ['nombre']
    template_name = 'crear_tallas.html'
    success_url = reverse_lazy('ver_tallas')


class TallasDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Talla
    success_url = reverse_lazy('ver_tallas')
    ayuda_bloqueo = 'Primero elimina o cambia de talla esos productos en el inventario.'


class UniformeUpdateView(UpdateView):
    model = Uniforme
    fields = ['nombre']
    template_name = 'crear_uniformes.html'
    success_url = reverse_lazy('ver_uniformes')


class UniformeDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Uniforme
    success_url = reverse_lazy('ver_uniformes')
    ayuda_bloqueo = 'Primero elimina o cambia de uniforme esos productos en el inventario.'


class InventarioUpdateView(UpdateView):
    model = Inventario
    fields = ['codigo_barras', 'cantidad', 'colegio', 'talla', 'uniforme', 'precio']
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')


class InventarioDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Inventario
    success_url = reverse_lazy('ver_inventario')
    ayuda_bloqueo = 'Para que el historial quede completo, los productos con ventas no se borran. Si ya no lo vendes, deja su stock en 0.'


def ver_colegios(request):
    return render(request, 'colegios.html')

def colegios_json(request):
    colegios = Colegio.objects.all().values('id', 'nombre')
    data = list(colegios)
    return JsonResponse({'data': data})

def ver_tallas(request):
    return render(request, 'tallas.html')

def tallas_json(request):
    tallas = Talla.objects.all().values('id','nombre')
    data = list(tallas)
    return JsonResponse({'data': data})

def ver_uniformes(request):
    return render(request, 'uniformes.html')

def uniformes_json(request):
    uniformes = Uniforme.objects.all().values('id','nombre')
    data = list(uniformes)
    return JsonResponse({'data': data})

def ver_inventario(request):
    return render(request,'inventario.html')

def inventario_json(request):
    inventario = Inventario.objects.select_related('colegio', 'talla', 'uniforme').all()
    data = []

    for item in inventario:
        data.append({
            'id': item.id,
            'codigo_barras': item.codigo_barras,
            'colegio': item.colegio.nombre,
            'talla': item.talla.nombre,
            'uniforme': item.uniforme.nombre,
            'cantidad': item.cantidad,
            'precio_unitario': float(item.precio),
            'precio_total': float(item.cantidad * item.precio)
        })

    return JsonResponse({'data': data})


# ---------------------------------------------------------------------------
# Códigos de barras y etiquetas
# ---------------------------------------------------------------------------

# Los EAN-13 que empiezan con 200-299 están reservados para uso interno de cada
# tienda, así que no chocan con códigos de productos comerciales.
PREFIJO_CODIGO = '200'


def digito_control_ean13(base12):
    suma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base12))
    return str((10 - suma % 10) % 10)


def sin_codigo(codigo):
    return not codigo or codigo.strip() in ('', '0')


def generar_codigos(cantidad=1):
    """Devuelve `cantidad` códigos EAN-13 internos que no estén en uso."""
    existentes = set(Inventario.objects.values_list('codigo_barras', flat=True))
    usados = [int(c[3:12]) for c in existentes
              if len(c) == 13 and c.isdigit() and c.startswith(PREFIJO_CODIGO)]
    n = max(usados, default=0) + 1
    codigos = []
    while len(codigos) < cantidad:
        base = PREFIJO_CODIGO + str(n).zfill(9)
        codigo = base + digito_control_ean13(base)
        if codigo not in existentes:
            codigos.append(codigo)
        n += 1
    return codigos


@require_GET
def generar_codigo(request):
    return JsonResponse({'codigo': generar_codigos(1)[0]})


@require_POST
def asignar_codigos(request):
    """Asigna un código nuevo a todos los productos que no tienen."""
    with transaction.atomic():
        pendientes = [p for p in Inventario.objects.select_for_update() if sin_codigo(p.codigo_barras)]
        for producto, codigo in zip(pendientes, generar_codigos(len(pendientes))):
            producto.codigo_barras = codigo
            producto.save(update_fields=['codigo_barras'])
    return JsonResponse({'status': 'success', 'asignados': len(pendientes)})


def etiquetas(request):
    return render(request, 'etiquetas.html')


# ---------------------------------------------------------------------------
# Punto de venta
# ---------------------------------------------------------------------------

def punto_de_venta(request):
    return render(request, 'pos.html')


def pantalla_cliente(request):
    return render(request, 'pantalla_cliente.html')

def buscar_producto(request):
    codigo = request.GET.get('codigo')
    try:
        producto = Inventario.objects.select_related('talla', 'uniforme', 'colegio').get(codigo_barras=codigo)
        data = {
            'found': True,
            'producto': {
                'id': producto.id,
                'nombre': producto.uniforme.nombre,
                'talla': producto.talla.nombre,
                'colegio': producto.colegio.nombre,
                'precio': float(producto.precio),
            }
        }
    except Inventario.DoesNotExist:
        data = {'found': False}
    return JsonResponse(data)


def _error(mensaje):
    return JsonResponse({'status': 'error', 'message': mensaje}, status=400)


@require_POST
def registrar_venta(request):
    # Leer el carrito: solo se confía en el id y la cantidad; el precio sale de la base de datos
    try:
        datos = json.loads(request.body)
        carrito = datos.get('carrito', [])
        metodo_pago = datos.get('metodo_pago') or 'efectivo'
        if metodo_pago not in dict(Venta.METODOS_PAGO):
            raise ValueError
        cantidades = defaultdict(int)
        for item in carrito:
            cantidad = int(item['cantidad'])
            if cantidad <= 0:
                raise ValueError
            cantidades[int(item['id'])] += cantidad
    except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
        return _error('Los datos de la venta no son válidos.')

    if not cantidades:
        return _error('El carrito está vacío.')

    # Todo o nada: si algo falla, no se descuenta stock ni queda una venta a medias
    with transaction.atomic():
        productos = (Inventario.objects.select_for_update()
                     .select_related('uniforme', 'talla', 'colegio')
                     .in_bulk(list(cantidades)))

        for producto_id, cantidad in cantidades.items():
            producto = productos.get(producto_id)
            if producto is None:
                return _error('Uno de los productos del carrito ya no existe. Recarga la página.')
            if cantidad > producto.cantidad:
                return _error(
                    f"No hay suficiente stock de {producto.uniforme.nombre} - {producto.talla.nombre} - "
                    f"{producto.colegio.nombre} (quedan {producto.cantidad})."
                )

        venta = Venta.objects.create(total=0, metodo_pago=metodo_pago)
        total = Decimal(0)
        for producto_id, cantidad in cantidades.items():
            producto = productos[producto_id]
            subtotal = producto.precio * cantidad
            DetalleVenta.objects.create(
                venta=venta,
                inventario=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio,
                subtotal=subtotal,
            )
            producto.cantidad -= cantidad
            producto.save(update_fields=['cantidad'])
            total += subtotal

        venta.total = total
        venta.save(update_fields=['total'])

    return JsonResponse({'status': 'success', 'venta_id': venta.id, 'total': float(total)})


# ---------------------------------------------------------------------------
# Historial y boletas
# ---------------------------------------------------------------------------

def _venta_dict(venta):
    items = [{
        'nombre': d.inventario.uniforme.nombre,
        'talla': d.inventario.talla.nombre,
        'colegio': d.inventario.colegio.nombre,
        'cantidad': d.cantidad,
        'precio': float(d.precio_unitario),
        'subtotal': float(d.subtotal),
    } for d in venta.detalleventa_set.all()]
    return {
        'id': venta.id,
        'fecha': venta.fecha.isoformat(),
        'total': float(venta.total),
        'unidades': sum(i['cantidad'] for i in items),
        'items': items,
        'metodo_pago': venta.metodo_pago,
        'metodo_pago_nombre': venta.get_metodo_pago_display(),
    }


def _ventas_con_detalle():
    return Venta.objects.prefetch_related(
        'detalleventa_set__inventario__uniforme',
        'detalleventa_set__inventario__talla',
        'detalleventa_set__inventario__colegio',
    )


def historial_ventas(request):
    ventas = _ventas_con_detalle().order_by('-fecha')
    return render(request, 'historial_ventas.html', {'ventas_data': [_venta_dict(v) for v in ventas]})


def boleta(request, pk):
    venta = get_object_or_404(_ventas_con_detalle(), pk=pk)
    anterior = Venta.objects.filter(pk__lt=pk).order_by('-pk').values_list('pk', flat=True).first()
    siguiente = Venta.objects.filter(pk__gt=pk).order_by('pk').values_list('pk', flat=True).first()
    return render(request, 'boleta.html', {
        'venta': venta,
        'venta_data': _venta_dict(venta),
        'anterior': anterior,
        'siguiente': siguiente,
    })


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

def dashboard_ventas(request):
    return render(request, 'dashboard.html')


def _inicio_del_dia(fecha):
    """Medianoche local de `fecha` como datetime con zona horaria."""
    return timezone.make_aware(datetime.combine(fecha, time.min))


def ventas_data(request):
    rango = request.GET.get('rango', 'dia')
    fecha_inicio = parse_date(request.GET.get('inicio') or '')
    fecha_fin = parse_date(request.GET.get('fin') or '')

    ventas_qs = Venta.objects.all()
    detalles = DetalleVenta.objects.all()

    if fecha_inicio and fecha_fin:
        desde = _inicio_del_dia(fecha_inicio)
        hasta = _inicio_del_dia(fecha_fin + timedelta(days=1))
        ventas_qs = ventas_qs.filter(fecha__gte=desde, fecha__lt=hasta)
        detalles = detalles.filter(venta__fecha__gte=desde, venta__fecha__lt=hasta)

    # Agrupar en Python usando la hora local (funciona igual en SQLite y MySQL,
    # sin depender de las tablas de zonas horarias de la base de datos)
    grupos = defaultdict(Decimal)
    for fecha, total in ventas_qs.values_list('fecha', 'total'):
        dia = timezone.localtime(fecha).date()
        if rango == 'semana':
            dia -= timedelta(days=dia.weekday())
        elif rango == 'mes':
            dia = dia.replace(day=1)
        grupos[dia] += total

    fechas = [d.strftime('%Y-%m-%d') for d in sorted(grupos)]
    montos = [float(grupos[d]) for d in sorted(grupos)]

    # KPI: Total ventas, cantidad de ventas (transacciones) y unidades vendidas
    total_ventas = float(ventas_qs.aggregate(total=Sum('total'))['total'] or 0)
    cantidad_ventas = ventas_qs.count()
    unidades_vendidas = detalles.aggregate(total=Sum('cantidad'))['total'] or 0

    # Productos más vendidos
    productos = detalles.values(
        nombre=F('inventario__uniforme__nombre'),
        talla=F('inventario__talla__nombre'),
        colegio=F('inventario__colegio__nombre')
    ).annotate(
        cantidad=Sum('cantidad'),
        total=Sum('subtotal')
    ).order_by('-cantidad')[:8]

    productos_list = [{
        'nombre': p['nombre'],
        'talla': p['talla'],
        'colegio': p['colegio'],
        'cantidad': p['cantidad'],
        'total': float(p['total'] or 0),
    } for p in productos]

    top_producto = productos_list[0] if productos_list else {'nombre': 'N/A', 'talla': '', 'colegio': ''}

    return JsonResponse({
        'fechas': fechas,
        'montos': montos,
        'productos': productos_list,
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'unidades_vendidas': unidades_vendidas,
        'top_producto': top_producto,
    })


def historial_ventas_json(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()

    detalles = DetalleVenta.objects.select_related(
        'venta', 'inventario__uniforme', 'inventario__talla', 'inventario__colegio'
    ).all()

    # Filtrado simple por búsqueda (producto, talla, colegio)
    if search_value:
        detalles = detalles.filter(
            Q(inventario__uniforme__nombre__icontains=search_value) |
            Q(inventario__talla__nombre__icontains=search_value) |
            Q(inventario__colegio__nombre__icontains=search_value)
        )

    total_records = detalles.count()
    detalles = detalles.order_by('-venta__fecha')

    paginator = Paginator(detalles, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    data = []
    for detalle in page_obj:
        data.append({
            'fecha': timezone.localtime(detalle.venta.fecha).strftime('%d/%m/%Y %H:%M'),
            'cantidad': detalle.cantidad,
            'producto': detalle.inventario.uniforme.nombre,
            'talla': detalle.inventario.talla.nombre,
            'colegio': detalle.inventario.colegio.nombre,
            'subtotal': f"${detalle.subtotal:.0f}"
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data,
    })


def stock_bajo(request):
    umbral = 10  # Stock crítico
    inventario_bajo = Inventario.objects.filter(cantidad__lt=umbral).select_related('uniforme', 'talla', 'colegio')

    productos = []
    for item in inventario_bajo:
        productos.append({
            'id': item.id,
            'nombre': item.uniforme.nombre,
            'talla': item.talla.nombre,
            'colegio': item.colegio.nombre,
            'stock': item.cantidad
        })

    return JsonResponse({'productos': productos})


def productos_tendencia(request):
    hoy = timezone.localdate()
    fin = _inicio_del_dia(hoy + timedelta(days=1))
    corte = _inicio_del_dia(hoy - timedelta(days=6))     # últimos 7 días (incluye hoy)
    inicio = _inicio_del_dia(hoy - timedelta(days=13))   # los 7 días anteriores

    def vendidos(desde, hasta):
        return DetalleVenta.objects.filter(
            venta__fecha__gte=desde, venta__fecha__lt=hasta
        ).values(
            nombre=F('inventario__uniforme__nombre'),
            talla=F('inventario__talla__nombre'),
            colegio=F('inventario__colegio__nombre')
        ).annotate(cantidad=Sum('cantidad'))

    anteriores = {(a['nombre'], a['talla'], a['colegio']): a['cantidad'] for a in vendidos(inicio, corte)}

    tendencia = []
    for r in vendidos(corte, fin):
        crecimiento = r['cantidad'] - anteriores.get((r['nombre'], r['talla'], r['colegio']), 0)
        if crecimiento > 0:
            tendencia.append({
                'nombre': r['nombre'],
                'talla': r['talla'],
                'colegio': r['colegio'],
                'crecimiento': crecimiento
            })

    tendencia = sorted(tendencia, key=lambda x: x['crecimiento'], reverse=True)[:5]

    return JsonResponse({'productos': tendencia})
