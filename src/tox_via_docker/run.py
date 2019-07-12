import tempfile
from contextlib import contextmanager

from dockerpty import ExecOperation, PseudoTerminal
from tox import reporter
from tox.exception import InvocationError

from .client import CLIENT


def tox_runtest(venv, redirect):
    pass


@contextmanager
def inside_container(image, mount_local=None, mount_to=None):
    container = start_container(image, mount_local, mount_to)
    try:
        yield container
    finally:
        stop_container(container)


def stop_container(container):
    reporter.verbosity1(f"stop container via {container.short_id} ({container.attrs['Name']})")
    container.stop(timeout=0)
    container.remove()


def start_container(image, mount_local=None, mount_to=None):
    try:
        container = CLIENT.containers.create(
            image,
            command=["sleep", "infinity"],
            auto_remove=False,
            detach=True,
            network_mode="host",
            volumes={mount_local: {"bind": str(mount_to), "mode": "Z"}}
            if mount_to and mount_local
            else None,
        )
    except Exception as exception:
        reporter.error(repr(exception))
        raise
    reporter.verbosity1(
        f"start container via {container.short_id} ({container.attrs['Name']}) based on {image}"
    )
    container.start()
    return container


def run_in_container(
    container, cmd, interactive=False, ignore_ret=False, env=None, attach_to_stdin=False, cwd=None
):
    output = None
    docker_id = container.short_id
    try:
        exec_id = CLIENT.api.exec_create(
            docker_id,
            cmd,
            environment=env,
            workdir=cwd,
            stdin=interactive,
            tty=interactive,
            stdout=True,
            stderr=True,
        )
        if interactive:
            stdin = None
            if attach_to_stdin is False:
                stdin = tempfile.SpooledTemporaryFile(
                    mode="r+b"
                )  # a mock file to bypass connection
            try:
                operation = ExecOperation(
                    CLIENT.api, exec_id, interactive=stdin is None, stdin=stdin
                )
                PseudoTerminal(CLIENT, operation).start()
            finally:
                if stdin is not None:
                    stdin.close()
        else:
            output = CLIENT.api.exec_start(exec_id["Id"], detach=False, tty=False).decode("utf-8")
        exit_info = CLIENT.api.exec_inspect(exec_id)
        exit_success = exit_info["Running"] is False and (exit_info["ExitCode"] == 0 or ignore_ret)
        if not exit_success:
            raise DockerInvocationFailed(
                cmd, exit_info["ExitCode"], output or repr(exit_info), docker_id
            )
    except DockerInvocationFailed:  # pragma: no cover
        raise  # pragma: no cover
    except Exception as exception:  # pragma: no cover
        raise DockerInvocationFailed(cmd, -2, repr(exception), docker_id)  # pragma: no cover
    return output


class DockerInvocationFailed(InvocationError):
    def __init__(self, command, exit_code, out, docker_id):
        self.id = docker_id
        super().__init__(command, exit_code)
        self.out = out

    def __repr__(self):
        return (
            f"DockerInvocationFailed(command={self.command!r}, exit_code={self.exit_code!r}, out={self.out!r},"
            f" id={self.id!r})"
        )
