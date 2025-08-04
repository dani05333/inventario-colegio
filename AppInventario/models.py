from django.db import models

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
    codigo_barras = models.CharField(max_length=50, unique=True, default=0)
    cantidad = models.PositiveIntegerField()
    colegio = models.ForeignKey(Colegio, on_delete=models.CASCADE)
    talla = models.ForeignKey(Talla, on_delete=models.CASCADE)
    uniforme = models.ForeignKey(Uniforme, on_delete=models.CASCADE)
    precio = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"{self.uniforme} - {self.talla} - {self.colegio}"
    
    @property
    def precio_total(self):
        return self.cantidad * self.precio
    
class Venta(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2)

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE)
    inventario = models.ForeignKey(Inventario, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)  
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)         

