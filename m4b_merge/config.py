from pathlib import Path
import logging
import shutil
from appdirs import user_config_dir

# config section for docker
if Path('/config').is_dir():
    config_path = Path('/config')
else:
    appname = "m4b-merge"
    config_path = Path(user_config_dir(appname))
    Path(config_path).mkdir(
        parents=True,
        exist_ok=True
    )

# Find paths to m4b-tool/mp4chaps binaries.
# Missing binaries are tolerated at import time so that management
# commands (migrations, tests) can run outside the full runtime image;
# require_binaries() enforces their presence before any merge runs.
m4b_tool_bin = shutil.which('m4b-tool')
if not m4b_tool_bin:
    logging.warning(
        'Cannot find m4b-tool binary; merges will fail until it is installed.'
    )

mp4chaps_bin = shutil.which('mp4chaps')
if not mp4chaps_bin:
    logging.warning(
        'Cannot find mp4chaps binary; merges will fail until it is installed.'
    )


def require_binaries():
    if not m4b_tool_bin:
        raise RuntimeError('Cannot find m4b-tool binary.')
    if not mp4chaps_bin:
        raise RuntimeError('Cannot find mp4chaps binary.')
