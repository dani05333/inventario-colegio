import calendar
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_POST
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from AppInventario import seguridad
from AppInventario.forms import normalizar_nombre
from AppInventario.views import EliminarProtegidoMixin, _error, requiere_admin

from . import disponibilidad as disp
from .forms import CategoriaForm, ClienteForm, PiezaForm, TrajeForm
from .models import METODOS_PAGO, Arriendo, ArriendoLinea, Categoria, Cliente, Pago, Pieza, Traje, TrajePieza

DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']


def _nombre_dia(d):
    return f'{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}'


def _resumen_lineas(arriendos):
    """'20 × Traje completo de diablada, 2 × Oso' sumando las líneas de varios arriendos."""
    total = defaultdict(int)
    for a in arriendos:
        for l in a.lineas.all():
            total[l.nombre] += l.cantidad
    return sorted(total.items(), key=lambda x: -x[1])


def _con_detalle():
    return Arriendo.objects.select_related('cliente').prefetch_related('lineas__traje', 'lineas__pieza', 'pagos')


# ---------------------------------------------------------------------------
# Agenda: avisos de lo que viene
# ---------------------------------------------------------------------------

def agenda(request):
    hoy = timezone.localdate()
    activos = _con_detalle().filter(estado__in=Arriendo.ACTIVOS)
    proximos = defaultdict(list)
    for a in activos.filter(estado='reservado', fecha_retiro__range=(hoy, hoy + timedelta(days=7))):
        proximos[a.fecha_retiro].append(a)
    retiros = [{'dia': d, 'nombre': _nombre_dia(d), 'hoy': d == hoy, 'manana': d == hoy + timedelta(days=1),
                'arriendos': lista, 'resumen': _resumen_lineas(lista)} for d, lista in sorted(proximos.items())]
    sobre = disp.sobre_reservas(hoy, hoy + timedelta(days=60))
    contexto = {
        'hoy': hoy,
        'retiros': retiros,
        'devoluciones': list(activos.filter(estado='entregado', fecha_devolucion__range=(hoy, hoy + timedelta(days=1)))),
        'atrasados': list(activos.filter(estado='entregado', fecha_devolucion__lt=hoy)),
        'no_retirados': list(activos.filter(estado='reservado', fecha_retiro__lt=hoy)),
        'sin_abono': [a for a in activos.filter(estado='reservado', fecha_retiro__lte=hoy + timedelta(days=7)) if not a.pagos.all()],
        'sobre': [{'dia': d, 'nombre': _nombre_dia(d), 'exceso': ex} for d, ex in sorted(sobre.items())],
        'en_uso_hoy': sum(a.unidades for a in activos.filter(estado='entregado')),
    }
    # Lo cobrado en arriendos se ve en Egresos → Resumen del mes (con la clave)
    return render(request, 'arriendos/agenda.html', contexto)


# ---------------------------------------------------------------------------
# Calendario del mes
# ---------------------------------------------------------------------------

def calendario(request):
    hoy = timezone.localdate()
    try:
        anio, mes = (int(x) for x in (request.GET.get('mes') or '').split('-'))
        date(anio, mes, 1)
    except (ValueError, TypeError):
        anio, mes = hoy.year, hoy.month
    semanas_cal = calendar.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    desde, hasta = semanas_cal[0][0], semanas_cal[-1][-1]
    uso, quienes = disp.uso_por_dia(desde, hasta)
    piezas = Pieza.objects.in_bulk()
    activos = list(_con_detalle().filter(estado__in=Arriendo.ACTIVOS).filter(Q(fecha_retiro__range=(desde, hasta)) | Q(fecha_devolucion__range=(desde, hasta))))
    semanas = []
    for semana in semanas_cal:
        fila = []
        for d in semana:
            exceso = [str(piezas[pid]) for pid, n in uso[d].items() if pid in piezas and n > piezas[pid].stock]
            fila.append({
                'dia': d, 'del_mes': d.month == mes, 'hoy': d == hoy,
                'retiros': [a for a in activos if a.fecha_retiro == d],
                'devoluciones': [a for a in activos if a.fecha_devolucion == d],
                'en_uso': sum(a.unidades for a in quienes[d]),
                'exceso': exceso,
            })
        semanas.append(fila)
    dia = parse_date(request.GET.get('dia') or '') or (hoy if (hoy.year, hoy.month) == (anio, mes) else None)
    detalle = None
    if dia:
        _, q = disp.uso_por_dia(dia, dia)
        detalle = {'dia': dia, 'nombre': _nombre_dia(dia), 'arriendos': q[dia], 'disp': disp.resumen_trajes(dia, dia)}
    pa, pm = (anio, mes - 1) if mes > 1 else (anio - 1, 12)
    sa, sm = (anio, mes + 1) if mes < 12 else (anio + 1, 1)
    return render(request, 'arriendos/calendario.html', {
        'semanas': semanas, 'dias_semana': [d[:3] for d in DIAS], 'nombre_mes': f'{MESES[mes - 1].capitalize()} {anio}',
        'mes_param': f'{anio:04d}-{mes:02d}', 'mes_anterior': f'{pa:04d}-{pm:02d}', 'mes_siguiente': f'{sa:04d}-{sm:02d}',
        'detalle': detalle, 'es_mes_actual': (anio, mes) == (hoy.year, hoy.month),
    })


