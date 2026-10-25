import json
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from AppInventario import seguridad
from AppInventario.forms import normalizar_nombre
from AppInventario.views import EliminarProtegidoMixin, _error, requiere_admin

from . import codigos
from .forms import CategoriaForm, ProductoForm
from .models import Categoria, DetalleVenta, Ingreso, Producto, Venta


def _producto_dict(p):
    return {
        'id': p.id, 'codigo': p.codigo_barras, 'nombre': p.nombre, 'marca': p.marca,
        'categoria': p.categoria.nombre if p.categoria_id else '', 'categoria_id': p.categoria_id,
        'precio': int(p.precio), 'stock': p.stock, 'stock_minimo': p.stock_minimo, 'activo': p.activo,
    }


def _venta_dict(venta):
    """La venta como la usa la boleta (App.receiptHtml): la marca va donde en uniformes va el colegio."""
    items = [{
        'inventario_id': d.producto_id, 'nombre': d.producto.nombre, 'talla': '', 'colegio': d.producto.marca,
        'cantidad': d.cantidad, 'precio': float(d.precio_unitario), 'subtotal': float(d.subtotal),
    } for d in venta.detalles.all()]
    return {
        'id': venta.id, 'folio': venta.folio, 'negocio': 'libreria',
        'fecha': venta.fecha.isoformat(), 'total': float(venta.total),
        'unidades': sum(i['cantidad'] for i in items), 'items': items, 'conjuntos': [],
        'metodo_pago': venta.metodo_pago, 'metodo_pago_nombre': venta.get_metodo_pago_display(),
        'anulada': venta.anulada,
        'fecha_anulacion': venta.fecha_anulacion.isoformat() if venta.fecha_anulacion else None,
        'motivo_anulacion': venta.motivo_anulacion,
    }


def _ventas_con_detalle():
    return Venta.objects.prefetch_related('detalles__producto')


# ---------------------------------------------------------------------------
# Punto de venta
# ---------------------------------------------------------------------------

def pos(request):
    return render(request, 'libreria/pos.html', {'metodos_pago': Venta.METODOS_PAGO})


@require_GET
def productos_json(request):
    """Productos para el punto de venta (solo los que se venden) o para el ingreso (?todos=1)."""
    productos = Producto.objects.select_related('categoria')
    if not request.GET.get('todos'):
        productos = productos.filter(activo=True)
    return JsonResponse({'data': [_producto_dict(p) for p in productos]})


@require_GET
def buscar_internet(request):
    """Nombre y marca de un código de barras según bases de datos públicas (si hay internet)."""
    encontrado = codigos.buscar_en_internet(request.GET.get('codigo'))
    return JsonResponse({'encontrado': bool(encontrado), **(encontrado or {})})


@require_GET
def generar_codigo(request):
    return JsonResponse({'codigo': codigos.generar_codigos(1)[0]})


@require_POST
def registrar_venta(request):
    # Solo se confía en el id y la cantidad; el precio sale de la base de datos
    try:
        datos = json.loads(request.body)
        metodo_pago = datos.get('metodo_pago') or 'efectivo'
        if metodo_pago not in dict(Venta.METODOS_PAGO):
            raise ValueError
        cantidades = defaultdict(int)
        for item in datos.get('carrito', []):
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
        productos = Producto.objects.select_for_update().in_bulk(list(cantidades))
        for pid, cantidad in cantidades.items():
            p = productos.get(pid)
            if p is None or not p.activo:
                return _error('Uno de los productos del carrito ya no está a la venta. Recarga la página.')
            if cantidad > p.stock:
                return _error(f'No hay suficiente stock de {p} (quedan {p.stock}).')
        venta = Venta.objects.create(total=0, metodo_pago=metodo_pago)
        total = Decimal(0)
        for pid, cantidad in cantidades.items():
            p = productos[pid]
            subtotal = p.precio * cantidad
            DetalleVenta.objects.create(venta=venta, producto=p, cantidad=cantidad, precio_unitario=p.precio, subtotal=subtotal)
            p.stock -= cantidad
            p.save(update_fields=['stock'])
            total += subtotal
        venta.total = total
        venta.save(update_fields=['total'])
    return JsonResponse({'status': 'success', 'venta': _venta_dict(_ventas_con_detalle().get(pk=venta.pk))})


# ---------------------------------------------------------------------------
# Historial (la lista se ve sin clave; los totales piden la clave)
# ---------------------------------------------------------------------------

