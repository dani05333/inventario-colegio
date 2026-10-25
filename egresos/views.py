"""Egresos (toda la sección pide la clave de administrador): gastos del negocio, sueldos y el resumen del mes."""
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from AppInventario.models import Venta as VentaUniformes
from AppInventario.views import EliminarProtegidoMixin, requiere_admin
from arriendos.models import Pago as PagoArriendo
from libreria.models import Venta as VentaLibreria

from .forms import CategoriaGastoForm, EmpleadoForm, GastoForm, PagoEmpleadoForm, ProveedorForm, RegistroHorasForm
from .models import NEGOCIOS, CategoriaGasto, Empleado, Gasto, PagoEmpleado, Proveedor, RegistroHoras

MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
# Para decir «$5.000 por metro» (y no «por metros»)
SINGULAR = {'unidades': 'unidad', 'metros': 'metro', 'centímetros': 'centímetro', 'kilos': 'kilo', 'gramos': 'gramo', 'rollos': 'rollo',
            'conos': 'cono', 'paquetes': 'paquete', 'cajas': 'caja', 'docenas': 'docena', 'litros': 'litro'}
UNIDADES = ['unidades', 'metros', 'centímetros', 'kilos', 'gramos', 'rollos', 'conos', 'paquetes', 'cajas', 'docenas', 'litros']


# ---------------------------------------------------------------------------
# Meses
# ---------------------------------------------------------------------------

def _mes(request):
    """(año, mes) de ?mes=AAAA-MM; si no viene o no es válido, el mes actual."""
    try:
        anio, mes = (int(x) for x in (request.GET.get('mes') or '').split('-'))
        date(anio, mes, 1)
        return anio, mes
    except (ValueError, TypeError):
        hoy = timezone.localdate()
        return hoy.year, hoy.month


def _mover(anio, mes, n):
    total = anio * 12 + (mes - 1) + n
    return total // 12, total % 12 + 1


def _nombre_mes(anio, mes):
    return f'{MESES[mes - 1].capitalize()} {anio}'


def _contexto_mes(anio, mes):
    pa, pm = _mover(anio, mes, -1)
    sa, sm = _mover(anio, mes, 1)
    hoy = timezone.localdate()
    return {
        'anio': anio, 'mes': mes, 'mes_param': f'{anio:04d}-{mes:02d}', 'nombre_mes': _nombre_mes(anio, mes),
        'mes_anterior': f'{pa:04d}-{pm:02d}', 'mes_siguiente': f'{sa:04d}-{sm:02d}',
        'es_mes_actual': (anio, mes) == (hoy.year, hoy.month),
    }


def _ventas_mes(anio, mes):
    """Lo vendido en el mes: uniformes y librería (sin las ventas anuladas) y lo cobrado en arriendos de trajes."""
    inicio = timezone.make_aware(datetime.combine(date(anio, mes, 1), time.min))
    fa, fm = _mover(anio, mes, 1)
    fin = timezone.make_aware(datetime.combine(date(fa, fm, 1), time.min))
    totales = {}
    for clave, modelo in (('uniformes', VentaUniformes), ('libreria', VentaLibreria)):
        totales[clave] = modelo.objects.filter(fecha__gte=inicio, fecha__lt=fin, anulada=False).aggregate(t=Sum('total'))['t'] or Decimal(0)
    totales['arriendos'] = PagoArriendo.objects.filter(fecha__year=anio, fecha__month=mes).aggregate(t=Sum('monto'))['t'] or Decimal(0)
    totales['total'] = totales['uniformes'] + totales['libreria'] + totales['arriendos']
    return totales


def _egresos_mes(anio, mes):
    gastos = Gasto.objects.filter(fecha__year=anio, fecha__month=mes).aggregate(t=Sum('monto'))['t'] or Decimal(0)
    sueldos = PagoEmpleado.objects.filter(fecha__year=anio, fecha__month=mes).aggregate(t=Sum('monto'))['t'] or Decimal(0)
    return gastos, sueldos


def _variacion(actual, anterior):
    if not anterior:
        return None
    return round((actual - anterior) / anterior * 100)


# ---------------------------------------------------------------------------
# Resumen del mes
# ---------------------------------------------------------------------------

