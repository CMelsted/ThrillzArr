from .version import __version__


def add_version_to_context(request):
    return {'app_version': __version__}