# ---------------------------------------------------------------------------
# Disponibilidad para un rango de fechas
# ---------------------------------------------------------------------------

def _rango(request):
    hoy = timezone.localdate()
    desde = parse_date(request.GET.get('desde') or '') or hoy
    hasta = parse_date(request.GET.get('hasta') or '') or desde
    return (desde, hasta) if desde <= hasta else (hasta, desde)


def disponibilidad(request):
    desde, hasta = _rango(request)
    return render(request, 'arriendos/disponibilidad.html', {'desde': desde, 'hasta': hasta, 'disp': disp.resumen_trajes(desde, hasta)})


@require_GET
def api_disponibilidad(request):
    desde, hasta = _rango(request)
    excluir = request.GET.get('excluir')
    return JsonResponse(disp.resumen_trajes(desde, hasta, int(excluir) if excluir and excluir.isdigit() else None))


# ---------------------------------------------------------------------------
# Arriendos
# ---------------------------------------------------------------------------

FILTROS = [('activos', 'Activos'), ('reservado', 'Por retirar'), ('entregado', 'Entregados'), ('atrasados', 'Atrasados'),
           ('devuelto', 'Devueltos'), ('cancelado', 'Cancelados'), ('todos', 'Todos')]


def lista(request):
    filtro = request.GET.get('estado') or 'activos'
    q = (request.GET.get('q') or '').strip()
    arriendos = _con_detalle()
    if filtro == 'activos':
        arriendos = arriendos.filter(estado__in=Arriendo.ACTIVOS)
    elif filtro == 'atrasados':
        arriendos = arriendos.filter(estado='entregado', fecha_devolucion__lt=timezone.localdate())
    elif filtro in dict(Arriendo.ESTADOS):
        arriendos = arriendos.filter(estado=filtro)
    if q:
        arriendos = arriendos.filter(Q(cliente__nombre__icontains=q) | Q(evento__icontains=q) | Q(cliente__contacto__icontains=q))
    if filtro in ('devuelto', 'cancelado', 'todos'):
        arriendos = arriendos.order_by('-fecha_retiro', '-id')[:300]
    return render(request, 'arriendos/lista.html', {'arriendos': arriendos, 'filtro': filtro, 'filtros': FILTROS, 'q': q})


def _arriendo_dict(a):
    return {
        'id': a.id, 'folio': a.folio, 'estado': a.estado, 'cliente_id': a.cliente_id, 'cliente': str(a.cliente),
        'evento': a.evento, 'fecha_retiro': a.fecha_retiro.isoformat(), 'fecha_devolucion': a.fecha_devolucion.isoformat(),
        'garantia': int(a.garantia), 'notas': a.notas,
        'lineas': [{'traje_id': l.traje_id, 'pieza_id': l.pieza_id, 'nombre': l.nombre, 'cantidad': l.cantidad,
                    'precio': int(l.precio_unitario)} for l in a.lineas.all()],
    }


