"""Egresos: lo que se gasta en el negocio (insumos, servicios, arriendo…) y los sueldos de los empleados."""
from decimal import Decimal

from django.db import models
from django.utils import timezone

from AppInventario.models import MONTO, Venta

METODOS_PAGO = Venta.METODOS_PAGO
NEGOCIOS = [('uniformes', 'Uniformes'), ('libreria', 'Librería'), ('general', 'General (ambos)')]


class CategoriaGasto(models.Model):
    nombre = models.CharField(max_length=60)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Gasto(models.Model):
    fecha = models.DateField(default=timezone.localdate)
    categoria = models.ForeignKey(CategoriaGasto, on_delete=models.PROTECT, related_name='gastos')
    descripcion = models.CharField(max_length=200)
    # Lo que se compró, si se quiere anotar: 5 metros, 100 unidades, 2 kilos…
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidad = models.CharField(max_length=20, blank=True)
    monto = models.DecimalField(**MONTO)
    proveedor = models.CharField(max_length=100, blank=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='efectivo')
    negocio = models.CharField(max_length=20, choices=NEGOCIOS, default='uniformes')
    documento = models.CharField('N° de boleta o factura', max_length=40, blank=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado']

    def __str__(self):
        return f'{self.descripcion} ({self.fecha:%d/%m/%Y})'

    @property
    def precio_unitario(self):
        """Cuánto costó cada metro/unidad, si se anotó la cantidad."""
        return (self.monto / self.cantidad) if self.cantidad else None


class Empleado(models.Model):
    TIPOS_PAGO = [('mensual', 'Sueldo mensual fijo'), ('hora', 'Por hora trabajada')]

    nombre = models.CharField(max_length=100)
    cargo = models.CharField(max_length=60, blank=True)
    tipo_pago = models.CharField(max_length=10, choices=TIPOS_PAGO, default='mensual')
    sueldo_mensual = models.DecimalField(default=0, **MONTO)
    valor_hora = models.DecimalField(default=0, **MONTO)
    telefono = models.CharField(max_length=30, blank=True)
    fecha_ingreso = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ['-activo', 'nombre']

    def __str__(self):
        return self.nombre

    def resumen_mes(self, anio, mes):
        """Horas, sueldo del mes, lo pagado y lo que falta por pagar (los bonos se suman aparte)."""
        horas = self.horas.filter(fecha__year=anio, fecha__month=mes).aggregate(t=models.Sum('horas'))['t'] or Decimal(0)
        pagos = self.pagos.filter(periodo=f'{anio:04d}-{mes:02d}')
        por_tipo = {t: Decimal(0) for t, _ in PagoEmpleado.TIPOS}
        for p in pagos:
            por_tipo[p.tipo] += p.monto
        sueldo = self.sueldo_mensual if self.tipo_pago == 'mensual' else (horas * self.valor_hora).quantize(Decimal(1))
        pagado_sueldo = por_tipo['sueldo'] + por_tipo['adelanto']
        return {
            'horas': horas, 'sueldo': sueldo, 'pagado_sueldo': pagado_sueldo,
            'adelantos': por_tipo['adelanto'], 'bonos': por_tipo['bono'], 'otros': por_tipo['otro'],
            'pagado_total': sum(por_tipo.values(), Decimal(0)),
            'pendiente': max(sueldo - pagado_sueldo, Decimal(0)),
        }


class RegistroHoras(models.Model):
    empleado = models.ForeignKey(Empleado, on_delete=models.CASCADE, related_name='horas')
    fecha = models.DateField(default=timezone.localdate)
    horas = models.DecimalField(max_digits=5, decimal_places=2)
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha']


class PagoEmpleado(models.Model):
    TIPOS = [('sueldo', 'Sueldo'), ('adelanto', 'Adelanto'), ('bono', 'Bono'), ('otro', 'Otro')]

    empleado = models.ForeignKey(Empleado, on_delete=models.PROTECT, related_name='pagos')
    fecha = models.DateField(default=timezone.localdate)
    periodo = models.CharField('Mes que se paga', max_length=7)   # 'AAAA-MM'
    tipo = models.CharField(max_length=10, choices=TIPOS, default='sueldo')
    monto = models.DecimalField(**MONTO)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='transferencia')
    nota = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ['-fecha', '-id']
