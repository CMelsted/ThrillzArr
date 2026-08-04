from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0009_delete_source_global_and_mount_paths'),
    ]

    operations = [
        migrations.AlterModelManagers(
            name='setting',
            managers=[],
        ),
        migrations.RemoveField(
            model_name='setting',
            name='completed_directory',
        ),
        migrations.RemoveField(
            model_name='conversionpreset',
            name='move_to_audiobookshelf',
        ),
        migrations.RemoveField(
            model_name='conversionpreset',
            name='audiobookshelf_library_path',
        ),
    ]
