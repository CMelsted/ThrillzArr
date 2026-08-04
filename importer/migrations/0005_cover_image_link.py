from django.db import migrations, models
from m4b_merge import audible_helper, config


def add_cover_image_link(apps, _):
    # Use the historical models (schema-as-of-this-migration), not the
    # live app models - importing utils.merge/Setting here would query
    # columns added by later migrations that don't exist yet on a
    # from-scratch install
    Book = apps.get_model("importer", "Book")
    Setting = apps.get_model("importer", "Setting")

    books = Book.objects.all()
    if not books.exists():
        return

    existing_settings = Setting.objects.first()
    if not existing_settings:
        return
    config.api_url = existing_settings.api_url

    for book in books:
        metadata = audible_helper.BookData(book.asin).fetch_api_data(config.api_url)
        book.cover_image_link = metadata['image']
        book.save()

class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0004_book_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='book',
            name='cover_image_link',
            field=models.URLField(blank=True, null=True),
            preserve_default=False,
        ),

        migrations.RunPython(add_cover_image_link, migrations.RunPython.noop),

        migrations.AlterField(
            model_name='book',
            name='cover_image_link',
            field=models.URLField(null=False)
        ),
    ]