def arriendo_form(request, pk=None):
    arriendo = get_object_or_404(_con_detalle(), pk=pk) if pk else None
    if arriendo and arriendo.estado != 'reservado':
        return redirect('arriendos:detalle', pk=arriendo.pk)
    inicial = None
    if not arriendo and request.GET.get('fecha'):
        inicial = {'fecha_retiro': request.GET['fecha'], 'fecha_devolucion': request.GET['fecha']}
    return render(request, 'arriendos/arriendo_form.html', {
        'arriendo': arriendo, 'arriendo_data': _arriendo_dict(arriendo) if arriendo else inicial,
        'clientes': list(Cliente.objects.values('id', 'nombre', 'tipo', 'telefono')),
        'tipos_cliente': Cliente.TIPOS, 'metodos_pago': METODOS_PAGO,
    })


def _entero(valor, que):
    try:
        n = int(str(valor if valor is not None else '').strip() or 0)
    except ValueError:
        raise ValueError(f'Revisa {que}.')
    if n < 0:
        raise ValueError(f'{que.capitalize()} no puede ser menor que 0.')
    return n


@require_POST
def api_guardar(request):
    """Crea o modifica una reserva. No deja reservar más trajes de los que hay libres en esas fechas."""
    try:
        datos = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return _error('Datos no válidos.')
    arriendo = None
    if datos.get('id'):
        arriendo = Arriendo.objects.filter(pk=datos['id']).first()
        if not arriendo or arriendo.estado != 'reservado':
            return _error('Solo se puede modificar un arriendo que aún no se ha entregado.')
    retiro, devolucion = parse_date(datos.get('fecha_retiro') or ''), parse_date(datos.get('fecha_devolucion') or '')
    if not retiro or not devolucion:
        return _error('Indica la fecha de retiro y la de devolución.')
    if devolucion < retiro:
        return _error('La devolución no puede ser antes del retiro.')
    try:
        lineas = []
        for fila in datos.get('lineas') or []:
            cantidad = _entero(fila.get('cantidad'), 'la cantidad')
            if not cantidad:
                continue
            traje = Traje.objects.prefetch_related('componentes').filter(pk=fila.get('traje_id')).first() if fila.get('traje_id') else None
            pieza = Pieza.objects.filter(pk=fila.get('pieza_id')).first() if not traje and fila.get('pieza_id') else None
            if not traje and not pieza:
                raise ValueError('Uno de los trajes ya no existe. Recarga la página.')
            if traje and not traje.componentes.exists():
                raise ValueError(f'El traje «{traje}» no tiene piezas asignadas: complétalo en Inventario de trajes.')
            precio = _entero(fila.get('precio', (traje or pieza).precio), 'el precio')
            lineas.append((traje, pieza, cantidad, precio))
        if not lineas:
            raise ValueError('Agrega al menos un traje o pieza.')
        garantia = _entero(datos.get('garantia'), 'la garantía')
        abono = _entero((datos.get('abono') or {}).get('monto'), 'el abono')
    except ValueError as e:
        return _error(str(e))

    with transaction.atomic():
        faltan = disp.problemas([(t, p, c) for t, p, c, _ in lineas], retiro, devolucion, excluir=arriendo.pk if arriendo else None)
        if faltan:
            return JsonResponse({'status': 'error', 'message': 'No alcanzan los trajes para esas fechas.', 'problemas': faltan}, status=400)
        if datos.get('cliente_id'):
            cliente = Cliente.objects.filter(pk=datos['cliente_id']).first()
            if not cliente:
                return _error('El cliente ya no existe. Recarga la página.')
        else:
            nuevo = datos.get('cliente_nuevo') or {}
            nombre = normalizar_nombre(nuevo.get('nombre'))
            if not nombre:
                return _error('Elige un cliente o escribe el nombre del nuevo.')
            cliente = Cliente.objects.create(
                nombre=nombre, tipo=nuevo.get('tipo') if nuevo.get('tipo') in dict(Cliente.TIPOS) else 'persona',
                contacto=normalizar_nombre(nuevo.get('contacto')), telefono=(nuevo.get('telefono') or '').strip()[:40])
        if arriendo is None:
            arriendo = Arriendo(estado='reservado')
        arriendo.cliente = cliente
        arriendo.evento = normalizar_nombre(datos.get('evento'))[:150]
        arriendo.fecha_retiro, arriendo.fecha_devolucion = retiro, devolucion
        arriendo.garantia = garantia
        arriendo.notas = (datos.get('notas') or '').strip()
        arriendo.total = sum(c * p for _, _, c, p in lineas)
        arriendo.save()
        arriendo.lineas.all().delete()
        for traje, pieza, cantidad, precio in lineas:
            ArriendoLinea.objects.create(arriendo=arriendo, traje=traje, pieza=pieza, cantidad=cantidad, precio_unitario=precio, subtotal=cantidad * precio)
        if abono:
            metodo = (datos.get('abono') or {}).get('metodo')
            Pago.objects.create(arriendo=arriendo, monto=abono, tipo='abono', metodo_pago=metodo if metodo in dict(METODOS_PAGO) else 'efectivo')
    return JsonResponse({'status': 'success', 'id': arriendo.pk, 'url': reverse('arriendos:detalle', args=[arriendo.pk])})


