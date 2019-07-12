import os
import shutil
import tempfile
from contextlib import contextmanager

from tox import reporter

from tox_via_docker.client import CLIENT

from .build import build_image
from .discovery import set_docker_image_tag


def tox_testenv_create(venv, action):
    """
    Python is already installed, we just need to handle dependency installs, there are two major phases, we take
    care of 1 here:

    1. extend base image -> create env image
       1. install pip/setuptools/wheel
       2. install dependencies
       3. develop -> copy folder - install via -e
          non-develop -> copy sdist - install
    2. run:
        1. start container from env image and mount {toxinidir} under
        2. install package (either develop or sdist)
        3. run commands one by one
        4. stop and remove container
    """
    with safe_package_view(venv) as context:
        cwd = os.getcwd()
        os.chdir(context)
        try:
            image_id = build_image(venv, context, action)
        except Exception as exception:
            reporter.error(f"could not build image {exception}")  # pragma: no cover
            raise  # pragma: no cover
        finally:
            os.chdir(cwd)

    image = set_docker_image_tag(image_id, venv)
    if venv.envconfig.image is not None:  # already had a previous image (e.g. different python)
        try:
            CLIENT.images.remove(image=venv.envconfig.image.id, force=True)
        except Exception as exception:  # pragma: no cover
            reporter.warning(f"could not delete image {exception}")  # pragma: no cover
    venv.envconfig.image = image
    return True


@contextmanager
def safe_package_view(venv):
    with tempfile.TemporaryDirectory() as temp_dir:
        if venv.envconfig.usedevelop and venv.envconfig.skip_install is False:
            # in develop mode we want to copy the entire project - simulate poor mans docker ignore by copy
            into = os.path.join(temp_dir)
            shutil.copytree(
                str(venv.envconfig.config.toxinidir),
                into,
                ignore=shutil.ignore_patterns(".tox", "*.pyc", "__pycache__", "*.egg-info"),
            )
            yield into
        elif hasattr(venv, "package"):
            # if it's an sdist install we just need that one package as a link
            os.link(venv.package, os.path.join(venv.package.basename))
            yield temp_dir
        else:
            yield temp_dir
