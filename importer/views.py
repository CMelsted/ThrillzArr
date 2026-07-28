# System imports
import logging
import os
import signal
from datetime import timedelta
from pathlib import Path

import requests
from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import TemplateView, View
# core merge logic:
from m4b_merge import helpers

from bragibooks_proj.celery import app as celery_app
# Import Merge functions for django
from utils.merge import create_book, set_book_people
# Import path helpers (locations come from the deploy-time bind mounts)
from utils.paths import importable_contents, input_dir
# Import Search tools
from utils.search_tools import ScoreTool, SearchTool

# Forms import
from .forms import BookMetadataForm, PresetForm, SettingForm
# Models import
from .models import Book, ConversionPreset, Setting, Status, StatusChoices
from .tasks import m4b_merge_task

# Get an instance of a logger
logger = logging.getLogger(__name__)


class ImportView(TemplateView):
    template_name = "importer.html"

    def get_context_data(self, **kwargs):
        return {"contents": importable_contents(input_dir())}

    def post(self, request):
        # Redirect if this is a new session
        existing_settings = Setting.objects.first()
        if not existing_settings:
            logger.debug("No settings found, returning to settings page")
            messages.error(
                request, "Settings must be configured before import"
            )
            return redirect("setting")

        if not (selected := request.POST.getlist('input_dir')):
            messages.error(request, "You must select content to import")
            return redirect("import")

        request.session['input_dir'] = selected
        return redirect("match")


class MatchView(TemplateView):
    template_name = "match.html"

    def get(self, request):
        # Redirect if this is a new session
        if 'input_dir' not in request.session:
            logger.debug("No session data found, returning to import page")
            return redirect("import")

        return render(request, self.template_name, self.get_context_data())

    def get_context_data(self, **kwargs) -> dict:
        # Check if any of these inputs exist in our DB
        # If so, prepopulate their asins
        context = []
        for this_dir in self.request.session['input_dir']:
            try:
                book = Book.objects.get(src_path=f"{this_dir}")
            except Book.DoesNotExist:
                context.append({'src_path': this_dir})
            else:
                context.append({'src_path': this_dir, 'asin': book.asin})

        return {"context": context}

    def post(self, request: HttpRequest):
        src_path = request.POST.get('src_path', '')
        input_dirs = request.session.get('input_dir', [])

        if src_path not in input_dirs:
            messages.error(request, "Unknown item")
            return redirect("match")

        # Removing an entry from the match list
        if request.POST.get('action') == 'remove':
            input_dirs.remove(src_path)
            request.session['input_dir'] = input_dirs
            return self._next_destination(request, input_dirs)

        # Accepting a single entry
        asin = request.POST.get('asin', '')

        # Check for validation errors
        if len(errors := Book.objects.book_asin_validator(asin)) > 0:
            for k, v in errors.items():
                messages.error(request, v)
            return redirect("match")

        if not (existing_settings := Setting.objects.first()):
            messages.error(request, "Settings not set")
            return redirect("setting")

        # Check that asin actually returns data from audible
        try:
            helpers.validate_asin(existing_settings.api_url, asin)
        except ValueError:
            messages.error(request, "Bad ASIN: " + asin)
            return redirect("match")

        original_path = Path(src_path)
        if not helpers.get_directory(original_path):
            messages.error(request, f"No supported files in {original_path}")
            return redirect("match")

        logger.info(f"Making models for: {original_path}")
        book = create_book(asin, original_path)
        logger.info(f"Book {book} is now awaiting review")

        input_dirs.remove(src_path)
        request.session['input_dir'] = input_dirs
        return self._next_destination(request, input_dirs)

    @staticmethod
    def _next_destination(request, input_dirs):
        if input_dirs:
            return redirect("match")
        del request.session['input_dir']
        if Book.objects.filter(
                status__status=StatusChoices.PENDING_REVIEW).exists():
            return redirect("review")
        return redirect("import")


