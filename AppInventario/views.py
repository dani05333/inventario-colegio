from django.shortcuts import render
from .models import Colegio, Talla, Uniforme, Inventario, Venta, DetalleVenta
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Sum, Count, F
from django.utils.dateparse import parse_date
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils.dateparse import parse_date
from django.utils.timezone import make_aware, datetime as dj_datetime
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.timezone import now, timedelta

def inicio(request):
    return render(request, 'inicio.html')

def ver_colegios(request):
    colegios = Colegio.objects.all()
    return render(request, 'colegios.html', {'colegios': colegios})

def ver_tallas(request):
    tallas = Talla.objects.all()
    return render (request, 'tallas.html',{'tallas':tallas})

def ver_uniformes(request):
    uniformes = Uniforme.objects.all()
    return render (request, 'uniformes.html',{'uniformes':uniformes})

def ver_inventario(request):
    inventario = Inventario.objects.select_related('codigo_barra','colegio','talla','uniforme').all()
    return render (request, 'inventario.html',{'inventario':inventario})

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
    fields = ['codigo_barras','cantidad', 'colegio', 'talla', 'uniforme','precio']
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')

class ColegioUpdateView(UpdateView):
    model = Colegio
    fields = ['nombre']
    template_name = 'crear_colegios.html'
    success_url = reverse_lazy('ver_colegios')
    
class ColegioDeleteView(DeleteView):
    model = Colegio
    success_url = reverse_lazy('ver_colegios')
    template_name = 'confirmar_eliminar.html'
    
class TallasUpdateView(UpdateView):
    model = Talla
    fields = ['nombre']
    template_name = 'crear_tallas.html'
    success_url = reverse_lazy('ver_tallas')
    
class TallasDeleteView(DeleteView):
    model = Talla
    success_url = reverse_lazy('ver_tallas')
    template_name = 'confirmar_eliminar.html'
    
class UniformeUpdateView(UpdateView):
    model = Uniforme
    fields = ['nombre']
    template_name = 'crear_uniformes.html'
    success_url = reverse_lazy('ver_uniformes')
    
class UniformeDeleteView(DeleteView):
    model = Uniforme
    success_url = reverse_lazy('ver_uniformes')
    template_name = 'confirmar_eliminar.html'
    
class InventarioUpdateView(UpdateView):
    model = Inventario
    fields = ['cantidad', 'colegio', 'talla', 'uniforme','precio']
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')
    
class InventarioDeleteView(DeleteView):
    model = Inventario
    template_name = 'confirmar_eliminar.html'
    success_url = reverse_lazy('ver_inventario')
    
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

def punto_de_venta(request):
    return render(request, 'pos.html')

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

@csrf_exempt
def registrar_venta(request):
    data = json.loads(request.body)
    carrito = data.get('carrito', [])
    total = 0

    # Validar stock antes de hacer cualquier modificación
    for item in carrito:
        inventario = Inventario.objects.get(id=item['id'])
        if item['cantidad'] > inventario.cantidad:
            return JsonResponse({
                'status': 'error',
                'message': f"No hay suficiente stock de {inventario.uniforme.nombre} - {inventario.talla.nombre} - {inventario.colegio.nombre}."
            }, status=400)

        total += item['precio'] * item['cantidad']

    # Crear la venta porque ya validamos el stock
    venta = Venta.objects.create(total=total)

    for item in carrito:
        inventario = Inventario.objects.get(id=item['id'])

        # Registrar el detalle de la venta
        DetalleVenta.objects.create(
            venta=venta,
            inventario=inventario,
            cantidad=item['cantidad'],
            precio_unitario=inventario.precio,
            subtotal=item['cantidad'] * inventario.precio
        )

        # Actualizar el stock
        inventario.cantidad -= item['cantidad']
        inventario.save()

    return JsonResponse({'status': 'success'})



def historial_ventas(request):
    ventas = Venta.objects.prefetch_related('detalleventa_set').order_by('-fecha')
    return render(request, 'historial_ventas.html', {'ventas': ventas})

def dashboard_ventas(request):
    return render(request, 'dashboard.html')

