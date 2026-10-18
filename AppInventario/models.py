from django.core.validators import MinValueValidator
from django.db import models

# Montos en pesos, sin decimales. Mismo tipo en todos los modelos para no mezclar enteros y decimales.
MONTO = dict(max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])


class Colegio(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Talla(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Uniforme(models.Model):
    nombre = models.CharField(max_length=100)


    def __str__(self):
        return self.nombre

class Inventario(models.Model):
    codigo_barras = models.CharField(max_length=50, unique=True)
    cantidad = models.PositiveIntegerField()
    # PROTECT: no se puede borrar un colegio/talla/uniforme que tenga productos asociados
    colegio = models.ForeignKey(Colegio, on_delete=models.PROTECT)
    talla = models.ForeignKey(Talla, on_delete=models.PROTECT)
    uniforme = models.ForeignKey(Uniforme, on_delete=models.PROTECT)
    precio = models.DecimalField(default=0, **MONTO)

    def __str__(self):
        return f"{self.uniforme} - {self.talla} - {self.colegio}"

    @property
    def precio_total(self):
        return self.cantidad * self.precio

class Venta(models.Model):
    METODOS_PAGO = [
        ('efectivo', 'Efectivo'),
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
        ('transferencia', 'Transferencia'),
    ]

    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(**MONTO)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='efectivo')
    # Una venta anulada queda registrada (con su motivo) pero no cuenta en totales ni análisis
    anulada = models.BooleanField(default=False)
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=200, blank=True)

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    # PROTECT: un producto con ventas no se puede borrar, así el historial queda completo
    inventario = models.ForeignKey(Inventario, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(**MONTO)
    subtotal = models.DecimalField(default=0, **MONTO)
