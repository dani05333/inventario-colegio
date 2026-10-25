from django import forms

from AppInventario.forms import NombreUnicoForm, normalizar_nombre

from .models import Categoria, Producto


class CategoriaForm(NombreUnicoForm):
    etiqueta = 'la categoría'

    class Meta:
        model = Categoria
        fields = ['nombre']


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['codigo_barras', 'nombre', 'marca', 'categoria', 'precio', 'costo', 'stock', 'stock_minimo', 'activo']
        labels = {
            'codigo_barras': 'Código de barras', 'precio': 'Precio de venta', 'costo': 'Costo (lo que pagas por él)',
            'stock': 'Stock', 'stock_minimo': 'Avisar cuando queden', 'activo': 'Se vende (aparece en el punto de venta)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].empty_label = 'Sin categoría'
        self.fields['codigo_barras'].error_messages['unique'] = 'Ya hay un producto con este código de barras.'

    def clean_codigo_barras(self):
        codigo = (self.cleaned_data.get('codigo_barras') or '').strip()
        if not codigo:
            raise forms.ValidationError('Escanea el código del producto o usa «Generar código».')
        return codigo

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))

    def clean_marca(self):
        return normalizar_nombre(self.cleaned_data.get('marca'))
