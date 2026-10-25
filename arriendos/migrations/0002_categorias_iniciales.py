from django.db import migrations

CATEGORIAS = ['Diablada', 'Caporal', 'Tinku', 'Morenada', 'Saya', 'Cueca', 'Figurines']


def crear(apps, schema_editor):
    Categoria = apps.get_model('arriendos', 'Categoria')
    for nombre in CATEGORIAS:
        Categoria.objects.get_or_create(nombre=nombre)


class Migration(migrations.Migration):
    dependencies = [('arriendos', '0001_initial')]
    operations = [migrations.RunPython(crear, migrations.RunPython.noop)]
