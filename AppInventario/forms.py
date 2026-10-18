import re

from django import forms

from .models import Colegio, Talla, Uniforme, Inventario


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


class InventarioForm(forms.ModelForm):
    class Meta:
        model = Inventario
        fields = ['codigo_barras', 'cantidad', 'colegio', 'talla', 'uniforme', 'precio']

    def clean_codigo_barras(self):
        return (self.cleaned_data.get('codigo_barras') or '').strip()

    def clean(self):
        datos = super().clean()
        colegio, talla, uniforme = datos.get('colegio'), datos.get('talla'), datos.get('uniforme')
        if colegio and talla and uniforme:
            repetido = (Inventario.objects.filter(colegio=colegio, talla=talla, uniforme=uniforme)
                        .exclude(pk=self.instance.pk).first())
            if repetido:
                raise forms.ValidationError(
                    f'Ya existe el producto «{uniforme} · talla {talla} · {colegio}» '
                    f'(código {repetido.codigo_barras}). Si llegaron más unidades, edita ese producto y suma el stock.')
        return datos
