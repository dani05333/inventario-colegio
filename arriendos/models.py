"""Arriendo de trajes folclóricos (Chloe Arriendos).

El stock está en las PIEZAS (pantalón de diablada, pechera, máscara, oso…). Un TRAJE completo es un conjunto
de piezas con su propio precio: arrendar un traje usa sus piezas, así nunca se cuenta el stock dos veces.
Un ARRIENDO reserva piezas entre la fecha de retiro y la de devolución (ver disponibilidad.py)."""
from decimal import Decimal

from django.db import models
from django.utils import timezone

from AppInventario.models import MONTO, Venta

METODOS_PAGO = Venta.METODOS_PAGO


class Categoria(models.Model):
    nombre = models.CharField(max_length=60)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Pieza(models.Model):
    nombre = models.CharField(max_length=120)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    talla = models.CharField(max_length=30, blank=True)
    stock = models.PositiveIntegerField('Cantidad que tienen', default=0)
    precio = models.DecimalField('Precio de arriendo suelto', **MONTO)
    figurin = models.BooleanField('Es un figurín (oso, águila…)', default=False)
    activo = models.BooleanField('Se arrienda', default=True)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ['categoria__nombre', 'nombre', 'talla']

    def __str__(self):
        return f'{self.nombre} · {self.talla}' if self.talla else self.nombre


class Traje(models.Model):
    nombre = models.CharField(max_length=120)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    talla = models.CharField(max_length=30, blank=True)
    precio = models.DecimalField('Precio de arriendo del traje completo', **MONTO)
    activo = models.BooleanField('Se arrienda', default=True)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ['categoria__nombre', 'nombre', 'talla']

    def __str__(self):
        return f'{self.nombre} · {self.talla}' if self.talla else self.nombre


class TrajePieza(models.Model):
    traje = models.ForeignKey(Traje, on_delete=models.CASCADE, related_name='componentes')
    # PROTECT: una pieza que forma parte de un traje no se puede borrar
    pieza = models.ForeignKey(Pieza, on_delete=models.PROTECT, related_name='en_trajes')
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [('traje', 'pieza')]


class Cliente(models.Model):
    TIPOS = [('persona', 'Persona'), ('curso', 'Curso'), ('colegio', 'Colegio'), ('agrupacion', 'Agrupación / conjunto'), ('otro', 'Otro')]

    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=15, choices=TIPOS, default='persona')
    contacto = models.CharField('Persona responsable', max_length=120, blank=True)
    telefono = models.CharField('Teléfono', max_length=40, blank=True)
    email = models.EmailField('Correo', blank=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Arriendo(models.Model):
    ESTADOS = [('reservado', 'Reservado'), ('entregado', 'Entregado'), ('devuelto', 'Devuelto'), ('cancelado', 'Cancelado')]
    # Los que ocupan trajes (los devueltos y cancelados ya no)
    ACTIVOS = ('reservado', 'entregado')

    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name='arriendos')
    evento = models.CharField('Evento o motivo', max_length=150, blank=True)
    fecha_retiro = models.DateField('Retiran el')
    fecha_devolucion = models.DateField('Devuelven el')
    estado = models.CharField(max_length=10, choices=ESTADOS, default='reservado')
    total = models.DecimalField(default=0, **MONTO)
    garantia = models.DecimalField('Garantía', default=0, **MONTO)   # se devuelve al recibir los trajes bien
    garantia_devuelta = models.BooleanField(default=False)
    cargo_extra = models.DecimalField('Cargo por daños o atraso', default=0, **MONTO)
    faltantes = models.TextField('Faltantes o daños al devolver', blank=True)
    notas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    devuelto_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['fecha_retiro', 'id']

    def __str__(self):
        return f'{self.folio} · {self.cliente}'

    @property
    def folio(self):
        return f'A-{self.pk}'

    @property
    def pagado(self):
        return sum((p.monto for p in self.pagos.all()), Decimal(0))

    @property
    def saldo(self):
        return max(self.total + self.cargo_extra - self.pagado, Decimal(0))

    @property
    def atrasado(self):
        return self.estado == 'entregado' and self.fecha_devolucion < timezone.localdate()

    @property
    def unidades(self):
        return sum(l.cantidad for l in self.lineas.all())


class ArriendoLinea(models.Model):
    """Un traje completo o una pieza suelta del arriendo (uno de los dos)."""
    arriendo = models.ForeignKey(Arriendo, on_delete=models.CASCADE, related_name='lineas')
    traje = models.ForeignKey(Traje, on_delete=models.PROTECT, null=True, blank=True, related_name='arrendado')
    pieza = models.ForeignKey(Pieza, on_delete=models.PROTECT, null=True, blank=True, related_name='arrendada')
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(**MONTO)
    subtotal = models.DecimalField(**MONTO)

    @property
    def nombre(self):
        return str(self.traje) if self.traje_id else str(self.pieza)

    @property
    def es_traje(self):
        return bool(self.traje_id)


class Pago(models.Model):
    TIPOS = [('abono', 'Abono'), ('saldo', 'Saldo'), ('cargo', 'Cargo por daños o atraso')]

    arriendo = models.ForeignKey(Arriendo, on_delete=models.CASCADE, related_name='pagos')
    fecha = models.DateField(default=timezone.localdate)
    monto = models.DecimalField(**MONTO)
    tipo = models.CharField(max_length=10, choices=TIPOS, default='abono')
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='efectivo')

    class Meta:
        ordering = ['fecha', 'id']
