import json
import logging
import os
import socket
import sys
import typing
from copy import deepcopy
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest
import yaml
from asgiref.typing import ASGIApplication, ASGIReceiveCallable, ASGISendCallable, Scope
from pytest_mock import MockerFixture

from esg._types import Environ, StartResponse
from esg.config import LOGGING_CONFIG, Config
from esg.middleware.debug import DebugMiddleware
from esg.middleware.proxy_headers import ProxyHeadersMiddleware
from esg.middleware.wsgi import WSGIMiddleware
from tests.utils import as_cwd


@pytest.fixture
def mocked_logging_config_module(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("logging.config")


@pytest.fixture(scope="function")
def logging_config() -> dict:
    return deepcopy(LOGGING_CONFIG)


@pytest.fixture
def json_logging_config(logging_config: dict) -> str:
    return json.dumps(logging_config)


@pytest.fixture
def yaml_logging_config(logging_config: dict) -> str:
    return yaml.dump(logging_config)


async def asgi_app(
    scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
) -> None:
    pass  # pragma: nocover


def wsgi_app(environ: Environ, start_response: StartResponse) -> None:
    pass  # pragma: nocover


def test_debug_app() -> None:
    config = Config(app=asgi_app, debug=True, proxy_headers=False)
    config.load()

    assert config.debug is True
    assert isinstance(config.loaded_app, DebugMiddleware)


@pytest.mark.parametrize(
    "app, expected_should_reload",
    [(asgi_app, False), ("tests.test_config:asgi_app", True)],
)
def test_config_should_reload_is_set(
    app: ASGIApplication, expected_should_reload: bool
) -> None:
    config_debug = Config(app=app, debug=True)
    assert config_debug.debug is True
    assert config_debug.should_reload is expected_should_reload

    config_reload = Config(app=app, reload=True)
    assert config_reload.reload is True
    assert config_reload.should_reload is expected_should_reload


def test_should_warn_on_invalid_reload_configuration(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    config_class = Config(app=asgi_app, reload_dirs=[str(tmp_path)])
    assert not config_class.should_reload
    assert len(caplog.records) == 1
    assert (
        caplog.records[-1].message
        == "Current configuration will not reload as not all conditions are met,"
        "please refer to documentation."
    )

    config_no_reload = Config(
        app="tests.test_config:asgi_app", reload_dirs=[str(tmp_path)]
    )
    assert not config_no_reload.should_reload
    assert len(caplog.records) == 2
    assert (
        caplog.records[-1].message
        == "Current configuration will not reload as not all conditions are met,"
        "please refer to documentation."
    )


def test_reload_dir_is_set(
    reload_directory_structure: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app_dir = reload_directory_structure / "app"
    with caplog.at_level(logging.INFO):
        config = Config(
            app="tests.test_config:asgi_app", reload=True, reload_dirs=[str(app_dir)]
        )
        assert len(caplog.records) == 1
        assert (
            caplog.records[-1].message
            == f"Will watch for changes in these directories: {[str(app_dir)]}"
        )
        assert config.reload_dirs == [app_dir]
        config = Config(
            app="tests.test_config:asgi_app", reload=True, reload_dirs=str(app_dir)
        )
        assert config.reload_dirs == [app_dir]


def test_non_existant_reload_dir_is_not_set(
    reload_directory_structure: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with as_cwd(reload_directory_structure), caplog.at_level(logging.WARNING):
        config = Config(
            app="tests.test_config:asgi_app", reload=True, reload_dirs=["reload"]
        )
        assert config.reload_dirs == [reload_directory_structure]
        assert (
            caplog.records[-1].message
            == "Provided reload directories ['reload'] did not contain valid "
            + "directories, watching current working directory."
        )


def test_reload_subdir_removal(reload_directory_structure: Path) -> None:
    app_dir = reload_directory_structure / "app"

    reload_dirs = [str(reload_directory_structure), "app", str(app_dir)]

    with as_cwd(reload_directory_structure):
        config = Config(
            app="tests.test_config:asgi_app", reload=True, reload_dirs=reload_dirs
        )
        assert config.reload_dirs == [reload_directory_structure]


def test_reload_included_dir_is_added_to_reload_dirs(
    reload_directory_structure: Path,
) -> None:
    app_dir = reload_directory_structure / "app"
    ext_dir = reload_directory_structure / "ext"

    with as_cwd(reload_directory_structure):
        config = Config(
            app="tests.test_config:asgi_app",
            reload=True,
            reload_dirs=[str(app_dir)],
            reload_includes=["*.js", str(ext_dir)],
        )
        assert frozenset(config.reload_dirs), frozenset([app_dir, ext_dir])
        assert frozenset(config.reload_includes) == frozenset(["*.js", str(ext_dir)])


def test_reload_dir_subdirectories_are_removed(
    reload_directory_structure: Path,
) -> None:
    app_dir = reload_directory_structure / "app"
    app_sub_dir = app_dir / "sub"
    ext_dir = reload_directory_structure / "ext"
    ext_sub_dir = ext_dir / "sub"

    with as_cwd(reload_directory_structure):
        config = Config(
            app="tests.test_config:asgi_app",
            reload=True,
            reload_dirs=[
                str(app_dir),
                str(app_sub_dir),
                str(ext_sub_dir),
                str(ext_dir),
            ],
        )
        assert frozenset(config.reload_dirs) == frozenset([app_dir, ext_dir])


def test_reload_excluded_subdirectories_are_removed(
    reload_directory_structure: Path,
) -> None:
    app_dir = reload_directory_structure / "app"
    app_sub_dir = app_dir / "sub"

    with as_cwd(reload_directory_structure):
        config = Config(
            app="tests.test_config:asgi_app",
            reload=True,
            reload_excludes=[str(app_dir), str(app_sub_dir)],
        )
        assert frozenset(config.reload_dirs) == frozenset([reload_directory_structure])
        assert frozenset(config.reload_dirs_excludes) == frozenset([app_dir])
        assert frozenset(config.reload_excludes) == frozenset(
            [str(app_dir), str(app_sub_dir)]
        )


def test_reload_includes_exclude_dir_patterns_are_matched(
    reload_directory_structure: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        first_app_dir = reload_directory_structure / "app_first" / "src"
        second_app_dir = reload_directory_structure / "app_second" / "src"

        with as_cwd(reload_directory_structure):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_includes=["*/src"],
                reload_excludes=["app", "*third*"],
            )
            assert len(caplog.records) == 1
            assert (
                caplog.records[-1].message
                == "Will watch for changes in these directories: "
                f"{sorted([str(first_app_dir), str(second_app_dir)])}"
            )
            assert frozenset(config.reload_dirs) == frozenset(
                [first_app_dir, second_app_dir]
            )
            assert config.reload_includes == ["*/src"]


def test_wsgi_app() -> None:
    config = Config(app=wsgi_app, interface="wsgi", proxy_headers=False)
    config.load()

    assert isinstance(config.loaded_app, WSGIMiddleware)
    assert config.interface == "wsgi"
    assert config.asgi_version == "3.0"


def test_proxy_headers() -> None:
    config = Config(app=asgi_app)
    config.load()

    assert config.proxy_headers is True
    assert isinstance(config.loaded_app, ProxyHeadersMiddleware)


def test_app_unimportable_module() -> None:
    config = Config(app="no.such:app")
    with pytest.raises(ImportError):
        config.load()


def test_app_unimportable_other(caplog: pytest.LogCaptureFixture) -> None:
    config = Config(app="tests.test_config:app")
    with pytest.raises(SystemExit):
        config.load()
    error_messages = [
        record.message
        for record in caplog.records
        if record.name == "esg.error" and record.levelname == "ERROR"
    ]
    assert (
        'Error loading ASGI app. Attribute "app" not found in module "tests.test_config".'  # noqa: E501
        == error_messages.pop(0)
    )


def test_app_factory(caplog: pytest.LogCaptureFixture) -> None:
    def create_app() -> ASGIApplication:
        return asgi_app

    config = Config(app=create_app, factory=True, proxy_headers=False)
    config.load()
    assert config.loaded_app is asgi_app

    # Flag not passed. In this case, successfully load the app, but issue a warning
    # to indicate that an explicit flag is preferred.
    caplog.clear()
    config = Config(app=create_app, proxy_headers=False)
    with caplog.at_level(logging.WARNING):
        config.load()
    assert config.loaded_app is asgi_app
    assert len(caplog.records) == 1
    assert "--factory" in caplog.records[0].message

    # App not a no-arguments callable.
    config = Config(app=asgi_app, factory=True)
    with pytest.raises(SystemExit):
        config.load()


def test_socket_bind() -> None:
    config = Config(app=asgi_app)
    config.load()
    sock = config.bind_socket()
    assert isinstance(sock, socket.socket)
    sock.close()


def test_ssl_config(
    tls_ca_certificate_pem_path: str,
    tls_ca_certificate_private_key_path: str,
) -> None:
    config = Config(
        app=asgi_app,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_keyfile=tls_ca_certificate_private_key_path,
    )
    config.load()

    assert config.is_ssl is True


def test_ssl_config_combined(tls_certificate_key_and_chain_path: str) -> None:
    config = Config(
        app=asgi_app,
        ssl_certfile=tls_certificate_key_and_chain_path,
    )
    config.load()

    assert config.is_ssl is True


def asgi2_app(scope: Scope) -> typing.Callable:
    async def asgi(
        receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:  # pragma: nocover
        pass

    return asgi  # pragma: nocover


@pytest.mark.parametrize(
    "app, expected_interface", [(asgi_app, "3.0"), (asgi2_app, "2.0")]
)
def test_asgi_version(
    app: ASGIApplication, expected_interface: Literal["2.0", "3.0"]
) -> None:
    config = Config(app=app)
    config.load()
    assert config.asgi_version == expected_interface


@pytest.mark.parametrize(
    "use_colors, expected",
    [
        pytest.param(None, None, id="use_colors_not_provided"),
        pytest.param("invalid", None, id="use_colors_invalid_value"),
        pytest.param(True, True, id="use_colors_enabled"),
        pytest.param(False, False, id="use_colors_disabled"),
    ],
)
def test_log_config_default(
    mocked_logging_config_module: MagicMock,
    use_colors: typing.Optional[bool],
    expected: typing.Optional[bool],
) -> None:
    """
    Test that one can specify the use_colors option when using the default logging
    config.
    """
    config = Config(app=asgi_app, use_colors=use_colors)
    config.load()

    mocked_logging_config_module.dictConfig.assert_called_once_with(LOGGING_CONFIG)

    (provided_dict_config,), _ = mocked_logging_config_module.dictConfig.call_args
    assert provided_dict_config["formatters"]["default"]["use_colors"] == expected


def test_log_config_json(
    mocked_logging_config_module: MagicMock,
    logging_config: dict,
    json_logging_config: str,
    mocker: MockerFixture,
) -> None:
    """
    Test that one can load a json config from disk.
    """
    mocked_open = mocker.patch(
        "esg.config.open", mocker.mock_open(read_data=json_logging_config)
    )

    config = Config(app=asgi_app, log_config="log_config.json")
    config.load()

    mocked_open.assert_called_once_with("log_config.json")
    mocked_logging_config_module.dictConfig.assert_called_once_with(logging_config)


@pytest.mark.parametrize("config_filename", ["log_config.yml", "log_config.yaml"])
def test_log_config_yaml(
    mocked_logging_config_module: MagicMock,
    logging_config: dict,
    yaml_logging_config: str,
    mocker: MockerFixture,
    config_filename: str,
) -> None:
    """
    Test that one can load a yaml config from disk.
    """
    mocked_open = mocker.patch(
        "esg.config.open", mocker.mock_open(read_data=yaml_logging_config)
    )

    config = Config(app=asgi_app, log_config=config_filename)
    config.load()

    mocked_open.assert_called_once_with(config_filename)
    mocked_logging_config_module.dictConfig.assert_called_once_with(logging_config)


def test_log_config_file(mocked_logging_config_module: MagicMock) -> None:
    """
    Test that one can load a configparser config from disk.
    """
    config = Config(app=asgi_app, log_config="log_config")
    config.load()

    mocked_logging_config_module.fileConfig.assert_called_once_with(
        "log_config", disable_existing_loggers=False
    )


@pytest.fixture(params=[0, 1])
def web_concurrency(request: pytest.FixtureRequest) -> typing.Iterator[int]:
    yield getattr(request, "param")
    if os.getenv("WEB_CONCURRENCY"):
        del os.environ["WEB_CONCURRENCY"]


@pytest.fixture(params=["127.0.0.1", "127.0.0.2"])
def forwarded_allow_ips(request: pytest.FixtureRequest) -> typing.Iterator[str]:
    yield getattr(request, "param")
    if os.getenv("FORWARDED_ALLOW_IPS"):
        del os.environ["FORWARDED_ALLOW_IPS"]


def test_env_file(
    web_concurrency: int,
    forwarded_allow_ips: str,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """
    Test that one can load environment variables using an env file.
    """
    fp = tmp_path / ".env"
    content = (
        f"WEB_CONCURRENCY={web_concurrency}\n"
        f"FORWARDED_ALLOW_IPS={forwarded_allow_ips}\n"
    )
    fp.write_text(content)
    with caplog.at_level(logging.INFO):
        config = Config(app=asgi_app, env_file=fp)
        config.load()

    assert config.workers == int(str(os.getenv("WEB_CONCURRENCY")))
    assert config.forwarded_allow_ips == os.getenv("FORWARDED_ALLOW_IPS")
    assert len(caplog.records) == 1
    assert f"Loading environment from '{fp}'" in caplog.records[0].message


@pytest.mark.parametrize(
    "access_log, handlers",
    [
        pytest.param(True, 1, id="access log enabled should have single handler"),
        pytest.param(False, 0, id="access log disabled shouldn't have handlers"),
    ],
)
def test_config_access_log(access_log: bool, handlers: int) -> None:
    config = Config(app=asgi_app, access_log=access_log)
    config.load()

    assert len(logging.getLogger("esg.access").handlers) == handlers
    assert config.access_log == access_log


@pytest.mark.parametrize("log_level", [5, 10, 20, 30, 40, 50])
def test_config_log_level(log_level: int) -> None:
    config = Config(app=asgi_app, log_level=log_level)
    config.load()

    assert logging.getLogger("esg.error").level == log_level
    assert logging.getLogger("esg.access").level == log_level
    assert logging.getLogger("esg.asgi").level == log_level
    assert config.log_level == log_level


def test_ws_max_size() -> None:
    config = Config(app=asgi_app, ws_max_size=1000)
    config.load()
    assert config.ws_max_size == 1000


@pytest.mark.parametrize(
    "reload, workers",
    [
        (True, 1),
        (False, 2),
    ],
    ids=["--reload=True --workers=1", "--reload=False --workers=2"],
)
@pytest.mark.skipif(
    sys.platform in ("win32", "darwin"), reason="require unix-like system"
)
def test_bind_unix_socket_works_with_reload_or_workers(
    tmp_path, reload, workers
):  # pragma: py-win32
    uds_file = tmp_path / "esg.sock"
    config = Config(
        app=asgi_app, uds=uds_file.as_posix(), reload=reload, workers=workers
    )
    config.load()
    sock = config.bind_socket()
    assert isinstance(sock, socket.socket)
    assert sock.family == socket.AF_UNIX
    assert sock.getsockname() == uds_file.as_posix()
    sock.close()


@pytest.mark.parametrize(
    "reload, workers",
    [
        (True, 1),
        (False, 2),
    ],
    ids=["--reload=True --workers=1", "--reload=False --workers=2"],
)
@pytest.mark.skipif(
    sys.platform in ("win32", "darwin"), reason="require unix-like system"
)
def test_bind_fd_works_with_reload_or_workers(reload, workers):  # pragma: py-win32
    fdsock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    fd = fdsock.fileno()
    config = Config(app=asgi_app, fd=fd, reload=reload, workers=workers)
    config.load()
    sock = config.bind_socket()
    assert isinstance(sock, socket.socket)
    assert sock.family == socket.AF_UNIX
    assert sock.getsockname() == ""
    sock.close()
    fdsock.close()