def detalle(request, pk):
    a = get_object_or_404(_con_detalle(), pk=pk)
    return render(request, 'arriendos/detalle.html', {'a': a, 'metodos_pago': METODOS_PAGO, 'hoy': timezone.localdate()})


@require_POST
def api_accion(request, pk):
    """entregar · devolver · cancelar · pago (cada una puede incluir un pago)."""
    try:
        datos = json.loads(request.body or '{}')
        monto = _entero((datos.get('pago') or {}).get('monto'), 'el monto')
        cargo = _entero(datos.get('cargo_extra'), 'el cargo') if datos.get('accion') == 'devolver' else 0
    except (json.JSONDecodeError, ValueError) as e:
        return _error(str(e) if isinstance(e, ValueError) else 'Datos no válidos.')
    accion = datos.get('accion')
    with transaction.atomic():
        a = get_object_or_404(Arriendo.objects.select_for_update(), pk=pk)
        if accion == 'entregar':
            if a.estado != 'reservado':
                return _error('Este arriendo ya no está por retirar.')
            a.estado, a.entregado_en = 'entregado', timezone.now()
        elif accion == 'devolver':
            if a.estado != 'entregado':
                return _error('Solo se recibe de vuelta un arriendo entregado.')
            a.estado, a.devuelto_en = 'devuelto', timezone.now()
            a.faltantes = (datos.get('faltantes') or '').strip()
            a.cargo_extra = cargo
            a.garantia_devuelta = bool(datos.get('garantia_devuelta'))
        elif accion == 'cancelar':
            if a.estado != 'reservado':
                return _error('Solo se puede cancelar una reserva que no se ha entregado.')
            a.estado = 'cancelado'
            a.notas = (a.notas + '\n' if a.notas else '') + f'Cancelado el {timezone.localdate():%d/%m/%Y}. ' + (datos.get('motivo') or '').strip()
        elif accion != 'pago':
            return _error('Acción no válida.')
        a.save()
        if monto:
            metodo = (datos.get('pago') or {}).get('metodo')
            tipo = (datos.get('pago') or {}).get('tipo')
            Pago.objects.create(arriendo=a, monto=monto, metodo_pago=metodo if metodo in dict(METODOS_PAGO) else 'efectivo',
                                tipo=tipo if tipo in dict(Pago.TIPOS) else ('cargo' if accion == 'devolver' and cargo else 'saldo'))
        elif accion == 'pago':
            return _error('Indica el monto del pago.')
    return JsonResponse({'status': 'success'})


# ---------------------------------------------------------------------------
# Clientes
# ---------------------------------------------------------------------------

def clientes(request):
    lista = []
    for c in Cliente.objects.prefetch_related('arriendos'):
        arr = [a for a in c.arriendos.all() if a.estado != 'cancelado']
        lista.append({'c': c, 'arriendos': len(arr), 'ultimo': max((a.fecha_retiro for a in arr), default=None),
                      'activos': sum(1 for a in arr if a.estado in Arriendo.ACTIVOS)})
    lista.sort(key=lambda x: x['ultimo'] or date.min, reverse=True)
    return render(request, 'arriendos/clientes.html', {'clientes': lista})


def cliente(request, pk):
    c = get_object_or_404(Cliente, pk=pk)
    arriendos = _con_detalle().filter(cliente=c).order_by('-fecha_retiro')
    return render(request, 'arriendos/cliente.html', {'c': c, 'arriendos': arriendos})


