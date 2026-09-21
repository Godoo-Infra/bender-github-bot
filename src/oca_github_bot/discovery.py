# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Import every module of a package, so that its contents register themselves.

Used by the packages meant to be extended by adding a file -- ``commands`` and
``custom`` -- rather than listing their modules by hand as ``tasks`` and
``webhooks`` do.
"""

import pkgutil
from importlib import import_module


def import_submodules(package_name, package_path, skip=()):
    """Import every non-private submodule of a package. Returns their names."""
    imported = []
    for module_info in pkgutil.iter_modules(package_path):
        name = module_info.name
        if name.startswith("_") or name in skip:
            continue
        import_module(f"{package_name}.{name}")
        imported.append(name)
    return imported
