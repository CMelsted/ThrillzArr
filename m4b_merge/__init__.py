# Vendored from djdembeck/m4b-merge tag v0.5.3-python-final
# (the last Python release before the upstream Rust rewrite).
# Local modifications:
#   - config.py: missing binaries warn at import and raise at merge time,
#     instead of SystemExit at import time
#   - m4b_helper.py: subprocess.call replaced with Popen in a new session,
#     exposing the process group id for cancellation; run_merge() split into
#     separately-callable stages
__version__ = '0.5.3+thrillzarr'
