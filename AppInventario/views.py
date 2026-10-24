import json
import logging
import mimetypes
import re
from collections import defaultdict
from functools import wraps
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import F, ProtectedError, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from . import conjuntos, impresora, presentacion, seguridad, sistema
from .forms import ColegioForm, ColorForm, ConjuntoForm, InventarioForm, TallaForm, UniformeForm
from .models import Colegio, Color, Conjunto, DetalleVenta, Inventario, PrecioConjuntoTalla, Talla, Uniforme, Venta

logger = logging.getLogger(__name__)


def inicio(request):
    return render(request, 'inicio.html')


# ---------------------------------------------------------------------------
# Secciones con montos de venta (historial, boletas, análisis): solo con la clave de administrador
# ---------------------------------------------------------------------------

def requiere_admin(vista):
    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        if seguridad.acceso_admin(request):
            seguridad.renovar_acceso(request)
            respuesta = vista(request, *args, **kwargs)
            # Que el botón «Atrás» no muestre una copia guardada cuando el acceso ya se cerró
            respuesta['Cache-Control'] = 'no-store'
            return respuesta
        if request.path.startswith('/api/'):
            return JsonResponse({'status': 'error', 'message': 'Ingresa la clave de administrador para ver esta información.'}, status=403)
        return render(request, 'acceso_admin.html', {'siguiente': request.get_full_path()}, status=403)
    return envuelta


@require_POST
def abrir_acceso(request):
    siguiente = request.POST.get('siguiente') or ''
    if not url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
        siguiente = reverse('punto_de_venta')
    try:
        seguridad.abrir_acceso(request, request.POST.get('clave'))
    except seguridad.ClaveError as e:
        return render(request, 'acceso_admin.html', {'siguiente': siguiente, 'error': str(e)}, status=403)
    return redirect(siguiente)


@require_POST
def cerrar_acceso(request):
    seguridad.cerrar_acceso(request)
    return redirect('punto_de_venta')


# ---------------------------------------------------------------------------
# Eliminación protegida
# ---------------------------------------------------------------------------

