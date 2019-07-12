import json
import pipes
import platform
import re
import textwrap
from itertools import chain
from pathlib import Path

from tox import reporter
from tox.config import DepConfig
from tox.exception import InvocationError

from ..client import CLIENT

_BUILT_IMAGES = set()


def build_image(venv, context, action):
    create_docker_file(context, venv)
    # host -> Linux access local pip
    generator = CLIENT.api.build(path=str(context), rm=True, network_mode="host")
    image_id = None
    while True:
        output = None
        try:
            output = next(generator)
            message = ""
            for fragment in output.decode().split("\r\n"):
                if fragment:
                    msg = json.loads(fragment)
                    if "stream" in msg:
                        msg = msg["stream"]
                        match = re.search(r"(^Successfully built |sha256:)([0-9a-f]+)$", msg)
                        if match:
                            image_id = match.group(2)
                    else:
                        msg = fragment
                    message += msg
            message = "".join(message).strip("\n")
            reporter.verbosity1(message)
        except StopIteration:
            reporter.info("Docker image build complete.")
            break
        except ValueError:  # pragma: no cover
            reporter.error(
                "Error parsing output from docker image build: {}".format(output)
            )  # pragma: no cover
    if image_id is None:
        raise InvocationError("docker image build failed")  # pragma: no cover
    _BUILT_IMAGES.add(image_id)
    return image_id


def create_docker_file(context, venv):
    mount = venv.envconfig.mount
    venv.envconfig.labels = {}
    content = textwrap.dedent(
        f"""
        FROM {venv.envconfig.base_repository}:{venv.envconfig.base_tag}
        WORKDIR {mount}
        {'ENV PIP_TRUSTED_HOST host.docker.internal' if platform.system() == "Darwin" else ''}

        RUN pip install pip setuptools wheel
    """
    ).lstrip()

    pip_install = get_pip_install(venv, venv.envconfig.deps)
    if pip_install:
        content += f"RUN {quote_command(pip_install)}\n"

    project_install = get_project_install(venv, mount, overwrite=context)
    if project_install:
        content += f"COPY . {mount}\n"
    if project_install:
        content += f"RUN {quote_command(project_install)}\n"
        content += f'RUN python -c "import shutil; shutil.rmtree({mount})"\n'
    if venv.envconfig.labels:
        labels = " ".join(f"{k}={v}" for k, v in venv.envconfig.labels.items())
        content += f"LABELS {labels}\n"
    Path("Dockerfile").write_text(content)
    return content


def get_project_install(venv, mount, no_deps=False, overwrite=None):
    if venv.envconfig.skip_install or venv.envconfig.config.skipsdist:
        return None
    if venv.envconfig.usedevelop and venv.envconfig.skip_install is False:
        what = mount  # install the folder itself
    else:
        if overwrite is None:
            what = mount.join(
                venv.package.relto(venv.envconfig.config.toxinidir)
            )  # install relative to root
        else:
            what = mount.join(venv.package.basename)  # package at root level in folder
    what = str(what)
    if venv.envconfig.extras:
        what = f'{what}[{",".join(venv.envconfig.extras)}]'
    pip_install = get_pip_install(venv, [DepConfig(what, None)])
    if no_deps:
        pip_install.append("--no-deps")
    return pip_install


def get_pip_install(venv, packages, use_develop=False):
    flags = ["-e"] if use_develop else []
    flags.extend(["-v"] * min(3, reporter.verbosity() - 2))
    if not packages:
        return None
    pip_install = list(venv.envconfig.install_command)
    try:
        index = pip_install.index("{opts}")
        pip_install = list(chain(pip_install[:index], flags, pip_install[index + 1 :]))
    except ValueError:  # pragma: no cover
        pass  # pragma: no cover
    try:
        index = pip_install.index("{packages}")
        pip_install = list(
            chain(pip_install[:index], (i.name for i in packages), pip_install[index + 1 :])
        )
    except ValueError:  # pragma: no cover
        pass  # pragma: no cover
    if "PIP_INDEX_URL" in venv.env:
        index_url = venv.env["PIP_INDEX_URL"]
        pip_install.extend(("-i", index_url))
    return pip_install


def quote_command(dpkg_targets):
    return " ".join(pipes.quote(i) for i in dpkg_targets)
