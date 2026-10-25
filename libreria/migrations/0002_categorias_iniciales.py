from django.db import migrations

CATEGORIAS = ['Cuadernos', 'Lápices y lápices pasta', 'Arte y manualidades', 'Papelería', 'Oficina', 'Estuches y mochilas']


def crear(apps, schema_editor):
    Categoria = apps.get_model('libreria', 'Categoria')
    for nombre in CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [('libreria', '0001_initial')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
