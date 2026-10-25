from django import forms

from AppInventario.forms import NombreUnicoForm, normalizar_nombre
from egresos.forms import FormEstilado

from .models import Categoria, Cliente, Pieza, Traje


class CategoriaForm(NombreUnicoForm):
    etiqueta = 'la categoría'

    class Meta:
        model = Categoria
        fields = ['nombre']


class PiezaForm(FormEstilado):
    class Meta:
        model = Pieza
        fields = ['nombre', 'categoria', 'talla', 'stock', 'precio', 'figurin', 'activo', 'notas']
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Pechera de diablada'}),
                   'talla': forms.TextInput(attrs={'placeholder': 'Ej: adulto, niño, M'}),
                   'notas': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].empty_label = 'Sin categoría'

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))


class TrajeForm(FormEstilado):
    class Meta:
        model = Traje
        fields = ['nombre', 'categoria', 'talla', 'precio', 'activo', 'notas']
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej: Traje completo de diablada'}),
                   'talla': forms.TextInput(attrs={'placeholder': 'Ej: adulto'}),
                   'notas': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].empty_label = 'Sin categoría'

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))


class ClienteForm(FormEstilado):
    class Meta:
        model = Cliente
        fields = ['nombre', 'tipo', 'contacto', 'telefono', 'email', 'notas']
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Ej: 4° básico B · Colegio Prado'}),
                   'notas': forms.Textarea(attrs={'rows': 2})}

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))
