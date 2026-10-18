import re

from django import forms

from .models import Colegio, Color, Conjunto, Inventario, Talla, Uniforme


def normalizar_nombre(nombre):
    """Quita espacios de más: '  Talla   6 ' -> 'Talla 6'."""
    return re.sub(r'\s+', ' ', nombre or '').strip()


class NombreUnicoForm(forms.ModelForm):
    """No permite dos registros con el mismo nombre (sin importar mayúsculas ni espacios)."""
    etiqueta = 'registro'

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data.get('nombre'))
        if not nombre:
            raise forms.ValidationError('Escribe un nombre.')
        # Se compara en Python: SQLite solo ignora mayúsculas en letras sin tilde («Ó» ≠ «ó»)
        clave = nombre.casefold()
        repetido = next((o for o in self._meta.model.objects.exclude(pk=self.instance.pk)
                         if normalizar_nombre(o.nombre).casefold() == clave), None)
        if repetido:
            raise forms.ValidationError(f'Ya existe {self.etiqueta} «{repetido.nombre}».')
        return nombre


class ColegioForm(NombreUnicoForm):
    etiqueta = 'el colegio'

    class Meta:
        model = Colegio
        fields = ['nombre']


class TallaForm(NombreUnicoForm):
    etiqueta = 'la talla'

    class Meta:
        model = Talla
        fields = ['nombre']


class UniformeForm(NombreUnicoForm):
    etiqueta = 'el uniforme'

    class Meta:
        model = Uniforme
        fields = ['nombre']


class ColorForm(NombreUnicoForm):
    etiqueta = 'el color'

    class Meta:
        model = Color
        fields = ['nombre']


class InventarioForm(forms.ModelForm):
    class Meta:
        model = Inventario
        fields = ['codigo_barras', 'cantidad', 'colegio', 'talla', 'uniforme', 'color', 'precio']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['color'].empty_label = 'Sin color'

    def clean_codigo_barras(self):
        return (self.cleaned_data.get('codigo_barras') or '').strip()

    def clean(self):
        datos = super().clean()
        colegio, talla, uniforme, color = datos.get('colegio'), datos.get('talla'), datos.get('uniforme'), datos.get('color')
        if colegio and talla and uniforme:
            repetido = (Inventario.objects.filter(colegio=colegio, talla=talla, uniforme=uniforme, color=color)
                        .exclude(pk=self.instance.pk).first())
            if repetido:
                nombre = f'{uniforme} {color}' if color else str(uniforme)
                raise forms.ValidationError(
                    f'Ya existe el producto «{nombre} · talla {talla} · {colegio}» '
                    f'(código {repetido.codigo_barras}). Si llegaron más unidades, edita ese producto y suma el stock.')
        return datos


class ConjuntoForm(forms.ModelForm):
    class Meta:
        model = Conjunto
        fields = ['nombre', 'colegio', 'componentes', 'precio', 'activo']
        widgets = {'componentes': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['colegio'].empty_label = 'Todos los colegios'
        self.fields['componentes'].queryset = Uniforme.objects.order_by('nombre')

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))

    def clean_componentes(self):
        componentes = self.cleaned_data.get('componentes')
        if not componentes or len(componentes) < 2:
            raise forms.ValidationError('Elige al menos 2 prendas que formen el conjunto.')
        return componentes
