from typer.testing import CliRunner

from fpl_engine import __version__
from fpl_engine.cli import app

runner = CliRunner()


def test_version_command_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_info_command_prints_resolved_settings() -> None:
    result = runner.invoke(app, ["info"])

    assert result.exit_code == 0
    assert "environment" in result.stdout
    assert "data_dir" in result.stdout


def test_no_args_shows_help_instead_of_erroring() -> None:
    result = runner.invoke(app, [])

    # Click/Typer convention: no_args_is_help prints help but still exits 2.
    # We assert the help text renders, not exit_code 0 — the point of this
    # test is "does it crash / print a traceback," which it doesn't.
    assert result.exit_code == 2
    assert "Usage" in result.stdout