class ReviewView(TemplateView):
    template_name = "review.html"

    def get_context_data(self, **kwargs) -> dict:
        pending_books = Book.objects.filter(
            status__status=StatusChoices.PENDING_REVIEW).order_by(
            '-created_at')

        rows = []
        for book in pending_books:
            form = BookMetadataForm(
                prefix=str(book.pk),
                instance=book,
                initial={
                    'authors': ', '.join(
                        str(author) for author in book.authors.all()),
                    'narrators': ', '.join(
                        str(narrator) for narrator in book.narrators.all()),
                }
            )
            rows.append({'book': book, 'form': form})

        return {
            "rows": rows,
            "presets": ConversionPreset.objects.all(),
            "default_preset": ConversionPreset.get_default(),
        }

    def post(self, request: HttpRequest):
        action = request.POST.get('action', '')

        if action.startswith('discard:'):
            book = get_object_or_404(Book, pk=action.split(':', 1)[1])
            logger.info(f"Discarding pending book {book}")
            # Deleting the Status cascades to the Book
            book.status.delete()
            messages.success(request, "Book discarded")
            return redirect("review")

        if action.startswith('approve:'):
            books = [get_object_or_404(Book, pk=action.split(':', 1)[1])]
        elif action == 'approve_all':
            books = list(Book.objects.filter(
                status__status=StatusChoices.PENDING_REVIEW))
        else:
            return HttpResponseBadRequest("Unknown action")

        approved = 0
        for book in books:
            form = BookMetadataForm(
                request.POST, prefix=str(book.pk), instance=book)
            if not form.is_valid():
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(
                            request, f"{book.title}: {field}: {error}")
                continue

            form.save()
            set_book_people(
                book,
                form.cleaned_data.get('authors', ''),
                form.cleaned_data.get('narrators', '')
            )

            if preset_id := request.POST.get(f"{book.pk}-preset"):
                book.preset = ConversionPreset.objects.filter(
                    pk=preset_id).first()
                book.save()

            book.status.status = StatusChoices.PROCESSING
            book.status.save()

            result = m4b_merge_task.delay(book.asin)
            Status.objects.filter(pk=book.status.pk).update(
                task_id=result.id)
            logger.info(f"Approved and queued book {book}")
            approved += 1

        if approved:
            return redirect("books")
        return redirect("review")


class EditBookView(TemplateView):
    template_name = "edit_book.html"

    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        form = BookMetadataForm(
            instance=book,
            initial={
                'authors': ', '.join(
                    str(author) for author in book.authors.all()),
                'narrators': ', '.join(
                    str(narrator) for narrator in book.narrators.all()),
            }
        )
        return render(request, self.template_name,
                      {"book": book, "form": form})

    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        form = BookMetadataForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            set_book_people(
                book,
                form.cleaned_data.get('authors', ''),
                form.cleaned_data.get('narrators', '')
            )
            messages.success(request, f"Saved changes to {book.title}")
            return redirect("books")

        return render(request, self.template_name,
                      {"book": book, "form": form})


