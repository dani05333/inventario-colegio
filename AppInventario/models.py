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


class Color(models.Model):
    nombre = models.CharField(max_length=60)

    def __str__(self):
        return self.nombre

class Inventario(models.Model):
    codigo_barras = models.CharField(max_length=50, unique=True)
    cantidad = models.PositiveIntegerField()
    # PROTECT: no se puede borrar un colegio/talla/uniforme que tenga productos asociados
    colegio = models.ForeignKey(Colegio, on_delete=models.PROTECT)
    talla = models.ForeignKey(Talla, on_delete=models.PROTECT)
    uniforme = models.ForeignKey(Uniforme, on_delete=models.PROTECT)
    # Opcional: el mismo uniforme en distintos colores es un producto distinto (con su propio stock)
    color = models.ForeignKey(Color, on_delete=models.PROTECT, null=True, blank=True)
    precio = models.DecimalField(default=0, **MONTO)

    @property
    def nombre_completo(self):
        """'Polerón Azul' o 'Polerón' si no tiene color."""
        return f"{self.uniforme} {self.color}" if self.color_id else str(self.uniforme)

    def __str__(self):
        return f"{self.nombre_completo} - {self.talla} - {self.colegio}"

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
    # Conjuntos armados en la venta, para mostrarlos en la boleta como un ítem con su precio:
    # [{"nombre", "talla", "precio", "piezas": [{"inventario_id", "nombre", "talla"}]}]
    conjuntos = models.JSONField(default=list, blank=True)

class Configuracion(models.Model):
    """Ajustes del sistema como pares clave/valor (por ejemplo, la clave de administrador cifrada)."""
    clave = models.CharField(max_length=50, unique=True)
    valor = models.TextField(blank=True)

    def __str__(self):
        return self.clave


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    # PROTECT: un producto con ventas no se puede borrar, así el historial queda completo
    inventario = models.ForeignKey(Inventario, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(**MONTO)
    # subtotal = lo cobrado realmente por este producto (si fue parte de un conjunto, ya incluye su parte del precio del conjunto)
    subtotal = models.DecimalField(default=0, **MONTO)


class Conjunto(models.Model):
    """Varias prendas que, vendidas juntas, tienen un precio especial (por ejemplo, 'Buzo completo')."""
    nombre = models.CharField(max_length=100)
    colegio = models.ForeignKey(Colegio, on_delete=models.PROTECT, null=True, blank=True,
                                help_text='Vacío = vale para todos los colegios')
    componentes = models.ManyToManyField(Uniforme, related_name='conjuntos')
    precio = models.DecimalField(**MONTO)   # precio general (para las tallas sin precio propio)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - {self.colegio}" if self.colegio_id else self.nombre


class PrecioConjuntoTalla(models.Model):
    """Precio del conjunto para una talla específica (reemplaza al precio general)."""
    conjunto = models.ForeignKey(Conjunto, on_delete=models.CASCADE, related_name='precios_talla')
    talla = models.ForeignKey(Talla, on_delete=models.CASCADE)
    precio = models.DecimalField(**MONTO)

    class Meta:
        unique_together = [('conjunto', 'talla')]
