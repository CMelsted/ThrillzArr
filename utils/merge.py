import logging
import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from django.conf import settings
# core merge logic:
from m4b_merge import audible_helper, config, helpers, m4b_helper

from importer.models import (Author, Book, ConversionPreset, Narrator,
                             Setting, Status, StatusChoices)

# Get an instance of a logger
logger = logging.getLogger(__name__)


def set_configs(book=None):
    existing_settings = Setting.objects.first()
    if existing_settings:
        config.api_url = existing_settings.api_url
        config.junk_dir = existing_settings.completed_directory
        config.num_cpus = (
            existing_settings.num_cpus if existing_settings.num_cpus > 0
            else os.cpu_count()
        )
        config.output = existing_settings.output_directory

    preset = None
    if book:
        preset = book.preset
    if not preset:
        preset = ConversionPreset.get_default()
    if preset:
        config.path_format = preset.output_scheme


def _update_status(book, **fields):
    # Targeted UPDATE so concurrent writes (e.g. the abandon view setting
    # cancel_requested from the web process) are never clobbered by a
    # stale in-memory save().
    Status.objects.filter(pk=book.status.pk).update(**fields)


def _set_progress(book, percent, stage):
    _update_status(book, progress_percent=percent, stage=stage)


def _cancelled(book):
    book.status.refresh_from_db()
    return (
        book.status.cancel_requested
        or book.status.status == StatusChoices.ABANDONED
    )


def _fail(book, message):
    logger.error(message)
    _update_status(
        book,
        status=StatusChoices.ERROR,
        message=message,
        stage='',
        pgid=None
    )


def _apply_book_overrides(metadata, book):
    """
        Push any manual edits made on the Book model back into the
        metadata dict used for tagging, so review-stage edits are
        reflected in the output file.
    """
    # Book.title already contains "title - subtitle" when a subtitle
    # existed, so drop the separate subtitle to avoid doubling it
    metadata['title'] = book.title
    metadata.pop('subtitle', None)

    metadata['description'] = book.short_desc
    metadata['summary'] = book.long_desc

    if book.cover_image_link:
        metadata['image'] = book.cover_image_link

    metadata['releaseDate'] = (
        f"{book.release_date.isoformat()}T00:00:00.000Z"
    )

    authors = [{'name': str(author)} for author in book.authors.all()]
    if authors:
        metadata['authors'] = authors
    narrators = [{'name': str(narrator)} for narrator in book.narrators.all()]
    if narrators:
        metadata['narrators'] = narrators

    if book.series:
        series = metadata.get('seriesPrimary', {})
        series['name'] = book.series
        metadata['seriesPrimary'] = series
    else:
        metadata.pop('seriesPrimary', None)

    return metadata


def _post_process(book, m4b):
    """
        After a successful merge: optionally relocate the output into an
        Audiobookshelf library, then either delete the source input or
        move it to the completed/junk dir. Returns the final output path.
    """
    output_file = Path(f"{m4b.book_output}.m4b")
    chapters_file = Path(f"{m4b.book_output}.chapters.txt")
    dest = output_file

    preset = book.preset or ConversionPreset.get_default()

    if (preset and preset.move_to_audiobookshelf
            and preset.audiobookshelf_library_path):
        rel_path = os.path.relpath(m4b.book_output, config.output)
        target_base = Path(preset.audiobookshelf_library_path) / rel_path
        target_base.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Moving output to Audiobookshelf library: {target_base}")
        shutil.move(str(output_file), f"{target_base}.m4b")
        if chapters_file.exists():
            shutil.move(str(chapters_file), f"{target_base}.chapters.txt")
        dest = Path(f"{target_base}.m4b")

    if preset and preset.delete_source_after_success:
        m4b.cleanup_cover()
        src = Path(book.src_path)
        logger.info(f"Deleting source input: {src}")
        try:
            if src.is_dir():
                shutil.rmtree(src)
            elif src.exists():
                src.unlink()
        except OSError:
            logger.warning(f"Couldn't delete source input: {src}")
    else:
        m4b.move_completed_input()

    return dest


def run_m4b_merge(asin: str):
    # Log Level
    env_log_level = os.environ.get("LOG_LEVEL", "INFO")
    logging.basicConfig(level=env_log_level)

    book = Book.objects.get(asin=asin)

    # Job may have been abandoned while still queued
    if _cancelled(book):
        logger.info(f"Skipping cancelled job for {asin}")
        return

    set_configs(book)

    # Log all Settings
    logger.debug(f'Using API URL: {config.api_url}')
    logger.debug(f'Using junk path: {config.junk_dir}')
    logger.debug(f'Using CPU cores: {config.num_cpus}')
    logger.debug(f'Using output path: {config.output}')
    logger.debug(f'Using output format: {config.path_format}')

    logger.info(
        f"{'-' * 15} Starting to process {asin}: {book.title} {'-' * 15}")
    _set_progress(book, 5, "Preparing")

    input_data = helpers.get_directory(Path(book.src_path))
    if not input_data:
        _fail(
            book,
            f"invalid input_data: {input_data} for book: {book} "
            f"at path: {book.src_path}"
        )
        return

    audible = audible_helper.BookData(asin)
    metadata = _apply_book_overrides(
        audible.fetch_api_data(config.api_url), book
    )

    # Process metadata and run components to merge files
    m4b = m4b_helper.M4bMerge(
        input_data,
        metadata,
        Path(book.src_path),
        audible.get_chapters()
    )
    # Persist the child process group id so the abandon view can kill
    # the running m4b-tool tree directly
    m4b.on_subprocess_start = (
        lambda pgid: _update_status(book, pgid=pgid)
    )

    try:
        m4b.prepare_data()
        m4b.prepare_command_args()

        if _cancelled(book):
            return
        _set_progress(book, 10, "Merging audio")
        logger.info(f"Processing {book.title}")
        m4b.merge()
        _update_status(book, pgid=None)

        if _cancelled(book):
            return
        output_file = Path(f"{m4b.book_output}.m4b")
        if not output_file.exists():
            _fail(book, f"Merge produced no output file at {output_file}")
            return

        _set_progress(book, 80, "Fixing chapters")
        m4b.fix_chapters()
        _update_status(book, pgid=None)

        if _cancelled(book):
            return
        _set_progress(book, 90, "Post-processing")
        dest = _post_process(book, m4b)
    except Exception as e:
        if _cancelled(book):
            logger.info(f"Job for {asin} cancelled during processing")
            return
        logger.error(f"Error occured while merging '{book.title}': {e}")
        message = (
            str(e) + "\n" + traceback.format_exc()
            if settings.DEBUG else str(e)
        )
        _update_status(
            book,
            status=StatusChoices.ERROR,
            message=message,
            stage='',
            pgid=None
        )
        return

    Book.objects.filter(pk=book.pk).update(dest_path=str(dest))
    _update_status(
        book,
        status=StatusChoices.DONE,
        message='',
        progress_percent=100,
        stage='',
        pgid=None
    )
    logger.info(f"{'-' * 15} Done processing {asin} {'-' * 15}")


