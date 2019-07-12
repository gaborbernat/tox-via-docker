import inspect
import os
import re
import sys

from tox import reporter
from tox.interpreters import PythonInfo
from tox.interpreters.discovery import PythonSpec

from ..client import CLIENT
from ..run import DockerInvocationFailed, inside_container, run_in_container

PYTHON_INFO_AT = inspect.getabsfile(PythonInfo)


def get_image(repository, tag):
    return CLIENT.images.pull(repository, tag), (repository, tag)


def docker_image(conf):
    match = re.match(
        r"(\w*[a-zA-Z])(\d)?(?:\.(\d))?(-(32|64))?",
        "python" if conf.basepython == sys.executable else conf.basepython,
    )
    name, major, minor, architecture = None, sys.version_info[0], sys.version_info[1], None
    if match:
        groups = match.groups()
        name = groups[0]
        if len(groups) >= 2 and groups[1] is not None:
            major = int(groups[1])
        if len(groups) >= 3 and groups[2] is not None:
            minor = int(groups[2])
        architecture = int(groups[3]) if len(groups) >= 4 and groups[3] is not None else None
    repository = conf.repository
    tag = ""
    if major:
        tag += f"{major}"
    if minor:
        tag += f".{minor}"
    if conf.tag_postfix:
        tag += f"-{conf.tag_postfix}"
    return get_image(repository, tag)


def tox_get_python_executable(envconfig):
    envconfig.docker_image, (envconfig.base_repository, envconfig.base_tag) = docker_image(
        envconfig
    )
    name = envconfig.basepython
    mount_folder = os.path.dirname(PYTHON_INFO_AT)
    mount_to = "/w"
    with inside_container(
        envconfig.docker_image, mount_local=mount_folder, mount_to=mount_to
    ) as container:
        try:
            output = run_in_container(
                container, ["python", os.path.join(mount_to, os.path.basename(PYTHON_INFO_AT))]
            )
        except DockerInvocationFailed as exception:
            spec = PythonSpec.from_string_spec(name)
            reporter.verbosity1(
                "failed getting tox env for {} because {!r}".format(name, exception)
            )
            return spec
    info = PythonInfo.from_json(output)
    envconfig.env_prefix = info.prefix
    envconfig.interpreter = info
    return info.executable
