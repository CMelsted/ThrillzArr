from django import forms
from .models import Book, ConversionPreset, Setting


class SettingForm(forms.ModelForm):
    move_completed_enabled = forms.BooleanField(
        required=False,
        initial=True,
        label='Move original input files to a folder after completion',
        widget=forms.CheckboxInput(attrs={'id': 'move-completed-enabled'})
    )

    # The move checkbox must render directly above the path it controls
    field_order = [
        'api_url',
        'num_cpus',
        'delete_source_after_success',
        'move_completed_enabled',
        'completed_directory',
    ]

    class Meta:
        model = Setting
        fields = (
            'api_url',
            'num_cpus',
            'delete_source_after_success',
            'completed_directory'
        )
        labels = {
            'api_url': 'Custom API URL',
            'num_cpus': 'Number of CPUs to use (0 will use all available)',
            'delete_source_after_success': 'Delete source files after successful conversion',
            'completed_directory': 'Folder to move original input files into'
        }
        widgets = {
            'api_url': forms.URLInput(attrs={'class': 'input is-fullwidth'}),
            'num_cpus': forms.NumberInput(attrs={'class': 'input is-fullwidth'}),
            'delete_source_after_success': forms.CheckboxInput(attrs={'id': 'delete-source-enabled'}),
            'completed_directory': forms.TextInput(attrs={'class': 'input is-fullwidth', "required": False}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['move_completed_enabled'].initial = bool(
                self.instance.completed_directory)

    def clean(self):
        cleaned_data = super().clean()
        move_enabled = cleaned_data.get('move_completed_enabled')

        # Moving the originals and deleting them are contradictory
        if move_enabled and cleaned_data.get('delete_source_after_success'):
            raise forms.ValidationError(
                'Moving original files and deleting them are mutually '
                'exclusive - choose one.'
            )

        if not move_enabled:
            cleaned_data['completed_directory'] = ''
        elif not cleaned_data.get('completed_directory'):
            self.add_error(
                'completed_directory',
                'A folder path is required when moving is enabled'
            )
        return cleaned_data


class PresetForm(forms.ModelForm):
    class Meta:
        model = ConversionPreset
        fields = (
            'name',
            'is_default',
            'output_scheme',
            'move_to_audiobookshelf',
            'audiobookshelf_library_path'
        )
        labels = {
            'name': 'Preset name',
            'is_default': 'Use as default preset',
            'output_scheme': 'Output path format',
            'move_to_audiobookshelf': 'Move completed books into an Audiobookshelf library folder',
            'audiobookshelf_library_path': 'Audiobookshelf library folder path'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'output_scheme': forms.TextInput(attrs={'class': 'input is-fullwidth'}),
            'audiobookshelf_library_path': forms.TextInput(attrs={'class': 'input is-fullwidth', "required": False}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('move_to_audiobookshelf') and not \
                cleaned_data.get('audiobookshelf_library_path'):
            self.add_error(
                'audiobookshelf_library_path',
                'A library path is required when moving to Audiobookshelf'
            )
        return cleaned_data


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