def _rango(request, dias=30):
    hoy = timezone.localdate()
    desde = parse_date(request.GET.get('desde') or '') or hoy - timedelta(days=dias - 1)
    hasta = parse_date(request.GET.get('hasta') or '') or hoy
    if desde > hasta:
        desde, hasta = hasta, desde
    return desde, hasta


def historial(request):
    desde, hasta = _rango(request)
    inicio = timezone.make_aware(datetime.combine(desde, time.min))
    fin = timezone.make_aware(datetime.combine(hasta + timedelta(days=1), time.min))
    ventas = list(_ventas_con_detalle().filter(fecha__gte=inicio, fecha__lt=fin).order_by('-fecha'))
    validas = [v for v in ventas if not v.anulada]
    total = sum((v.total for v in validas), Decimal(0))
    contexto = {
        'desde': desde, 'hasta': hasta,
        'ventas': ventas,
        'ventas_data': [_venta_dict(v) for v in ventas],
        'metodos_pago': Venta.METODOS_PAGO,
    }
    if seguridad.acceso_admin(request):
        seguridad.renovar_acceso(request)
        mas_vendidos = (DetalleVenta.objects.filter(venta__in=validas)
                        .values('producto__nombre', 'producto__marca')
                        .annotate(unidades=Sum('cantidad'), total=Sum('subtotal')).order_by('-unidades')[:8])
        contexto['totales'] = {
            'boletas': len(validas), 'anuladas': len(ventas) - len(validas), 'total': total,
            'unidades': sum(sum(d.cantidad for d in v.detalles.all()) for v in validas),
            'ticket': total / len(validas) if validas else 0,
            'mas_vendidos': list(mas_vendidos),
        }
    respuesta = render(request, 'libreria/historial.html', contexto)
    respuesta['Cache-Control'] = 'no-store'   # que «Atrás» no muestre los totales después de bloquear
    return respuesta