@requiere_admin
def resumen(request):
    anio, mes = _mes(request)
    gastos, sueldos = _egresos_mes(anio, mes)
    egresos = gastos + sueldos
    pa, pm = _mover(anio, mes, -1)
    g_ant, s_ant = _egresos_mes(pa, pm)
    ventas = _ventas_mes(anio, mes)
    vendido = ventas['total']

    por_categoria = list(Gasto.objects.filter(fecha__year=anio, fecha__month=mes)
                         .values('categoria__nombre').annotate(total=Sum('monto')).order_by('-total'))
    for c in por_categoria:
        c['pct'] = round(c['total'] / gastos * 100) if gastos else 0
    nombres_negocio = dict(NEGOCIOS)
    por_negocio = [{'nombre': nombres_negocio[n['negocio']], 'total': n['total']}
                   for n in Gasto.objects.filter(fecha__year=anio, fecha__month=mes).values('negocio').annotate(total=Sum('monto')).order_by('-total')]

    # Últimos 12 meses para el gráfico
    serie = []
    for i in range(11, -1, -1):
        a, m = _mover(anio, mes, -i)
        g, s = _egresos_mes(a, m)
        v = _ventas_mes(a, m)
        serie.append({'mes': f'{MESES[m - 1][:3].capitalize()} {str(a)[2:]}', 'gastos': float(g), 'sueldos': float(s),
                      'ventas': float(v['total'])})

    pendientes = []
    for e in Empleado.objects.filter(activo=True):
        r = e.resumen_mes(anio, mes)
        if r['pendiente'] > 0:
            pendientes.append({'empleado': e, **r})

    return render(request, 'egresos/resumen.html', {
        **_contexto_mes(anio, mes),
        'gastos': gastos, 'sueldos': sueldos, 'egresos': egresos,
        'var_egresos': _variacion(egresos, g_ant + s_ant), 'egresos_anterior': g_ant + s_ant,
        'ventas': ventas, 'vendido': vendido, 'resultado': vendido - egresos,
        'por_categoria': por_categoria, 'por_negocio': por_negocio, 'serie': serie,
        'recientes': Gasto.objects.select_related('categoria').filter(fecha__year=anio, fecha__month=mes)[:8],
        'pendientes': pendientes,
    })


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

@requiere_admin
def gastos(request):
    anio, mes = _mes(request)
    if request.method == 'POST':
        form = GastoForm(request.POST)
        if form.is_valid():
            gasto = form.save()
            destino = f"{reverse('egresos:gastos')}?mes={gasto.fecha:%Y-%m}&nuevo={gasto.pk}"
            return redirect(destino)
    else:
        ultimo = Gasto.objects.order_by('-creado').first()   # se recuerda la forma de pago y el negocio del último gasto
        form = GastoForm(initial={'fecha': timezone.localdate(), 'metodo_pago': ultimo.metodo_pago if ultimo else 'efectivo',
                                  'negocio': ultimo.negocio if ultimo else 'uniformes',
                                  'proveedor': request.GET.get('proveedor', '')})   # «Anotar compra» desde la ficha del proveedor
    lista = Gasto.objects.select_related('categoria', 'proveedor').filter(fecha__year=anio, fecha__month=mes)
    categoria = request.GET.get('categoria') or ''
    if categoria.isdigit():
        lista = lista.filter(categoria_id=int(categoria))
    negocio = request.GET.get('negocio') or ''
    if negocio in dict(NEGOCIOS):
        lista = lista.filter(negocio=negocio)
    return render(request, 'egresos/gastos.html', {
        **_contexto_mes(anio, mes),
        'form': form, 'gastos': lista, 'total': lista.aggregate(t=Sum('monto'))['t'] or 0,
        'categorias': CategoriaGasto.objects.all(), 'negocios': NEGOCIOS,
        'f_categoria': categoria, 'f_negocio': negocio, 'unidades': UNIDADES,
        'proveedores': list(Proveedor.objects.values_list('nombre', flat=True)),
        'nuevo': request.GET.get('nuevo'),
    })


@requiere_admin
def gasto_editar(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)
    form = GastoForm(request.POST or None, instance=gasto)
    if request.method == 'POST' and form.is_valid():
        gasto = form.save()
        return redirect(f"{reverse('egresos:gastos')}?mes={gasto.fecha:%Y-%m}")
    return render(request, 'egresos/gasto_form.html', {
        'form': form, 'gasto': gasto, 'unidades': UNIDADES,
        'proveedores': list(Proveedor.objects.values_list('nombre', flat=True)),
    })


