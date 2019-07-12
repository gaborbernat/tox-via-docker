import atexit

import docker

CLIENT = docker.from_env()

atexit.register(CLIENT.close)
