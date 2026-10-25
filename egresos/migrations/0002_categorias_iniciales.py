from django.db import migrations

CATEGORIAS = [
    'Telas', 'Hilos', 'Botones y broches', 'Cierres y elásticos', 'Insumos de costura', 'Mercadería para la librería',
    'Arriendo', 'Luz, agua e internet', 'Transporte y envíos', 'Publicidad', 'Mantención y reparaciones', 'Otros',
]


def crear(apps, schema_editor):
    CategoriaGasto = apps.get_model('egresos', 'CategoriaGasto')
    for nombre in CATEGORIAS:
        CategoriaGasto.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [('egresos', '0001_initial')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
