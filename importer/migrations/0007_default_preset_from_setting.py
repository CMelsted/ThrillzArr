from django.db import migrations

DEFAULT_OUTPUT_SCHEME = 'author/title/title - subtitle'


def create_default_preset(apps, schema_editor):
    Setting = apps.get_model('importer', 'Setting')
    ConversionPreset = apps.get_model('importer', 'ConversionPreset')

    if ConversionPreset.objects.exists():
        return

    setting = Setting.objects.first()
    output_scheme = DEFAULT_OUTPUT_SCHEME
    if setting and getattr(setting, 'output_scheme', ''):
        output_scheme = setting.output_scheme

    ConversionPreset.objects.create(
        name='Default',
        is_default=True,
        output_scheme=output_scheme,
    )


def remove_default_preset(apps, schema_editor):
    ConversionPreset = apps.get_model('importer', 'ConversionPreset')
    ConversionPreset.objects.filter(name='Default').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0006_job_lifecycle_and_presets'),
    ]

    operations = [
        migrations.RunPython(create_default_preset, remove_default_preset),
    ]