@require_POST
def anular_venta(request, pk):
    """Anula una venta: deja de contar en los totales y, si se pide, devuelve el stock."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        datos = {}
    motivo = str(datos.get('motivo') or '').strip()[:200]
    if not motivo:
        return _error('Indica el motivo de la anulación.')
    try:
        seguridad.verificar(datos.get('clave'))
    except seguridad.ClaveError as e:
        return _error(str(e))
    with transaction.atomic():
        venta = get_object_or_404(Venta.objects.select_for_update(), pk=pk)
        if venta.anulada:
            return _error('Esta venta ya estaba anulada.')
        if datos.get('devolver_stock', True):
            for d in venta.detalles.all():
                Producto.objects.filter(pk=d.producto_id).update(stock=F('stock') + d.cantidad)
        venta.anulada = True
        venta.fecha_anulacion = timezone.now()
        venta.motivo_anulacion = motivo
        venta.save(update_fields=['anulada', 'fecha_anulacion', 'motivo_anulacion'])
    return JsonResponse({'status': 'success', 'venta': _venta_dict(_ventas_con_detalle().get(pk=pk))})


# ---------------------------------------------------------------------------
# Inventario (con clave)
# ---------------------------------------------------------------------------

@requiere_admin
def inventario(request):
    productos = list(Producto.objects.select_related('categoria'))
    activos = [p for p in productos if p.activo]
    return render(request, 'libreria/inventario.html', {
        'productos': productos,
        'categorias': Categoria.objects.all(),
        'resumen': {
            'productos': len(activos),
            'unidades': sum(p.stock for p in activos),
            'valor_costo': sum(p.stock * p.costo for p in activos),
            'valor_venta': sum(p.stock * p.precio for p in activos),
            'stock_bajo': sum(1 for p in activos if p.stock_bajo),
        },
    })


def _volver(request, defecto):
    volver = request.GET.get('volver') or request.POST.get('volver') or ''
    return volver if url_has_allowed_host_and_scheme(volver, allowed_hosts={request.get_host()}) else defecto


@requiere_admin
def producto_form(request, pk=None):
    producto = get_object_or_404(Producto, pk=pk) if pk else None
    volver = _volver(request, reverse('libreria:inventario'))
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            return redirect(volver)
    else:
        inicial = {'codigo_barras': request.GET.get('codigo', '')} if not producto else None
        form = ProductoForm(instance=producto, initial=inicial)
    return render(request, 'libreria/producto_form.html', {'form': form, 'producto': producto, 'volver': volver})


@require_POST
@requiere_admin
def producto_eliminar(request, pk):
    """Borra el producto; si ya tiene ventas, lo desactiva (deja de venderse pero el historial queda completo)."""
    producto = get_object_or_404(Producto, pk=pk)
    if producto.ventas.exists():
        producto.activo = False
        producto.save(update_fields=['activo'])
        return JsonResponse({'status': 'success', 'accion': 'desactivado'})
    producto.delete()
    return JsonResponse({'status': 'success', 'accion': 'eliminado'})


# ---------------------------------------------------------------------------
# Ingreso rápido de mercadería (con clave): se escanea lo que llegó
# ---------------------------------------------------------------------------

@requiere_admin
def ingreso(request):
    return render(request, 'libreria/ingreso.html', {'categorias': Categoria.objects.all()})


class IngresoError(ValueError):
    """Dato no válido en el ingreso (el mensaje se muestra tal cual)."""


def _entero(valor, que, producto, minimo=0):
    try:
        n = int(str(valor if valor is not None else '').strip() or 0)
    except ValueError:
        raise IngresoError(f'Revisa {que} de «{producto}».')
    if n < minimo:
        raise IngresoError(f'{que.capitalize()} de «{producto}» no puede ser menor que {minimo}.')
    return n


@require_POST
@requiere_admin
def ingreso_guardar(request):
    """Suma el stock de los productos escaneados (y actualiza su precio o costo si se cambió) y crea los
    productos nuevos. Todo o nada; cada ingreso queda registrado."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error('Datos no válidos.')
    existentes, nuevos = datos.get('existentes') or [], datos.get('nuevos') or []
    if not isinstance(existentes, list) or not isinstance(nuevos, list) or not (existentes or nuevos):
        return _error('No hay nada que guardar.')
    try:
        with transaction.atomic():
            sumados, creados = [], []
            for fila in existentes:
                p = Producto.objects.select_for_update().filter(pk=fila.get('id')).first()
                if not p:
                    raise IngresoError('Uno de los productos ya no existe. Recarga la página.')
                cantidad = _entero(fila.get('cantidad'), 'la cantidad', p)
                costo = _entero(fila.get('costo'), 'el costo', p) if fila.get('costo') not in (None, '') else None
                precio = _entero(fila.get('precio'), 'el precio', p) if fila.get('precio') not in (None, '') else None
                p.stock += cantidad
                if costo is not None:
                    p.costo = costo
                if precio is not None:
                    p.precio = precio
                p.activo = True
                p.save(update_fields=['stock', 'costo', 'precio', 'activo'])
                if cantidad:
                    Ingreso.objects.create(producto=p, cantidad=cantidad, costo_unitario=p.costo)
                sumados.append({'id': p.id, 'nombre': str(p), 'cantidad': cantidad, 'stock': p.stock})
            for fila in nuevos:
                nombre = normalizar_nombre(fila.get('nombre'))
                codigo = (fila.get('codigo') or '').strip() or codigos.generar_codigos(1)[0]
                if not nombre:
                    raise IngresoError(f'Falta el nombre del producto con código {codigo}.')
                if Producto.objects.filter(codigo_barras=codigo).exists():
                    raise IngresoError(f'Ya existe un producto con el código {codigo}.')
                categoria = Categoria.objects.filter(pk=fila.get('categoria_id')).first() if fila.get('categoria_id') else None
                p = Producto.objects.create(
                    codigo_barras=codigo, nombre=nombre, marca=normalizar_nombre(fila.get('marca')), categoria=categoria,
                    precio=_entero(fila.get('precio'), 'el precio', nombre), costo=_entero(fila.get('costo'), 'el costo', nombre),
                    stock=_entero(fila.get('cantidad'), 'la cantidad', nombre),
                    stock_minimo=_entero(fila.get('stock_minimo'), 'el aviso de stock', nombre),
                )
                if p.stock:
                    Ingreso.objects.create(producto=p, cantidad=p.stock, costo_unitario=p.costo)
                creados.append({'id': p.id, 'nombre': str(p), 'codigo': p.codigo_barras, 'cantidad': p.stock})
    except IngresoError as e:
        return _error(str(e))
    return JsonResponse({'status': 'success', 'sumados': sumados, 'creados': creados})


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def categorias(request):
    return render(request, 'libreria/categorias.html')


def categorias_json(request):
    return JsonResponse({'data': list(Categoria.objects.values('id', 'nombre'))})


class CategoriaCreateView(CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'libreria/categoria_form.html'
    success_url = reverse_lazy('libreria:categorias')


class CategoriaUpdateView(UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'libreria/categoria_form.html'
    success_url = reverse_lazy('libreria:categorias')


class CategoriaDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Categoria
    success_url = reverse_lazy('libreria:categorias')