@require_POST
@requiere_admin
def gasto_eliminar(request, pk):
    get_object_or_404(Gasto, pk=pk).delete()
    return JsonResponse({'status': 'success'})


# ---------------------------------------------------------------------------
# Proveedores: ficha e historial de compras
# ---------------------------------------------------------------------------

@requiere_admin
def proveedores(request):
    anio = timezone.localdate().year
    lista = []
    for p in Proveedor.objects.all():
        compras = p.gastos.all()
        ultima = compras.order_by('-fecha').first()
        lista.append({
            'p': p, 'ultima': ultima, 'compras': compras.count(),
            'total_anio': compras.filter(fecha__year=anio).aggregate(t=Sum('monto'))['t'] or 0,
        })
    lista.sort(key=lambda x: (x['ultima'].fecha if x['ultima'] else date.min), reverse=True)   # los más recientes primero
    return render(request, 'egresos/proveedores.html', {'proveedores': lista, 'anio': anio})


def _lo_que_se_compra(gastos):
    """Agrupa las compras por lo que se compró: veces, última vez, cantidad habitual y último precio por unidad."""
    grupos = {}
    for g in sorted(gastos, key=lambda g: (g.fecha, g.creado)):   # de la más antigua a la más reciente
        clave = g.descripcion.casefold()
        x = grupos.setdefault(clave, {'descripcion': g.descripcion, 'veces': 0, 'total': Decimal(0), 'cantidades': [],
                                      'unidad': '', 'ultima': None, 'ultimo_monto': None, 'ultimo_unitario': None})
        x['veces'] += 1
        x['total'] += g.monto
        x['ultima'], x['ultimo_monto'] = g.fecha, g.monto
        x['descripcion'] = g.descripcion
        if g.cantidad:
            x['cantidades'].append(g.cantidad)
            x['unidad'] = g.unidad or x['unidad']
            x['ultimo_unitario'] = g.precio_unitario
    for x in grupos.values():
        x['cantidad_habitual'] = (sum(x['cantidades']) / len(x['cantidades'])) if x['cantidades'] else None
        x['por'] = SINGULAR.get(x['unidad'].strip().lower(), x['unidad']) or 'unidad'
    return sorted(grupos.values(), key=lambda x: (x['veces'], x['ultima']), reverse=True)


@requiere_admin
def proveedor(request, pk):
    prov = get_object_or_404(Proveedor, pk=pk)
    gastos = list(prov.gastos.select_related('categoria').order_by('-fecha', '-creado'))
    hoy = timezone.localdate()
    meses = []
    for i in range(11, -1, -1):
        a, m = _mover(hoy.year, hoy.month, -i)
        total = sum((g.monto for g in gastos if g.fecha.year == a and g.fecha.month == m), Decimal(0))
        meses.append({'mes': f'{MESES[m - 1][:3].capitalize()} {str(a)[2:]}', 'total': total})
    maximo = max((x['total'] for x in meses), default=0) or 1
    for x in meses:
        x['pct'] = round(x['total'] / maximo * 100)
    return render(request, 'egresos/proveedor.html', {
        'prov': prov, 'gastos': gastos, 'frecuentes': _lo_que_se_compra(gastos), 'meses': meses,
        'total': sum((g.monto for g in gastos), Decimal(0)),
        'total_anio': sum((g.monto for g in gastos if g.fecha.year == hoy.year), Decimal(0)),
        'primera': gastos[-1].fecha if gastos else None, 'ultima': gastos[0].fecha if gastos else None,
    })


@requiere_admin
def proveedor_form(request, pk=None):
    prov = get_object_or_404(Proveedor, pk=pk) if pk else None
    form = ProveedorForm(request.POST or None, instance=prov)
    if request.method == 'POST' and form.is_valid():
        prov = form.save()
        return redirect('egresos:proveedor', pk=prov.pk)
    return render(request, 'egresos/proveedor_form.html', {'form': form, 'prov': prov})


@require_POST
@requiere_admin
def proveedor_eliminar(request, pk):
    """Borra la ficha; sus gastos quedan, pero sin proveedor."""
    get_object_or_404(Proveedor, pk=pk).delete()
    return JsonResponse({'status': 'success'})


