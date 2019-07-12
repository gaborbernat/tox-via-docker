import pluggy

from .config import tox_addoption, tox_configure
from .image.base import tox_get_python_executable
from .image.env import tox_testenv_create
from .run import tox_runtest

hookimpl = pluggy.HookimplMarker("tox")


for func in (
    tox_addoption,
    tox_configure,
    tox_get_python_executable,
    tox_testenv_create,
    tox_runtest,
):
    hookimpl(func)

globals().pop("func")