def cliente_form(request, pk=None):
    c = get_object_or_404(Cliente, pk=pk) if pk else None
    form = ClienteForm(request.POST or None, instance=c)
    if request.method == 'POST' and form.is_valid():
        c = form.save()
        return redirect('arriendos:cliente', pk=c.pk)
    return render(request, 'arriendos/cliente_form.html', {'form': form, 'c': c})


# ---------------------------------------------------------------------------
# Inventario de trajes y piezas (con clave)
# ---------------------------------------------------------------------------

@requiere_admin
def inventario(request):
    hoy = timezone.localdate()
    libres = disp.disponibles(hoy, hoy)
    piezas = list(Pieza.objects.select_related('categoria'))
    for p in piezas:
        p.libres_hoy = libres.get(p.id, p.stock)
    trajes = list(Traje.objects.select_related('categoria').prefetch_related('componentes__pieza'))
    for t in trajes:
        t.libres_hoy = disp.traje_disponible(t, libres)
    return render(request, 'arriendos/inventario.html', {'piezas': piezas, 'trajes': trajes, 'hoy': hoy})


@requiere_admin
def pieza_form(request, pk=None):
    pieza = get_object_or_404(Pieza, pk=pk) if pk else None
    form = PiezaForm(request.POST or None, instance=pieza)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect(f"{reverse('arriendos:inventario')}#piezas")
    return render(request, 'arriendos/pieza_form.html', {'form': form, 'pieza': pieza})


@requiere_admin
def traje_form(request, pk=None):
    traje = get_object_or_404(Traje, pk=pk) if pk else None
    form = TrajeForm(request.POST or None, instance=traje)
    error = None
    componentes = [(c.pieza_id, c.cantidad) for c in traje.componentes.all()] if traje else []
    if request.method == 'POST':
        ids, cants = request.POST.getlist('pieza_id'), request.POST.getlist('pieza_cantidad')
        componentes = []
        for pid, cant in zip(ids, cants):
            if pid.isdigit() and cant.isdigit() and int(cant) > 0:
                componentes.append((int(pid), int(cant)))
        if not componentes:
            error = 'Agrega al menos una pieza: el traje completo se arma con piezas del inventario.'
        elif len({pid for pid, _ in componentes}) != len(componentes):
            error = 'Hay una pieza repetida en la lista.'
        if form.is_valid() and not error:
            with transaction.atomic():
                traje = form.save()
                traje.componentes.all().delete()
                for pid, cant in componentes:
                    TrajePieza.objects.create(traje=traje, pieza_id=pid, cantidad=cant)
            return redirect(f"{reverse('arriendos:inventario')}#trajes")
    return render(request, 'arriendos/traje_form.html', {
        'form': form, 'traje': traje, 'error': error, 'componentes': componentes,
        'piezas': list(Pieza.objects.select_related('categoria')),
    })


@require_POST
@requiere_admin
def api_eliminar(request, tipo, pk):
    """Borra una pieza o un traje; si ya se arrendó (o la pieza es parte de un traje), lo deja de arrendar."""
    modelo = {'pieza': Pieza, 'traje': Traje}.get(tipo)
    if not modelo:
        return _error('No válido.')
    obj = get_object_or_404(modelo, pk=pk)
    try:
        obj.delete()
        return JsonResponse({'status': 'success', 'accion': 'eliminado'})
    except ProtectedError:
        obj.activo = False
        obj.save(update_fields=['activo'])
        return JsonResponse({'status': 'success', 'accion': 'desactivado'})


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

def categorias(request):
    return render(request, 'arriendos/categorias.html')


def categorias_json(request):
    return JsonResponse({'data': list(Categoria.objects.values('id', 'nombre'))})


class CategoriaCreateView(CreateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'arriendos/categoria_form.html'
    success_url = reverse_lazy('arriendos:categorias')


class CategoriaUpdateView(UpdateView):
    model = Categoria
    form_class = CategoriaForm
    template_name = 'arriendos/categoria_form.html'
    success_url = reverse_lazy('arriendos:categorias')


class CategoriaDeleteView(EliminarProtegidoMixin, DeleteView):
    model = Categoria
    success_url = reverse_lazy('arriendos:categorias')
