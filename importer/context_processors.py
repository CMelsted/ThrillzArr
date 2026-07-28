from django import get_version
from m4b_merge import __version__ as m4b_merge_version
from .version import __version__


def add_version_to_context(request):
    return {
        'bragibooks_version': __version__,
        'django_version': get_version(),
        'm4b_merge_version': m4b_merge_version
    }
