from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0007_default_preset_from_setting'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='setting',
            name='output_scheme',
        ),
    ]
