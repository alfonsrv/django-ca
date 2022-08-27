# This file is part of django-ca (https://github.com/mathiasertl/django-ca).
#
# django-ca is free software: you can redistribute it and/or modify it under the terms of the GNU
# General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# django-ca is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with django-ca. If not,
# see <http://www.gnu.org/licenses/>.

"""Module to parse ``pyproject.toml`` and augment with auto-generated values."""

from pathlib import Path


def minor_to_major(version: str) -> str:
    """Convert minor to major version."""
    if version.count(".") == 1:
        return version
    return ".".join(version.split(".", 2)[:2])


def get_semantic_version(version=None):
    """Function to get the last git release."""
    # PYLINT NOTE: lazy import so that just importing this module has no external dependencies
    import semantic_version  # pylint: disable=import-outside-toplevel

    if version is None:
        # PYLINT NOTE: import django_ca only here so that it is not imported before coverage tests start
        import django_ca  # pylint: disable=import-outside-toplevel

        version = django_ca.VERSION

    kwargs = {"major": version[0], "minor": version[1], "patch": version[2]}
    if len(version) >= 5:
        kwargs["prerelease"] = tuple(str(e) for e in version[3:5])
        version = version[:3]
    elif len(version) != 3:
        raise ValueError(f"{version}: django_ca.VERSION must have either three or five elements.")

    return semantic_version.Version(**kwargs)


def get_last_version():
    """Get the last version that was released from ``django_ca.VERSION``."""
    version = get_semantic_version()

    # If this is a development release, just remove prerelease/build and return it
    if version.prerelease or version.build:
        version.prerelease = version.build = None
        return version

    if version.patch > 0:
        version.patch -= 1
        return version
    if version.minor > 0:
        version.minor -= 1
        return version
    raise ValueError("Unable to get last release version.")


def get_project_config():
    """Get project configuration from pyproject.toml."""
    # PYLINT NOTE: lazy import so that just importing this module has no external dependencies
    import toml  # pylint: disable=import-outside-toplevel

    with open(PYPROJECT_PATH, encoding="utf-8") as stream:
        full_config = toml.load(stream)

    config = full_config["django-ca"]["release"]
    config["python-map"] = {minor_to_major(pyver): pyver for pyver in config["python"]}
    config["python-major"] = [minor_to_major(pyver) for pyver in config["python"]]
    config["django-map"] = {minor_to_major(djver): djver for djver in config["django"]}
    config["django-major"] = [minor_to_major(djver) for djver in config["django"]]
    config["cryptography-map"] = {minor_to_major(cgver): cgver for cgver in config["cryptography"]}
    config["cryptography-major"] = [minor_to_major(cgver) for cgver in config["cryptography"]]
    config["acme-map"] = {minor_to_major(acmever): acmever for acmever in config["acme"]}
    config["acme-major"] = [minor_to_major(acmever) for acmever in config["acme"]]
    config["josepy-map"] = {minor_to_major(josepyver): josepyver for josepyver in config["josepy"]}
    config["josepy-major"] = [minor_to_major(josepyver) for josepyver in config["josepy"]]

    config["docker"] = full_config["django-ca"].setdefault("docker", {})
    _alpine_images = config["docker"].setdefault("alpine-images", [])
    if "default" not in _alpine_images:
        _alpine_images.append("default")

    config["docker"][
        "metavar"
    ] = "default|python:{%s-%s}-alpine{%s-%s}" % (  # pylint: disable=consider-using-f-string
        config["python-major"][0],
        config["python-major"][-1],
        config["alpine"][0],
        config["alpine"][-1],
    )
    for pyver in reversed(config["python-major"]):
        for alpver in reversed(config["alpine"]):
            # Skip images that are just no longer built upstream
            if (pyver, alpver) in [("3.10", "3.12")]:
                continue

            if f"python:{pyver}-alpine{alpver}" not in _alpine_images:
                _alpine_images.append(f"python:{pyver}-alpine{alpver}")
    return config


BASE_DIR = Path(__file__).resolve()
ROOT_DIR = Path(BASE_DIR).parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
DOCS_DIR = Path(ROOT_DIR) / "docs"
DOCS_BUILD_DIR = DOCS_DIR / "build"
DOCS_SOURCE_DIR = DOCS_DIR / "source"
DOC_TEMPLATES_DIR = DOCS_SOURCE_DIR / "include"
SRC_DIR = ROOT_DIR / "ca"
MANAGE_PY = SRC_DIR / "manage.py"
FIXTURES_DIR = SRC_DIR / "django_ca" / "tests" / "fixtures"
DOCKER_TAG = "mathiasertl/django-ca"