# ---------------------------------------------------------------------------
# Empleados: horas y pagos
# ---------------------------------------------------------------------------

@requiere_admin
def empleados(request):
    anio, mes = _mes(request)
    lista = [{'empleado': e, **e.resumen_mes(anio, mes)} for e in Empleado.objects.all()]
    activos = [x for x in lista if x['empleado'].activo]
    return render(request, 'egresos/empleados.html', {
        **_contexto_mes(anio, mes), 'empleados': lista,
        'total_sueldos': sum((x['sueldo'] for x in activos), Decimal(0)),
        'total_pagado': sum((x['pagado_total'] for x in activos), Decimal(0)),
        'total_pendiente': sum((x['pendiente'] for x in activos), Decimal(0)),
    })


@requiere_admin
def empleado_form(request, pk=None):
    empleado = get_object_or_404(Empleado, pk=pk) if pk else None
    form = EmpleadoForm(request.POST or None, instance=empleado)
    if request.method == 'POST' and form.is_valid():
        empleado = form.save()
        return redirect('egresos:empleado', pk=empleado.pk)
    return render(request, 'egresos/empleado_form.html', {'form': form, 'empleado': empleado})


@requiere_admin
def empleado(request, pk):
    emp = get_object_or_404(Empleado, pk=pk)
    anio, mes = _mes(request)
    periodo = f'{anio:04d}-{mes:02d}'
    form_horas = RegistroHorasForm(initial={'fecha': timezone.localdate()})
    form_pago = PagoEmpleadoForm(initial={'fecha': timezone.localdate(), 'periodo': periodo})
    if request.method == 'POST':
        if request.POST.get('accion') == 'horas':
            form_horas = RegistroHorasForm(request.POST)
            if form_horas.is_valid():
                r = form_horas.save(commit=False)
                r.empleado = emp
                r.save()
                return redirect(f"{reverse('egresos:empleado', args=[emp.pk])}?mes={r.fecha:%Y-%m}#horas")
        else:
            form_pago = PagoEmpleadoForm(request.POST)
            if form_pago.is_valid():
                p = form_pago.save(commit=False)
                p.empleado = emp
                p.save()
                return redirect(f"{reverse('egresos:empleado', args=[emp.pk])}?mes={p.periodo}#pagos")
    resumen_mes = emp.resumen_mes(anio, mes)
    if resumen_mes['pendiente'] and not request.method == 'POST':
        form_pago.initial['monto'] = int(resumen_mes['pendiente'])
    return render(request, 'egresos/empleado.html', {
        **_contexto_mes(anio, mes), 'emp': emp, 'r': resumen_mes,
        'horas': emp.horas.filter(fecha__year=anio, fecha__month=mes),
        'pagos': emp.pagos.filter(periodo=periodo),
        'form_horas': form_horas, 'form_pago': form_pago,
    })


@require_POST
@requiere_admin
def horas_eliminar(request, pk):
    get_object_or_404(RegistroHoras, pk=pk).delete()
    return JsonResponse({'status': 'success'})


@require_POST
@requiere_admin
def pago_eliminar(request, pk):
    get_object_or_404(PagoEmpleado, pk=pk).delete()
    return JsonResponse({'status': 'success'})


# ---------------------------------------------------------------------------
# Categorías de gasto
# ---------------------------------------------------------------------------

@requiere_admin
def categorias(request):
    return render(request, 'egresos/categorias.html')


@requiere_admin
def categorias_json(request):
    return JsonResponse({'data': list(CategoriaGasto.objects.values('id', 'nombre'))})


@method_decorator(requiere_admin, name='dispatch')
class CategoriaCreateView(CreateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = 'egresos/categoria_form.html'
    success_url = reverse_lazy('egresos:categorias')


@method_decorator(requiere_admin, name='dispatch')
class CategoriaUpdateView(UpdateView):
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = 'egresos/categoria_form.html'
    success_url = reverse_lazy('egresos:categorias')


@method_decorator(requiere_admin, name='dispatch')
class CategoriaDeleteView(EliminarProtegidoMixin, DeleteView):
    model = CategoriaGasto
    success_url = reverse_lazy('egresos:categorias')
    ayuda_bloqueo = 'Primero cambia de categoría esos gastos (o déjala, no molesta).'
