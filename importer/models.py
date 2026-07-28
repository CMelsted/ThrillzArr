from django.db import models
from pathlib import Path


class BookManager(models.Manager):
    def book_asin_validator(self, asin):
        errors = {}

        if len(asin) != 10 and len(asin) != 0:
            errors['invalid_asin'] = f"Invalid ASIN format for {asin}"

        if len(asin) == 0:
            errors['blank_asin'] = "Must fill in all ASIN fields"

        return errors


class SettingManager(models.Manager):
    def file_path_validator(self, path):
        errors = {}

        if not Path(path).is_dir():
            try:
                Path(path).mkdir(parents=True, exist_ok=True)
            except OSError:
                errors['invalid_path'] = (
                    f"Invalid path: {path}"
                )
        return errors


class StatusChoices(models.TextChoices):
    PENDING_REVIEW = "Pending Review"
    PROCESSING = "Processing"
    DONE = "Done"
    ERROR = "Error"
    ABANDONED = "Abandoned"


class Status(models.Model):
    status = models.CharField(max_length=20, choices=StatusChoices.choices)
    message = models.TextField()
    progress_percent = models.IntegerField(default=0)
    stage = models.CharField(max_length=100, blank=True, default='')
    task_id = models.CharField(max_length=255, blank=True, default='')
    cancel_requested = models.BooleanField(default=False)
    pgid = models.IntegerField(null=True, blank=True)

    def __str__(self) -> str:
        return self.status


class ConversionPreset(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_default = models.BooleanField(default=False)
    output_scheme = models.CharField(max_length=255)
    move_to_audiobookshelf = models.BooleanField(default=False)
    audiobookshelf_library_path = models.CharField(
        max_length=255, blank=True, default='')
    delete_source_after_success = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Only one preset may be the default
        if self.is_default:
            ConversionPreset.objects.exclude(pk=self.pk).update(
                is_default=False)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True).first() or \
            cls.objects.first()

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=255)
    asin = models.CharField(max_length=10)
    short_desc = models.TextField()
    long_desc = models.TextField()
    release_date = models.DateField()
    series = models.CharField(max_length=255, blank=True, default='')
    publisher = models.CharField(max_length=255)
    lang = models.CharField(max_length=25)
    runtime_length_minutes = models.IntegerField()
    format_type = models.CharField(max_length=25)
    converted = models.BooleanField()
    src_path = models.TextField()
    dest_path = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.OneToOneField(Status, on_delete=models.CASCADE)
    cover_image_link = models.URLField()
    preset = models.ForeignKey(
        ConversionPreset, null=True, blank=True, on_delete=models.SET_NULL)
    objects = BookManager()

    def __str__(self) -> str:
        return f"{self.title}: by {', '.join(str(author) for author in self.authors.all())}"


class Author(models.Model):
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)
    asin = models.CharField(max_length=10, null=True, default='')
    books = models.ManyToManyField(Book, related_name="authors")
    short_desc = models.TextField(blank=True, default='')
    long_desc = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Narrator(models.Model):
    first_name = models.CharField(max_length=45)
    last_name = models.CharField(max_length=45)
    books = models.ManyToManyField(Book, related_name="narrators")
    short_desc = models.TextField(blank=True, default='')
    long_desc = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Setting(models.Model):
    api_url = models.CharField(max_length=255)
    completed_directory = models.CharField(max_length=255)
    input_directory = models.CharField(max_length=255)
    num_cpus = models.IntegerField()
    output_directory = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = SettingManager()
