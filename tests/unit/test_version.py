def test_version():
    pkg = __import__("tox_via_docker", fromlist=["__version__"])
    assert pkg.__version__
