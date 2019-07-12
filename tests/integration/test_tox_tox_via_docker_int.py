def test_run_just_run(initproj, cmd):
    initproj(
        "pkg123-0.7",
        filedefs={
            "tox.ini": """
                [tox]
                envlist = py
                skipsdist = True

                [testenv]
                description = {envname} {envdir} {envtmpdir} {envlogdir} {envpython} {envbindir} {envsitepackagesdir}
                commands=python -c "import sys; print(sys.platform())"

            """
        },
    )
    result = cmd("-vvv")
    result.assert_success(is_run_test_env=True)
    assert result.out