class BookStatusView(View):
    def get(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        return JsonResponse({
            'id': book.pk,
            'status': book.status.status,
            'progress_percent': book.status.progress_percent,
            'stage': book.status.stage,
            'message': book.status.message,
        })


class AbandonJobView(View):
    def post(self, request, book_id):
        book = get_object_or_404(Book, pk=book_id)
        status = book.status

        if status.status != StatusChoices.PROCESSING:
            messages.error(request, "Job is not in progress")
            return redirect("books")

        logger.info(f"Abandoning job for {book}")
        Status.objects.filter(pk=status.pk).update(
            cancel_requested=True,
            status=StatusChoices.ABANDONED,
            message="Cancelled by user",
            stage='',
        )

        # Kill the running m4b-tool process tree directly; the celery
        # task also re-checks cancel_requested between stages
        if status.pgid:
            try:
                os.killpg(status.pgid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to process group {status.pgid}")
            except (ProcessLookupError, PermissionError):
                logger.warning(
                    f"Could not signal process group {status.pgid}")

        # Best-effort revoke in case the task is still queued
        if status.task_id:
            celery_app.control.revoke(status.task_id)

        messages.success(request, f"Abandoned job for {book.title}")
        return redirect("books")


class ClearJobsView(View):
    # Clearing removes DB records only; output/source files are untouched
    CLEARABLE = [StatusChoices.DONE, StatusChoices.ERROR,
                 StatusChoices.ABANDONED]

    def post(self, request):
        if clear_all := request.POST.get('clear_all'):
            if clear_all not in self.CLEARABLE:
                return HttpResponseBadRequest("Unknown status")
            statuses = Status.objects.filter(status=clear_all)
        elif book_id := request.POST.get('book_id'):
            statuses = Status.objects.filter(
                book__pk=book_id, status__in=self.CLEARABLE)
        else:
            messages.error(request, "No books selected")
            return redirect("books")

        # Deleting the Status cascades to the Book
        statuses.delete()
        return redirect("books")


class AsinSearch(View):
    def get(self, request):
        accepted_keywords = ["media_dir", "title", "author", "keywords"]

        if any(key not in accepted_keywords for key in request.GET.keys()):
            return HttpResponseBadRequest(
                f"'{', '.join(request.GET.keys() -  accepted_keywords)}' are not valid parameters. \
                Valid search parameters are {accepted_keywords}"
            )

        return self.search(
            request.GET.get("media_dir"),
            request.GET.get("title"),
            request.GET.get("author"),
            request.GET.get("keywords")
        )

    def search(self, media_dir: str = "", title: str = "", author: str = "", keywords: str = "") -> JsonResponse:
        """
            Search for an album.
        """
        # Instantiate search helper
        search_helper = SearchTool(
            filename=media_dir, title=title, author=author, keywords=keywords)

        # Call search API
        results = self.call_search_api(search_helper)

        # Write search result status to log
        if not results:
            logger.warn(
                f'No results found for query {search_helper.normalizedFileName}')
            return JsonResponse([], safe=False)

        logger.debug(
            f'Found {len(results)} result(s) for query "{search_helper.normalizedFileName}"')

        results = self.process_results(search_helper, results)

        return JsonResponse(results, safe=False)

    @staticmethod
    def process_results(helper: SearchTool, result) -> list[dict[str, str | int]]:
        """
            Process the results from the API call.
        """
        scored_results = []
        # Walk the found items and gather extended information
        logger.debug(msg="Search results")
        for index, result_dict in enumerate(result):
            score_helper = ScoreTool(
                helper, index, settings.LANGUAGE_CODE, result_dict)
            scored_results.append(score_helper.run_score_book())

            # Print separators for easy reading
            if index <= len(result):
                logger.debug("-" * 35)

        return sorted(scored_results, key=lambda inf: inf['score'], reverse=True)

    @staticmethod
    def call_search_api(helper: SearchTool):
        '''
            Builds URL then calls API, returns the JSON to helper function.
        '''
        query = helper.build_search_args()
        search_url = helper.build_url(query)
        request = requests.get(search_url)
        return helper.parse_api_response(request.json())


class BookListView(TemplateView):
    template_name = "book_tabs.html"

    def get(self, request):
        done_books = Book.objects.filter(status__status=StatusChoices.DONE).order_by(
            '-created_at')
        processing_books = Book.objects.filter(
            status__status=StatusChoices.PROCESSING).order_by(
            '-created_at')
        error_books = Book.objects.filter(status__status=StatusChoices.ERROR).order_by(
            '-created_at')
        abandoned_books = Book.objects.filter(
            status__status=StatusChoices.ABANDONED).order_by(
            '-created_at')

        return render(request, self.template_name, self.get_context_data(
            done_books=done_books, processing_books=processing_books,
            error_books=error_books, abandoned_books=abandoned_books))

    def get_context_data(self, **kwargs) -> dict:
        context = {"default_view": "done"}

        redirect_url = self.request.META.get('HTTP_REFERER', '')
        if 'match' in redirect_url or 'review' in redirect_url:
            context.update({"default_view": "processing"})

        for key, books in filter(lambda item: 'books' in item[0], kwargs.items()):
            context.update(
                {key: list(zip(books, self.calcBookLength(list(books))))})

        return context

    def calcBookLength(self, books: list[Book]) -> list[str]:
        # Calculate time object into sentence
        length_arr = []
        for book in books:
            d = int(
                timedelta(
                    minutes=book.runtime_length_minutes
                ).total_seconds()
            )
            book_length_calc = (
                f'{d//3600} hrs and {(d//60)%60} minutes'
            )
            length_arr.append(book_length_calc)
        return length_arr


class PresetsView(TemplateView):
    template_name = "presets.html"

    def get_context_data(self, **kwargs):
        edit_id = self.request.GET.get('edit')
        instance = ConversionPreset.objects.filter(pk=edit_id).first() \
            if edit_id else None
        return {
            "presets": ConversionPreset.objects.all().order_by('name'),
            "form": PresetForm(instance=instance),
            "editing": instance,
        }

    def post(self, request):
        action = request.POST.get('action', 'save')

        if action.startswith('delete:'):
            preset = get_object_or_404(
                ConversionPreset, pk=action.split(':', 1)[1])
            was_default = preset.is_default
            preset.delete()
            # Promote another preset so a default always exists
            if was_default and (
                    replacement := ConversionPreset.objects.first()):
                replacement.is_default = True
                replacement.save()
            messages.success(request, f"Deleted preset {preset.name}")
            return redirect("presets")

        preset_id = request.POST.get('preset_id')

        if action == 'set_default':
            preset = get_object_or_404(ConversionPreset, pk=preset_id)
            preset.is_default = True
            # save() clears the flag on every other preset
            preset.save()
            return redirect("presets")

        instance = ConversionPreset.objects.filter(pk=preset_id).first() \
            if preset_id else None
        form = PresetForm(request.POST, instance=instance)
        if form.is_valid():
            preset = form.save()
            # There must always be a default to fall back on
            if not ConversionPreset.objects.filter(is_default=True).exists():
                preset.is_default = True
                preset.save()
            messages.success(request, f"Saved preset {preset.name}")
            return redirect("presets")

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect("presets")


class SettingView(TemplateView):
    template_name = "setting.html"

    def get_context_data(self, **kwargs):
        existing_settings = Setting.objects.first()
        default_data = {
            'api_url': 'https://api.audnex.us',
            'num_cpus': 0,
        }
        if existing_settings:
            form = SettingForm(instance=existing_settings)
        else:
            form = SettingForm(initial=default_data)

        context = {
            "form": form,
            "settings": existing_settings,
        }
        return context

    def post(self, request):
        existing_settings = Setting.objects.first()

        form = SettingForm(request.POST, instance=existing_settings)
        if form.is_valid():
            form.save()
            return redirect("import")

        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        return redirect("setting")
