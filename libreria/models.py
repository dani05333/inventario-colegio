"""Librería (Chloe Librería): productos con su código de barras de fábrica, ventas e ingresos de mercadería.
Todo va separado de la tienda de uniformes."""
from django.db import models

from AppInventario.models import MONTO, Venta as VentaUniformes


class Categoria(models.Model):
    nombre = models.CharField(max_length=60)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    # El código que ya trae el producto (EAN/UPC). Si no trae, se genera uno interno que empieza con 201.
    codigo_barras = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    marca = models.CharField(max_length=80, blank=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    precio = models.DecimalField(**MONTO)                 # precio de venta
    costo = models.DecimalField(default=0, **MONTO)       # lo que cuesta comprarlo (opcional, para ver el margen)
    stock = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)  # avisa cuando quedan esta cantidad o menos (0 = sin aviso)
    activo = models.BooleanField(default=True)            # los inactivos no aparecen en el punto de venta
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.marca})' if self.marca else self.nombre

    @property
    def stock_bajo(self):
        return self.stock_minimo > 0 and self.stock <= self.stock_minimo


class Venta(models.Model):
    METODOS_PAGO = VentaUniformes.METODOS_PAGO

    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(**MONTO)
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='efectivo')
    anulada = models.BooleanField(default=False)
    fecha_anulacion = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.CharField(max_length=200, blank=True)

    @property
    def folio(self):
        """Número que sale en la boleta: L-1, L-2… (así no se confunde con las boletas de uniformes)."""
        return f'L-{self.pk}'


class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    # PROTECT: un producto con ventas no se borra (se desactiva), así el historial queda completo
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='ventas')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(**MONTO)
    subtotal = models.DecimalField(**MONTO)


class Ingreso(models.Model):
    """Mercadería que llegó: cuántas unidades se sumaron al stock y a qué costo."""
    fecha = models.DateTimeField(auto_now_add=True)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='ingresos')
    cantidad = models.PositiveIntegerField()
    costo_unitario = models.DecimalField(default=0, **MONTO)
