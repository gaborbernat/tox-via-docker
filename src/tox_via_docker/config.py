from .image.discovery import generate_tags


def tox_addoption(parser):
    """Add a command line option for later use"""
    parser.add_argument(
        "--repository", action="store", help="this is a magical option", default="python"
    )
    parser.add_testenv_attribute(
        name="repository",
        type="string",
        default=None,
        help="docker repository to run",
        postprocess=lambda testenv_config, value: testenv_config.config.option.repository
        if value is None
        else value,
    )
    parser.add_testenv_attribute(
        name="tag_postfix", type="string", default=None, help="docker tag postfix"
    )
    parser.add_testenv_attribute(
        name="mount", type="string", default="/opt/project", help="work dir"
    )


def tox_configure(config):
    for venv in config.envconfigs.values():
        generate_tags(venv, config)
