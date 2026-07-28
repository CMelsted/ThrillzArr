from django import forms
from .models import Book, ConversionPreset, Setting


class SettingForm(forms.ModelForm):
    class Meta:
        model = Setting
        fields = (
            'api_url',
            'num_cpus',
            'delete_source_after_success'
        )
        labels = {
            'api_url': 'Custom API URL',
            'num_cpus': 'Number of CPUs to use (0 will use all available)',
            'delete_source_after_success': 'Delete source files after successful conversion'
        }
        widgets = {
            'api_url': forms.URLInput(attrs={'class': 'input is-fullwidth'}),
            'num_cpus': forms.NumberInput(attrs={'class': 'input is-fullwidth'}),
        }


class PresetForm(forms.ModelForm):
    class Meta:
        model = ConversionPreset
        fields = (
            'name',
            'is_default',
            'output_scheme'
        )
        labels = {
            'name': 'Preset name',
            'is_default': 'Use as default preset',
            'output_scheme': 'Output path format'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'output_scheme': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
        }


class BookMetadataForm(forms.ModelForm):
    authors = forms.CharField(
        required=False,
        label='Authors (comma separated)',
        widget=forms.TextInput(attrs={'class': 'input is-fullwidth'})
    )
    narrators = forms.CharField(
        required=False,
        label='Narrators (comma separated)',
        widget=forms.TextInput(attrs={'class': 'input is-fullwidth'})
    )

    class Meta:
        model = Book
        fields = (
            'title',
            'series',
            'publisher',
            'lang',
            'release_date',
            'short_desc',
            'long_desc',
            'cover_image_link'
        )
        labels = {
            'title': 'Title',
            'series': 'Series',
            'publisher': 'Publisher',
            'lang': 'Language',
            'release_date': 'Release date',
            'short_desc': 'Short description',
            'long_desc': 'Long description',
            'cover_image_link': 'Cover image URL'
        }
        widgets = {
            'title': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'series': forms.TextInput(attrs={'class': 'input is-fullwidth', 'required': False}),
            'publisher': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'lang': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'release_date': forms.DateInput(attrs={'class': 'input is-fullwidth', 'type': 'date'}),
            'short_desc': forms.Textarea(attrs={'class': 'textarea', 'rows': 3}),
            'long_desc': forms.Textarea(attrs={'class': 'textarea', 'rows': 5}),
            'cover_image_link': forms.URLInput(attrs={'class': 'input is-fullwidth'}),
        }
