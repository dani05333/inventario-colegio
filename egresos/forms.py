from django import forms

from AppInventario.forms import NombreUnicoForm, normalizar_nombre

from .models import CategoriaGasto, Empleado, Gasto, PagoEmpleado, Proveedor, RegistroHoras


class FormEstilado(forms.ModelForm):
    """Aplica las clases de Bootstrap a todos los campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            w = campo.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault('class', 'form-check-input')
            elif isinstance(w, forms.Select):
                w.attrs.setdefault('class', 'form-select')
            else:
                w.attrs.setdefault('class', 'form-control')


class CategoriaGastoForm(NombreUnicoForm):
    etiqueta = 'la categoría'

    class Meta:
        model = CategoriaGasto
        fields = ['nombre']


class GastoForm(FormEstilado):
    # El proveedor se escribe (con sugerencias); al guardar se enlaza su ficha o se crea una nueva
    proveedor = forms.CharField(label='Proveedor', max_length=100, required=False,
                                widget=forms.TextInput(attrs={'list': 'proveedores', 'autocomplete': 'off'}))

    class Meta:
        model = Gasto
        fields = ['fecha', 'categoria', 'descripcion', 'cantidad', 'unidad', 'monto', 'metodo_pago', 'negocio', 'documento', 'notas']
        labels = {'descripcion': 'Qué se compró', 'monto': 'Monto total', 'metodo_pago': 'Forma de pago', 'negocio': 'Para qué negocio'}
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descripcion': forms.TextInput(attrs={'placeholder': 'Ej: tela gabardina azul'}),
            'cantidad': forms.NumberInput(attrs={'step': 'any', 'min': 0, 'placeholder': 'Ej: 5'}),
            'unidad': forms.TextInput(attrs={'placeholder': 'metros, unidades…', 'list': 'unidades'}),
            'monto': forms.NumberInput(attrs={'min': 0}),
            'notas': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].empty_label = 'Elige…'
        if self.instance.pk and self.instance.proveedor_id:
            self.initial.setdefault('proveedor', self.instance.proveedor.nombre)
        # El proveedor va junto a la cantidad (en el mismo orden que antes)
        self.order_fields(['fecha', 'categoria', 'descripcion', 'cantidad', 'unidad', 'monto', 'proveedor', 'metodo_pago', 'negocio', 'documento', 'notas'])

    def clean_descripcion(self):
        return normalizar_nombre(self.cleaned_data.get('descripcion'))

    def clean_proveedor(self):
        return normalizar_nombre(self.cleaned_data.get('proveedor'))

    def save(self, commit=True):
        gasto = super().save(commit=False)
        gasto.proveedor = Proveedor.por_nombre(self.cleaned_data.get('proveedor'))
        if commit:
            gasto.save()
        return gasto


class ProveedorForm(FormEstilado):
    class Meta:
        model = Proveedor
        fields = ['nombre', 'rubro', 'contacto', 'telefono', 'email', 'direccion', 'notas']
        widgets = {'notas': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ej: atiende de lunes a viernes, hace envíos, da crédito a 30 días…'}),
                   'rubro': forms.TextInput(attrs={'placeholder': 'Ej: telas, hilos y botones'})}

    def clean_nombre(self):
        nombre = normalizar_nombre(self.cleaned_data.get('nombre'))
        if not nombre:
            raise forms.ValidationError('Escribe el nombre del proveedor.')
        repetido = next((p for p in Proveedor.objects.exclude(pk=self.instance.pk) if normalizar_nombre(p.nombre).casefold() == nombre.casefold()), None)
        if repetido:
            raise forms.ValidationError(f'Ya existe el proveedor «{repetido}».')
        return nombre


class EmpleadoForm(FormEstilado):
    class Meta:
        model = Empleado
        fields = ['nombre', 'cargo', 'tipo_pago', 'sueldo_mensual', 'valor_hora', 'telefono', 'fecha_ingreso', 'activo', 'notas']
        labels = {'tipo_pago': 'Cómo se le paga', 'sueldo_mensual': 'Sueldo mensual', 'valor_hora': 'Valor por hora',
                  'fecha_ingreso': 'Fecha de ingreso', 'activo': 'Trabaja actualmente'}
        widgets = {'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'), 'notas': forms.Textarea(attrs={'rows': 2})}

    def clean_nombre(self):
        return normalizar_nombre(self.cleaned_data.get('nombre'))

    def clean(self):
        datos = super().clean()
        if datos.get('tipo_pago') == 'mensual' and not datos.get('sueldo_mensual'):
            self.add_error('sueldo_mensual', 'Indica el sueldo mensual.')
        if datos.get('tipo_pago') == 'hora' and not datos.get('valor_hora'):
            self.add_error('valor_hora', 'Indica cuánto se paga por hora.')
        return datos


class RegistroHorasForm(FormEstilado):
    class Meta:
        model = RegistroHoras
        fields = ['fecha', 'horas', 'nota']
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'horas': forms.NumberInput(attrs={'step': '0.25', 'min': 0, 'max': 24, 'placeholder': 'Ej: 8 o 4.5'}),
                   'nota': forms.TextInput(attrs={'placeholder': 'Opcional'})}

    def clean_horas(self):
        horas = self.cleaned_data.get('horas')
        if horas is not None and not (0 < horas <= 24):
            raise forms.ValidationError('Las horas deben estar entre 0 y 24.')
        return horas


class PagoEmpleadoForm(FormEstilado):
    class Meta:
        model = PagoEmpleado
        fields = ['fecha', 'periodo', 'tipo', 'monto', 'metodo_pago', 'nota']
        labels = {'metodo_pago': 'Forma de pago'}
        widgets = {'fecha': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
                   'periodo': forms.TextInput(attrs={'type': 'month'}),
                   'monto': forms.NumberInput(attrs={'min': 1}),
                   'nota': forms.TextInput(attrs={'placeholder': 'Opcional'})}

    def clean_periodo(self):
        periodo = (self.cleaned_data.get('periodo') or '').strip()
        try:
            anio, mes = (int(x) for x in periodo.split('-'))
            assert 2000 <= anio <= 2100 and 1 <= mes <= 12
        except (ValueError, AssertionError):
            raise forms.ValidationError('Elige el mes que se está pagando.')
        return f'{anio:04d}-{mes:02d}'
