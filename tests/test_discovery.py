# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import sys

from oca_github_bot import custom, registry
from oca_github_bot.discovery import import_submodules


def test_custom_package_is_discovered_not_listed():
    # the custom package exists and is imported at startup, so that a custom
    # action is added by dropping in a file
    assert custom.__name__ == "oca_github_bot.custom"
    assert "oca_github_bot.custom" in sys.modules


def test_import_submodules_imports_every_module(tmp_path, monkeypatch):
    package = tmp_path / "throwaway_package"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "a_feature.py").write_text(
        "from oca_github_bot import registry\n"
        "registry.register('a_feature', default=False)\n"
    )
    (package / "_private.py").write_text("raise AssertionError('not imported')\n")
    (package / "base.py").write_text("raise AssertionError('not imported')\n")
    monkeypatch.syspath_prepend(str(tmp_path))

    saved = registry.snapshot()
    try:
        imported = import_submodules(
            "throwaway_package", [str(package)], skip=("base",)
        )
        assert imported == ["a_feature"]
        # a custom capability is registered, but opted out of the default set
        assert registry.get("a_feature").default is False
        assert "a_feature" not in registry.default_names()
    finally:
        registry.restore(saved)
        for name in list(sys.modules):
            if name.startswith("throwaway_package"):
                del sys.modules[name]
