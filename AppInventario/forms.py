from django import forms
from .models import Colegio, Talla, Uniforme, Inventario

class ColegioForm(forms.ModelForm):
    class Meta:
        model = Colegio
        fields = ['nombre']
        
class TallaForm(forms.ModelForm):
    class Meta:
        model = Talla
        fields = ['nombre']
        
class UniformeForm(forms.ModelForm):
    class Meta:
        model = Uniforme
        fields = ['nombre']
        
class InventarioForm(forms.ModelForm):
    class Meta:
        model = Inventario
        fields = ['codigo_barras','cantidad', 'colegio', 'talla', 'uniforme', 'precio']

        widgets = {
            'cantidad': forms.NumberInput(attrs={'class': 'form-control'}),
            'colegio': forms.Select(attrs={'class': 'form-select'}),
            'talla': forms.Select(attrs={'class': 'form-select'}),
            'uniforme': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
        }