# Cómo se nombra cada modelo dependiente en el mensaje de "no se puede eliminar"
NOMBRES_DEPENDENCIAS = {
    Inventario: ('producto del inventario', 'productos del inventario'),
    DetalleVenta: ('venta registrada', 'ventas registradas'),
    Conjunto: ('conjunto', 'conjuntos'),
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
            seguridad.verificar(self.request.POST.get('clave'))
        except seguridad.ClaveError as e:
            return self.render_to_response(self.get_context_data(form=form, error_clave=str(e)))
        try:
            return super().form_valid(form)
        except ProtectedError:
            return self.render_to_response(self.get_context_data(form=form))


# ---------------------------------------------------------------------------
# Catálogos e inventario (CRUD)
# ---------------------------------------------------------------------------

class ColegioCreateView(CreateView):
    model = Colegio
    form_class = ColegioForm
    template_name = 'crear_colegios.html'
    success_url = reverse_lazy('ver_colegios')


class TallaCreateView(CreateView):
    model = Talla
    form_class = TallaForm
    template_name = 'crear_tallas.html'
    success_url = reverse_lazy('ver_tallas')


class UniformeCreateView(CreateView):
    model = Uniforme
    form_class = UniformeForm
    template_name = 'crear_uniformes.html'
    success_url = reverse_lazy('ver_uniformes')


class InventarioCreateView(CreateView):
    model = Inventario
    form_class = InventarioForm
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')


class ColegioUpdateView(UpdateView):
    model = Colegio
    form_class = ColegioForm
    template_name = 'crear_colegios.html'
    success_url = reverse_lazy('ver_colegios')


class ColegioDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Colegio
    success_url = reverse_lazy('ver_colegios')
    ayuda_bloqueo = 'Primero elimina o cambia de colegio esos productos en el inventario.'


class TallasUpdateView(UpdateView):
    model = Talla
    form_class = TallaForm
    template_name = 'crear_tallas.html'
    success_url = reverse_lazy('ver_tallas')


class TallasDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Talla
    success_url = reverse_lazy('ver_tallas')
    ayuda_bloqueo = 'Primero elimina o cambia de talla esos productos en el inventario.'


class UniformeUpdateView(UpdateView):
    model = Uniforme
    form_class = UniformeForm
    template_name = 'crear_uniformes.html'
    success_url = reverse_lazy('ver_uniformes')


class UniformeDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Uniforme
    success_url = reverse_lazy('ver_uniformes')
    ayuda_bloqueo = 'Primero elimina o cambia de uniforme esos productos en el inventario.'


class InventarioUpdateView(UpdateView):
    model = Inventario
    form_class = InventarioForm
    template_name = 'crear_inventario.html'
    success_url = reverse_lazy('ver_inventario')


class InventarioDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Inventario
    success_url = reverse_lazy('ver_inventario')
    ayuda_bloqueo = 'Para que el historial quede completo, los productos con ventas no se borran. Si ya no lo vendes, deja su stock en 0.'


class ColorCreateView(CreateView):
    model = Color
    form_class = ColorForm
    template_name = 'crear_colores.html'
    success_url = reverse_lazy('ver_colores')


class ColorUpdateView(UpdateView):
    model = Color
    form_class = ColorForm
    template_name = 'crear_colores.html'
    success_url = reverse_lazy('ver_colores')


class ColorDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Color
    success_url = reverse_lazy('ver_colores')
    ayuda_bloqueo = 'Primero cambia de color o elimina esos productos en el inventario.'


def ver_colores(request):
    return render(request, 'colores.html')


def colores_json(request):
    return JsonResponse({'data': list(Color.objects.values('id', 'nombre'))})


# ---------------------------------------------------------------------------
# Conjuntos (por ejemplo, 'Buzo completo')
# ---------------------------------------------------------------------------

def ver_conjuntos(request):
    lista = (Conjunto.objects.select_related('colegio')
             .prefetch_related('componentes', 'precios_talla__talla').order_by('nombre'))
    return render(request, 'conjuntos.html', {'conjuntos': lista})


def editar_conjunto(request, pk=None):
    conjunto = get_object_or_404(Conjunto, pk=pk) if pk else None
    tallas = list(Talla.objects.all())
    form = ConjuntoForm(request.POST or None, instance=conjunto)
    precios = {p.talla_id: p.precio for p in conjunto.precios_talla.all()} if conjunto else {}
    error_precios = None

    if request.method == 'POST':
        nuevos = {}
        for t in tallas:
            valor = (request.POST.get(f'precio_talla_{t.id}') or '').strip().replace('.', '')
            if valor:
                if not valor.isdigit():
                    error_precios = f'El precio de la talla {t} no es un número válido.'
                else:
                    nuevos[t.id] = int(valor)
        precios = nuevos
        if form.is_valid() and not error_precios:
            with transaction.atomic():
                conjunto = form.save()
                conjunto.precios_talla.all().delete()
                PrecioConjuntoTalla.objects.bulk_create(
                    [PrecioConjuntoTalla(conjunto=conjunto, talla_id=tid, precio=precio) for tid, precio in nuevos.items()])
            return redirect('ver_conjuntos')

    return render(request, 'crear_conjunto.html', {
        'form': form,
        'conjunto': conjunto,
        'filas_tallas': [(t, precios.get(t.id, '')) for t in tallas],
        'error_precios': error_precios,
    })


class ConjuntoDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Conjunto
    success_url = reverse_lazy('ver_conjuntos')


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
    inventario = Inventario.objects.select_related('colegio', 'talla', 'uniforme', 'color').all()
    data = []

    for item in inventario:
        data.append({
            'id': item.id,
            'codigo_barras': item.codigo_barras,
            'colegio': item.colegio.nombre,
            'talla': item.talla.nombre,
            'uniforme': item.uniforme.nombre,
            'color': item.color.nombre if item.color_id else '',
            'nombre': item.nombre_completo,
            'uniforme_id': item.uniforme_id,
            'talla_id': item.talla_id,
            'colegio_id': item.colegio_id,
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
                     .select_related('uniforme', 'talla', 'colegio', 'color')
                     .in_bulk(list(cantidades)))

        for producto_id, cantidad in cantidades.items():
            producto = productos.get(producto_id)
            if producto is None:
                return _error('Uno de los productos del carrito ya no existe. Recarga la página.')
            if cantidad > producto.cantidad:
                return _error(
                    f"No hay suficiente stock de {producto.nombre_completo} - {producto.talla.nombre} - "
                    f"{producto.colegio.nombre} (quedan {producto.cantidad})."
                )

        # Precios: los de la base de datos, aplicando los conjuntos (por ejemplo, 'Buzo completo')
        lineas = [{
            'id': pid, 'uniforme_id': productos[pid].uniforme_id, 'talla_id': productos[pid].talla_id,
            'colegio_id': productos[pid].colegio_id, 'precio': int(productos[pid].precio), 'cantidad': cant,
        } for pid, cant in cantidades.items()]
        armados, cobrado = conjuntos.armar(lineas, conjuntos.conjuntos_activos())

        venta = Venta.objects.create(total=0, metodo_pago=metodo_pago)
        total = Decimal(0)
        for producto_id, cantidad in cantidades.items():
            producto = productos[producto_id]
            subtotal = Decimal(cobrado[producto_id])
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
        venta.conjuntos = [{
            'nombre': a['nombre'],
            'precio': a['precio'],
            'talla': ' / '.join(dict.fromkeys(productos[pid].talla.nombre for pid in a['piezas'])),
            'piezas': [{'inventario_id': pid, 'nombre': productos[pid].nombre_completo,
                        'talla': productos[pid].talla.nombre} for pid in a['piezas']],
        } for a in armados]
        venta.save(update_fields=['total', 'conjuntos'])

    venta = _ventas_con_detalle().get(pk=venta.pk)
    return JsonResponse({'status': 'success', 'venta_id': venta.id, 'total': float(total), 'venta': _venta_dict(venta)})


@require_GET
def conjuntos_activos(request):
    return JsonResponse({'conjuntos': conjuntos.conjuntos_activos()})


# ---------------------------------------------------------------------------
# Historial y boletas
# ---------------------------------------------------------------------------

def _venta_dict(venta):
    items = [{
        'inventario_id': d.inventario_id,
        'nombre': d.inventario.nombre_completo,
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
        'anulada': venta.anulada,
        'fecha_anulacion': venta.fecha_anulacion.isoformat() if venta.fecha_anulacion else None,
        'motivo_anulacion': venta.motivo_anulacion,
        'conjuntos': venta.conjuntos or [],
    }


def _ventas_con_detalle():
    return Venta.objects.prefetch_related(
        'detalleventa_set__inventario__uniforme',
        'detalleventa_set__inventario__talla',
        'detalleventa_set__inventario__colegio',
        'detalleventa_set__inventario__color',
    )


@requiere_admin
def historial_ventas(request):
    ventas = _ventas_con_detalle().order_by('-fecha')
    return render(request, 'historial_ventas.html', {'ventas_data': [_venta_dict(v) for v in ventas]})


@require_POST
def anular_venta(request, pk):
    """Anula una venta: deja de contar en totales y análisis, y opcionalmente devuelve el stock."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        datos = {}
    motivo = str(datos.get('motivo') or '').strip()[:200]
    devolver_stock = bool(datos.get('devolver_stock', True))
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
        if devolver_stock:
            for detalle in venta.detalleventa_set.select_related('inventario'):
                Inventario.objects.filter(pk=detalle.inventario_id).update(cantidad=F('cantidad') + detalle.cantidad)
        venta.anulada = True
        venta.fecha_anulacion = timezone.now()
        venta.motivo_anulacion = motivo
        venta.save(update_fields=['anulada', 'fecha_anulacion', 'motivo_anulacion'])

    venta = _ventas_con_detalle().get(pk=pk)
    return JsonResponse({'status': 'success', 'venta': _venta_dict(venta)})


@requiere_admin
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
# Sistema: versión, respaldos y actualizaciones
# ---------------------------------------------------------------------------

def ver_sistema(request):
    return render(request, 'sistema.html', {
        'respaldos': sistema.listar_respaldos(),
        'respaldos_dir': settings.RESPALDOS_DIR,
        'datos_dir': settings.DATA_DIR,
        'total_ventas': Venta.objects.count(),
        'ventas_anuladas': Venta.objects.filter(anulada=True).count(),
        'presentacion': presentacion.ajustes(),
        'presentacion_items': [{'nombre': n, 'video': presentacion.es_video(n)} for n in presentacion.archivos()],
        'presentacion_max_mb': (presentacion.MAX_MB, presentacion.MAX_MB_VIDEO),
        'segundos_opciones': presentacion.SEGUNDOS_OPCIONES,
        'boleta_anchos': impresora.ANCHOS,
    })


@require_POST
def boleta_config(request):
    try:
        datos = json.loads(request.body or '{}')
        impresora.guardar_ancho(datos.get('ancho'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return _error('Ancho de rollo no válido.')
    return JsonResponse({'status': 'success', 'ancho': impresora.ancho()})


@require_GET
def impresora_estado(request):
    return JsonResponse(impresora.estado())


@require_POST
def impresora_instalar_driver(request):
    try:
        ancho = json.loads(request.body or '{}').get('ancho')   # 58 / 80; sin ancho = el de la boleta
        impresora.instalar_driver(int(ancho) if ancho else None)
    except (TypeError, json.JSONDecodeError):
        return _error('Ancho de rollo no válido.')
    except (ValueError, OSError) as e:
        return _error(str(e) if isinstance(e, ValueError) else 'No se pudo abrir el instalador del driver.')
    return JsonResponse({'status': 'success'})


# ---------------------------------------------------------------------------
# Presentación de imágenes en la pantalla del cliente
# ---------------------------------------------------------------------------

@require_GET
def presentacion_datos(request):
    return JsonResponse({
        **presentacion.ajustes(),
        'items': [{'url': reverse('presentacion_imagen', args=[n]), 'video': presentacion.es_video(n)}
                  for n in presentacion.archivos()],
    })


TROZO_VIDEO = 4 * 1024 * 1024   # bytes por respuesta cuando el navegador pide un video por partes


@require_GET
def presentacion_imagen(request, nombre):
    """Imagen o video de la presentación. Los videos se entregan por partes (Range), como los pide
    el navegador para reproducirlos sin cargarlos enteros."""
    ruta = presentacion.ruta_segura(nombre)
    if ruta is None:
        raise Http404
    tipo = mimetypes.guess_type(ruta.name)[0] or 'application/octet-stream'
    rango = re.fullmatch(r'bytes=(\d*)-(\d*)', request.headers.get('Range', '').strip())
    if not rango or not (rango.group(1) or rango.group(2)):
        respuesta = FileResponse(open(ruta, 'rb'), content_type=tipo)
    else:
        tamano = ruta.stat().st_size
        if rango.group(1):
            inicio = int(rango.group(1))
            fin = int(rango.group(2)) if rango.group(2) else tamano - 1
        else:   # «bytes=-N»: los últimos N bytes
            inicio, fin = max(0, tamano - int(rango.group(2))), tamano - 1
        fin = min(fin, tamano - 1, inicio + TROZO_VIDEO - 1)
        if inicio > fin:
            respuesta = HttpResponse(status=416)
            respuesta['Content-Range'] = f'bytes */{tamano}'
            return respuesta
        with open(ruta, 'rb') as f:
            f.seek(inicio)
            respuesta = HttpResponse(f.read(fin - inicio + 1), status=206, content_type=tipo)
        respuesta['Content-Range'] = f'bytes {inicio}-{fin}/{tamano}'
    respuesta['Accept-Ranges'] = 'bytes'
    respuesta['Cache-Control'] = 'max-age=86400'
    return respuesta


@require_POST
def presentacion_config(request):
    try:
        datos = json.loads(request.body or '{}')
        presentacion.guardar_ajustes(bool(datos.get('activa')), datos.get('segundos', 5))
    except (ValueError, TypeError, json.JSONDecodeError):
        return _error('Ajustes no válidos.')
    return JsonResponse({'status': 'success', **presentacion.ajustes()})


@require_POST
def presentacion_subir(request):
    archivos = request.FILES.getlist('imagenes')
    if not archivos:
        return _error('Elige al menos una imagen o video.')
    guardadas, errores = [], []
    for archivo in archivos:
        try:
            guardadas.append(presentacion.guardar_subida(archivo))
        except ValueError as e:
            errores.append(str(e))
    return JsonResponse({'status': 'success' if guardadas else 'error', 'guardadas': guardadas, 'errores': errores},
                        status=200 if guardadas else 400)


@require_POST
def presentacion_eliminar(request):
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        datos = {}
    try:
        seguridad.verificar(datos.get('clave'))
        presentacion.eliminar(datos.get('nombre'))
    except (seguridad.ClaveError, ValueError) as e:
        return _error(str(e))
    return JsonResponse({'status': 'success'})


@require_POST
def sistema_clave(request):
    """Crea o cambia la clave de administrador."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        datos = {}
    if datos.get('nueva') != datos.get('repetir'):
        return _error('La clave nueva y su repetición no coinciden.')
    try:
        seguridad.cambiar(datos.get('nueva'), actual=datos.get('actual'))
    except seguridad.ClaveError as e:
        return _error(str(e))
    return JsonResponse({'status': 'success'})


@require_POST
def borrar_ventas(request):
    """Elimina TODAS las ventas (pensado para limpiar las ventas de prueba antes de empezar a operar).
    Hace un respaldo antes y exige escribir BORRAR para confirmar."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        datos = {}
    if datos.get('confirmacion') != 'BORRAR':
        return _error('Para confirmar debes escribir BORRAR.')
    try:
        seguridad.verificar(datos.get('clave'))
    except seguridad.ClaveError as e:
        return _error(str(e))
    devolver_stock = bool(datos.get('devolver_stock', True))

    respaldo = None
    if settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
        try:
            respaldo = sistema.crear_respaldo('antes-de-borrar-ventas')
        except Exception:
            logger.exception('No se pudo respaldar antes de borrar ventas')
            return _error('No se pudo crear el respaldo previo, así que no se borró nada.')

    with transaction.atomic():
        if devolver_stock:
            # Las anuladas ya devolvieron su stock al anularse (o se decidió no devolverlo)
            vendidas = (DetalleVenta.objects.filter(venta__anulada=False)
                        .values('inventario_id').annotate(total=Sum('cantidad')))
            for fila in vendidas:
                Inventario.objects.filter(pk=fila['inventario_id']).update(cantidad=F('cantidad') + fila['total'])
        borradas = Venta.objects.count()
        DetalleVenta.objects.all().delete()
        Venta.objects.all().delete()

    return JsonResponse({'status': 'success', 'borradas': borradas, 'respaldo': respaldo.name if respaldo else None})


@require_GET
def sistema_salud(request):
    return JsonResponse({'ok': True, 'version': settings.APP_VERSION})


@require_GET
def sistema_buscar_actualizacion(request):
    try:
        return JsonResponse({'status': 'success', **sistema.buscar_actualizacion()})
    except Exception as e:
        logger.warning('No se pudo buscar actualizaciones', exc_info=True)
        return JsonResponse({'status': 'error', 'message': sistema.explicar_error(e)}, status=503)


@require_POST
def sistema_actualizar(request):
    try:
        info = sistema.descargar_e_instalar()
    except RuntimeError as e:
        return _error(str(e))
    except Exception as e:
        logger.exception('Falló la actualización')
        return JsonResponse({'status': 'error', 'message': sistema.explicar_error(e)}, status=503)
    return JsonResponse({'status': 'success', 'version': info['version']})


@require_POST
def sistema_respaldar(request):
    try:
        archivo = sistema.crear_respaldo('manual')
    except Exception as e:
        logger.exception('Falló el respaldo')
        return _error(f'No se pudo crear el respaldo: {e}')
    return JsonResponse({'status': 'success', 'archivo': archivo.name})


# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------

@requiere_admin
def dashboard_ventas(request):
    return render(request, 'dashboard.html')


def _inicio_del_dia(fecha):
    """Medianoche local de `fecha` como datetime con zona horaria."""
    return timezone.make_aware(datetime.combine(fecha, time.min))


@requiere_admin
def ventas_data(request):
    rango = request.GET.get('rango', 'dia')
    fecha_inicio = parse_date(request.GET.get('inicio') or '')
    fecha_fin = parse_date(request.GET.get('fin') or '')

    # Las ventas anuladas no cuentan en el análisis
    ventas_qs = Venta.objects.filter(anulada=False)
    detalles = DetalleVenta.objects.filter(venta__anulada=False)

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
        color=F('inventario__color__nombre'),
        talla=F('inventario__talla__nombre'),
        colegio=F('inventario__colegio__nombre')
    ).annotate(
        cantidad=Sum('cantidad'),
        total=Sum('subtotal')
    ).order_by('-cantidad')[:8]

    productos_list = [{
        'nombre': f"{p['nombre']} {p['color']}" if p['color'] else p['nombre'],
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


@requiere_admin
def historial_ventas_json(request):
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '').strip()

    detalles = DetalleVenta.objects.select_related(
        'venta', 'inventario__uniforme', 'inventario__talla', 'inventario__colegio'
    ).filter(venta__anulada=False)

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
    inventario_bajo = Inventario.objects.filter(cantidad__lt=umbral).select_related('uniforme', 'talla', 'colegio', 'color')

    productos = []
    for item in inventario_bajo:
        productos.append({
            'id': item.id,
            'nombre': item.nombre_completo,
            'talla': item.talla.nombre,
            'colegio': item.colegio.nombre,
            'stock': item.cantidad
        })

    return JsonResponse({'productos': productos})


@requiere_admin
def productos_tendencia(request):
    hoy = timezone.localdate()
    fin = _inicio_del_dia(hoy + timedelta(days=1))
    corte = _inicio_del_dia(hoy - timedelta(days=6))     # últimos 7 días (incluye hoy)
    inicio = _inicio_del_dia(hoy - timedelta(days=13))   # los 7 días anteriores

    def vendidos(desde, hasta):
        return DetalleVenta.objects.filter(
            venta__anulada=False, venta__fecha__gte=desde, venta__fecha__lt=hasta
        ).values(
            nombre=F('inventario__uniforme__nombre'),
            color=F('inventario__color__nombre'),
            talla=F('inventario__talla__nombre'),
            colegio=F('inventario__colegio__nombre')
        ).annotate(cantidad=Sum('cantidad'))

    anteriores = {(a['nombre'], a['color'], a['talla'], a['colegio']): a['cantidad'] for a in vendidos(inicio, corte)}

    tendencia = []
    for r in vendidos(corte, fin):
        crecimiento = r['cantidad'] - anteriores.get((r['nombre'], r['color'], r['talla'], r['colegio']), 0)
        if crecimiento > 0:
            tendencia.append({
                'nombre': f"{r['nombre']} {r['color']}" if r['color'] else r['nombre'],
                'talla': r['talla'],
                'colegio': r['colegio'],
                'crecimiento': crecimiento
            })

    tendencia = sorted(tendencia, key=lambda x: x['crecimiento'], reverse=True)[:5]

    return JsonResponse({'productos': tendencia})
