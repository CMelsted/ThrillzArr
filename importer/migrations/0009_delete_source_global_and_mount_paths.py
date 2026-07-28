from django.db import migrations, models


def carry_delete_flag_to_setting(apps, schema_editor):
    Setting = apps.get_model('importer', 'Setting')
    ConversionPreset = apps.get_model('importer', 'ConversionPreset')

    default_preset = (
        ConversionPreset.objects.filter(is_default=True).first()
        or ConversionPreset.objects.first()
    )
    if default_preset and default_preset.delete_source_after_success:
        Setting.objects.update(delete_source_after_success=True)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0008_remove_setting_output_scheme'),
    ]

    operations = [
        migrations.AddField(
            model_name='setting',
            name='delete_source_after_success',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(carry_delete_flag_to_setting, noop),
        migrations.RemoveField(
            model_name='conversionpreset',
            name='delete_source_after_success',
        ),
        migrations.AlterField(
            model_name='setting',
            name='completed_directory',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.RemoveField(
            model_name='setting',
            name='input_directory',
        ),
        migrations.RemoveField(
            model_name='setting',
            name='output_directory',
        ),
    ]
