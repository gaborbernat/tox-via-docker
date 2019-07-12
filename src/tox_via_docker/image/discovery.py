from contextlib import contextmanager
from getpass import getuser
from itertools import chain
from pathlib import Path

from appdirs import user_config_dir
from filelock import FileLock

from tox_via_docker.client import CLIENT

REPOSITORY = "tox-via-docker"


def set_docker_image_tag(image_id, venv):
    if not venv.envconfig.tag:
        generate_docker_image_tag(venv)
    image = CLIENT.images.get(image_id)
    tag = venv.envconfig.tag[len(REPOSITORY) + 1 :]
    image.tag(force=True, repository=REPOSITORY, tag=tag)
    return image


def generate_docker_image_tag(venv):
    project_name = venv.envconfig.config.toxinidir.basename
    tag = f"{REPOSITORY}:{project_name}-{venv.name}"
    with lock_data():
        keys = [
            int(i[len(tag) + 1 :] or 0)
            for i in chain.from_iterable(im.tags for im in CLIENT.images.list(name=REPOSITORY))
            if i.startswith(tag)
        ]
        if keys:
            tag = f"{tag}-{max(keys) + 1}"
        venv.envconfig.labels["tox-via-docker"] = tag
        venv.envconfig.tag = tag


def get_data_folder():
    image_tag_dirs = Path(user_config_dir("tox-via-docker"))
    if not image_tag_dirs.exists():
        image_tag_dirs.mkdir(parents=True)
    return image_tag_dirs


@contextmanager
def lock_data():
    lock = FileLock(get_data_folder() / "tags.lock")
    with lock:
        yield


def generate_tags(venv, config):
    set_docker_image_tag(venv)
    conf = venv.envconfig
    conf.labels = {
        "user": getuser(),
        "folder": str(config.toxinidir),
        "toxenv": conf.envname,
        "tool": self.tox_dpkg_repository,
    }
    images = CLIENT.images.list(
        name=REPOSITORY, filters={"label": ["{}={}".format(k, v) for k, v in conf.labels.items()]}
    )
    conf.image = images[0] if images else None
    conf.tag = images[0].labels["tox-dpkg-tag"] if images else None
    conf.labels["tox-dpkg-tag"] = conf.tag
    if conf.image is None:
        conf.recreate = True  # if cannot find we'll have to recreate
    conf.commands = [
        [c.replace(str(config.toxinidir), str(self.base)) for c in cmd] for cmd in conf.commands
    ]
