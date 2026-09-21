# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Bot commands.

Every module in this package is imported when the package is, so adding a
command means adding a module. Custom commands live in ``oca_github_bot.custom``
and are discovered the same way.
"""

from ..discovery import import_submodules
from .base import (
    COMMANDS,
    BotCommand,
    CommandError,
    InvalidCommandError,
    InvalidOptionsError,
    OptionsError,
    RequiredOptionError,
    build_command_re,
    command,
    parse_commands,
    usage_text,
)

import_submodules(__name__, __path__, skip=("base",))
