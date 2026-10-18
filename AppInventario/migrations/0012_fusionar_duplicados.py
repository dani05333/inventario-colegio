"""Fusiona colegios, tallas y uniformes repetidos (mismo nombre sin importar mayúsculas ni espacios).

Se queda el registro más antiguo y los productos del inventario que apuntaban a los repetidos
pasan a apuntar a ese. Desde esta versión los formularios ya no permiten crear repetidos.
"""
import re

from django.db import migrations


def _clave(nombre):
    return re.sub(r'\s+', ' ', nombre or '').strip().casefold()


def fusionar(apps, schema_editor):
    Inventario = apps.get_model('AppInventario', 'Inventario')
    for modelo, campo in (('Colegio', 'colegio'), ('Talla', 'talla'), ('Uniforme', 'uniforme')):
        Modelo = apps.get_model('AppInventario', modelo)
        conservados = {}
        for obj in Modelo.objects.order_by('id'):
            limpio = re.sub(r'\s+', ' ', obj.nombre or '').strip()
            if limpio != obj.nombre:
                obj.nombre = limpio
                obj.save(update_fields=['nombre'])
            clave = _clave(obj.nombre)
            if clave not in conservados:
                conservados[clave] = obj
                continue
            Inventario.objects.filter(**{campo: obj}).update(**{campo: conservados[clave]})
            obj.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('AppInventario', '0011_configuracion'),
    ]

    operations = [
        migrations.RunPython(fusionar, migrations.RunPython.noop),
    ]
