"""Regression checks for the documented local launcher/configuration path."""

from pathlib import Path

from horolog.settings import ENV_FILES, PROJECT_ROOT


def test_documented_root_dotenv_is_loaded() -> None:
    assert PROJECT_ROOT / ".env" in ENV_FILES
    assert (PROJECT_ROOT / "README.md").is_file(), "PROJECT_ROOT must point at the checkout root"


def test_api_local_dotenv_can_override_the_root_file() -> None:
    assert ENV_FILES[-1] == Path(".env")