def ventas_data(request):
    rango = request.GET.get('rango', 'dia')
    fecha_inicio = request.GET.get('inicio')
    fecha_fin = request.GET.get('fin')

    ventas_qs = Venta.objects.all()
    detalles = DetalleVenta.objects.select_related('venta', 'inventario__uniforme', 'inventario__talla', 'inventario__colegio')

    if fecha_inicio and fecha_fin:
        inicio_dt = make_aware(dj_datetime.combine(parse_date(fecha_inicio), dj_datetime.min.time()))
        fin_dt = make_aware(dj_datetime.combine(parse_date(fecha_fin), dj_datetime.max.time()))

        ventas_qs = ventas_qs.filter(fecha__range=(inicio_dt, fin_dt))
        detalles = detalles.filter(venta__fecha__range=(inicio_dt, fin_dt))

    # Agrupar según rango seleccionado (para gráfico de barras)
    ventas_grouped = ventas_qs
    if rango == 'dia':
        ventas_grouped = ventas_qs.annotate(fecha_group=TruncDate('fecha')).values('fecha_group').annotate(total=Sum('total'))
    elif rango == 'semana':
        ventas_grouped = ventas_qs.annotate(fecha_group=TruncWeek('fecha')).values('fecha_group').annotate(total=Sum('total'))
    elif rango == 'mes':
        ventas_grouped = ventas_qs.annotate(fecha_group=TruncMonth('fecha')).values('fecha_group').annotate(total=Sum('total'))

    # Construir listas de fechas y montos
    fechas = [v['fecha_group'].strftime('%Y-%m-%d') for v in ventas_grouped if v['fecha_group']]
    montos = [float(v['total']) for v in ventas_grouped]

    # KPI: Total ventas y cantidad de ventas (transacciones)
    total_ventas = ventas_qs.aggregate(total=Sum('total'))['total'] or 0
    cantidad_ventas = ventas_qs.count()

    # Agrupar productos más vendidos para el gráfico de torta
    productos = detalles.values(
        nombre=F('inventario__uniforme__nombre'),
        talla=F('inventario__talla__nombre'),
        colegio=F('inventario__colegio__nombre')
    ).annotate(
        cantidad=Sum('cantidad'),
        total=Sum('subtotal')
    ).order_by('-cantidad')[:5]

    productos_list = []
    for p in productos:
        productos_list.append({
            'nombre': p['nombre'],
            'talla': p['talla'],
            'colegio': p['colegio'],
            'cantidad': p['cantidad'],
            'total': p['total']
        })

    # Obtener producto más vendido específico (el primero del queryset)
    top_producto = productos_list[0] if productos_list else {'nombre': 'N/A', 'talla': '', 'colegio': ''}

    return JsonResponse({
        'fechas': fechas,
        'montos': montos,
        'productos': productos_list,
        'total_ventas': total_ventas,
        'cantidad_ventas': cantidad_ventas,
        'top_producto': top_producto  # <-- Se agrega esta clave
    })

    
    
@csrf_exempt  # Para desarrollo, mejor manejar CSRF token luego
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

    # Ordenamiento (opcional, puedes agregar según columnas recibidas)
    # Por simplicidad ordenamos por fecha de venta descendente
    detalles = detalles.order_by('-venta__fecha')

    # Paginación con Django Paginator
    paginator = Paginator(detalles, length)
    page_number = start // length + 1
    page_obj = paginator.get_page(page_number)

    data = []
    for detalle in page_obj:
        data.append({
            'fecha': detalle.venta.fecha.strftime('%d/%m/%Y %H:%M'),
            'cantidad': detalle.cantidad,
            'producto': detalle.inventario.uniforme.nombre,
            'talla': detalle.inventario.talla.nombre,
            'colegio': detalle.inventario.colegio.nombre,
            'subtotal': f"${detalle.subtotal:.2f}"
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
    hoy = now().date()
    hace_7_dias = hoy - timedelta(days=7)
    hace_14_dias = hoy - timedelta(days=14)

    # Ventas últimos 7 días
    recientes = DetalleVenta.objects.filter(
        venta__fecha__date__range=(hace_7_dias, hoy)
    ).values(
        nombre=F('inventario__uniforme__nombre'),
        talla=F('inventario__talla__nombre'),
        colegio=F('inventario__colegio__nombre')
    ).annotate(
        cantidad=Sum('cantidad')
    )

    # Ventas del período anterior
    anteriores = DetalleVenta.objects.filter(
        venta__fecha__date__range=(hace_14_dias, hace_7_dias)
    ).values(
        nombre=F('inventario__uniforme__nombre'),
        talla=F('inventario__talla__nombre'),
        colegio=F('inventario__colegio__nombre')
    ).annotate(
        cantidad=Sum('cantidad')
    )

    # Crear diccionarios para comparar
    anteriores_dict = { (a['nombre'], a['talla'], a['colegio']): a['cantidad'] for a in anteriores }

    tendencia = []
    for r in recientes:
        key = (r['nombre'], r['talla'], r['colegio'])
        cantidad_anterior = anteriores_dict.get(key, 0)
        crecimiento = r['cantidad'] - cantidad_anterior

        if crecimiento > 0:
            tendencia.append({
                'nombre': r['nombre'],
                'talla': r['talla'],
                'colegio': r['colegio'],
                'crecimiento': crecimiento
            })

    # Ordenar por mayor crecimiento
    tendencia = sorted(tendencia, key=lambda x: x['crecimiento'], reverse=True)[:5]

    return JsonResponse({'productos': tendencia})