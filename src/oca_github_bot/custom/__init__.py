# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Site-specific commands and tasks.

Every module here is imported at startup, so adding a custom action means
adding a file and restarting. One module per feature: a custom action is
usually a celery task and the command that starts it, and splitting those
across two packages means every feature is two files that have to agree.

This package exists mainly for merge hygiene. It is a directory upstream does
not have, so merging upstream never conflicts with what is in it.

Register custom capabilities with ``default=False`` -- both on the
``@switchable`` and on the command class -- so that adding one cannot change
behaviour until a repository allows it by name in its policy file. See
``docs/design/configurable-commands.md``.
"""

from ..discovery import import_submodules

import_submodules(__name__, __path__)