def create_book(asin, original_path) -> Book:
    # Make models only if book doesn't exist
    if not Book.objects.filter(asin=asin).exists():
        book = make_book_model(asin, original_path)

    else:
        book = Book.objects.get(asin=asin)
        book.src_path = original_path
        book.save()

        book.status.status = StatusChoices.PENDING_REVIEW
        book.status.message = ""
        book.status.progress_percent = 0
        book.status.stage = ""
        book.status.task_id = ""
        book.status.cancel_requested = False
        book.status.pgid = None
        book.status.save()
        logger.warning("Book already exists in database, only merging files")

    return book


def make_book_model(asin, original_path) -> Book:
    set_configs()
    # Create BookData object from asin response
    metadata = audible_helper.BookData(asin).fetch_api_data(config.api_url)

    # Book DB entry
    if 'subtitle' in metadata:
        base_title = metadata['title']
        base_subtitle = metadata['subtitle']
        title = f"{base_title} - {base_subtitle}"
    else:
        title = metadata['title']

    if 'runtimeLengthMin' in metadata:
        runtime = metadata['runtimeLengthMin']
    else:
        runtime = 0

    status = Status.objects.create(status=StatusChoices.PENDING_REVIEW)

    book = Book.objects.create(
        title=title,
        asin=asin,
        short_desc=metadata['description'],
        long_desc=metadata['summary'],
        release_date=datetime.strptime(
            metadata['releaseDate'], '%Y-%m-%dT%H:%M:%S.%fZ'),
        publisher=metadata['publisherName'],
        lang=metadata['language'],
        runtime_length_minutes=runtime,
        format_type=metadata['formatType'],
        converted=True,
        status=status,
        cover_image_link=metadata['image'],
        src_path=original_path,
        preset=ConversionPreset.get_default()
    )

    # Only add in series if it exists
    if 'primarySeries' in metadata:
        book.series = metadata['primarySeries']['name']
        book.save()

    make_author_model(book, metadata['authors'])
    make_narrator_model(book, metadata['narrators'])

    return book


def set_book_people(book, authors_str: str, narrators_str: str):
    """
        Replace a book's authors/narrators from comma-separated name
        strings (used by the review/edit metadata forms).
    """
    author_names = [n.strip() for n in authors_str.split(',') if n.strip()]
    narrator_names = [n.strip() for n in narrators_str.split(',') if n.strip()]

    if author_names:
        book.authors.clear()
        make_author_model(book, [{'name': name} for name in author_names])
    if narrator_names:
        book.narrators.clear()
        make_narrator_model(book, [{'name': name} for name in narrator_names])


def make_author_model(book, authors: list[dict[str, str]]):
    # Author DB entry
    # Create new entry for each author if there's more than one
    for author in authors:
        author_name_full = author['name']
        author_name_split = author_name_full.split()
        last_name_index = len(author_name_split) - 1

        # Check if author asin exists
        if 'asin' in author:
            author_asin = author['asin']
            _filter_vals = {'asin': author_asin}

        # If author doesn't exist, search by name and set asin to none
        else:
            author_asin = None
            _filter_vals = {
                'first_name': author_name_split[0],
                'last_name': author_name_split[last_name_index]
            }
            logger.warning(
                f"No author ASIN for: "
                f"{author_name_full}"
            )

        # Check if author is in database
        if not (author := Author.objects.filter(**_filter_vals).first()):
            logger.info(
                f"Using existing db entry for author: "
                f"{author_name_full}"
            )
            author = Author.objects.create(
                asin=author_asin,
                first_name=author_name_split[0],
                last_name=author_name_split[last_name_index]
            )

        author.books.add(book)
        author.save()


def make_narrator_model(book, narrators: list[dict[str, str]]):
    # Narrator DB entry
    # Create new entry for each narrator if there's more than one
    for narrator in narrators:

        narr_name_split = narrator['name'].split()
        last_name_index = len(narr_name_split) - 1

        if not (narrator := Narrator.objects.filter(
            first_name=narr_name_split[0],
            last_name=narr_name_split[last_name_index]
        ).first()):
            narrator = Narrator.objects.create(
                first_name=narr_name_split[0],
                last_name=narr_name_split[last_name_index]
            )

        narrator.books.add(book)
        narrator.save()
