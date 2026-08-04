from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0005_cover_image_link'),
    ]

    operations = [
        migrations.AlterField(
            model_name='status',
            name='status',
            field=models.CharField(choices=[('Pending Review', 'Pending Review'), ('Processing', 'Processing'), ('Done', 'Done'), ('Error', 'Error'), ('Abandoned', 'Abandoned')], max_length=20),
        ),
        migrations.AddField(
            model_name='status',
            name='progress_percent',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='status',
            name='stage',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='status',
            name='task_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='status',
            name='cancel_requested',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='status',
            name='pgid',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ConversionPreset',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('is_default', models.BooleanField(default=False)),
                ('output_scheme', models.CharField(max_length=255)),
                ('move_to_audiobookshelf', models.BooleanField(default=False)),
                ('audiobookshelf_library_path', models.CharField(blank=True, default='', max_length=255)),
                ('delete_source_after_success', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='book',
            name='preset',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='importer.conversionpreset'),
        ),
    ]
