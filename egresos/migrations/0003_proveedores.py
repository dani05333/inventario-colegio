"""Fichas de proveedores: el proveedor de cada gasto pasa de texto a una ficha (los nombres que ya había se
convierten en fichas, sin repetir los que solo cambian en mayúsculas o espacios)."""
import django.db.models.deletion
from django.db import migrations, models


def a_fichas(apps, schema_editor):
    Gasto = apps.get_model('egresos', 'Gasto')
    Proveedor = apps.get_model('egresos', 'Proveedor')
    fichas = {}
    for gasto in Gasto.objects.exclude(proveedor_texto=''):
        nombre = ' '.join(gasto.proveedor_texto.split())
        if not nombre:
            continue
        clave = nombre.casefold()
        if clave not in fichas:
            fichas[clave] = Proveedor.objects.create(nombre=nombre)
        gasto.proveedor_ficha = fichas[clave]
        gasto.save(update_fields=['proveedor_ficha'])


def a_texto(apps, schema_editor):
    Gasto = apps.get_model('egresos', 'Gasto')
    for gasto in Gasto.objects.exclude(proveedor_ficha=None).select_related('proveedor_ficha'):
        gasto.proveedor_texto = gasto.proveedor_ficha.nombre
        gasto.save(update_fields=['proveedor_texto'])


class Migration(migrations.Migration):
    dependencies = [('egresos', '0002_categorias_iniciales')]

    operations = [
        migrations.CreateModel(
            name='Proveedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100)),
                ('contacto', models.CharField(blank=True, max_length=100, verbose_name='Persona de contacto')),
                ('telefono', models.CharField(blank=True, max_length=40, verbose_name='Teléfono')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='Correo')),
                ('direccion', models.CharField(blank=True, max_length=200, verbose_name='Dirección')),
                ('rubro', models.CharField(blank=True, max_length=150, verbose_name='Qué vende')),
                ('notas', models.TextField(blank=True)),
                ('creado', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['nombre']},
        ),
        migrations.RenameField('gasto', 'proveedor', 'proveedor_texto'),
        migrations.AddField(
            model_name='gasto', name='proveedor_ficha',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gastos', to='egresos.proveedor'),
        ),
        migrations.RunPython(a_fichas, a_texto),
        migrations.RemoveField('gasto', 'proveedor_texto'),
        migrations.RenameField('gasto', 'proveedor_ficha', 'proveedor'),
    ]
