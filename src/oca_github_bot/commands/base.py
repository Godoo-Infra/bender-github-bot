# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""The command framework: the prefix, the registry, and the base command.

A command declares what it is -- its name, the capability it gates on, its
options and its help line -- rather than being wired into a dispatch chain.
Adding one means adding a module to this package, or to ``custom``.
"""

import re

from .. import config, registry
from ..config import BOT_COMMAND_PREFIX


def build_command_re(prefixes):
    """Build the pattern matching a command in a comment."""
    alternation = "|".join(re.escape(prefix) for prefix in prefixes)
    return re.compile(
        # Do not start with > (Github comment), not consuming it
        r"^(?=[^>])"
        # Anything before the prefix, at least one whitspace after
        rf".*(?:{alternation})\s+"
        # command group: any word is ok
        r"(?P<command>\w+)"
        # options group: spaces and words, all the times you want (0 is ok too)
        r"(?P<options>[ \t\w]*)"
        # non-capturing group:
        # stop finding options as soon as you find something that is not a word
        r"(?:\W|\r?$)",
        re.MULTILINE,
    )


BOT_COMMAND_RE = build_command_re(BOT_COMMAND_PREFIX)


class CommandError(Exception):
    pass


class InvalidCommandError(CommandError):
    def __init__(self, name):
        super().__init__(f"Invalid command: {name}")


class OptionsError(CommandError):
    pass


class InvalidOptionsError(OptionsError):
    def __init__(self, name, options):
        options_text = " ".join(options)
        super().__init__(f"Invalid options for command {name}: {options_text}")


class RequiredOptionError(OptionsError):
    def __init__(self, name, option, values):
        values_text = ", ".join(values)
        super().__init__(
            f"Required option {option} for command {name}.\n"
            f"Possible values : {values_text}"
        )


#: command name -> BotCommand subclass
COMMANDS = {}


class BotCommand:
    #: the word that invokes the command, after the prefix
    name = None
    #: the capability it gates on, which is the ``@switchable`` name of the
    #: task it starts; defaults to :attr:`name`
    switch = None
    #: one line describing the command, shown when a command is rejected
    description = ""
    #: when set, the command takes exactly one option, from this list
    required_choice = None
    #: whether the command applies to a repository that has no policy file
    default = True
    #: when true the command runs whatever the repository policy says, so that
    #: a repository which has denied everything can still be asked why
    always_available = False
    #: set from the single option when :attr:`required_choice` is used
    choice = None

    def __init__(self, name, options):
        self.name = name
        self.options = options
        self.parse_options(options)

    @classmethod
    def create(cls, name, options):
        command_cls = COMMANDS.get(name)
        if command_cls is None:
            raise InvalidCommandError(name)
        return command_cls(name, options)

    @classmethod
    def capability(cls):
        return cls.switch or cls.name

    def parse_options(self, options):
        if self.required_choice is None:
            if options:
                raise InvalidOptionsError(self.name, options)
            return
        if not options:
            raise RequiredOptionError(self.name, "option", self.required_choice)
        if len(options) == 1 and options[0] in self.required_choice:
            self.choice = options[0]
        else:
            raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        """Run the command on a given pull request on behalf of a GitHub user"""
        raise NotImplementedError()


def command(cls):
    """Register a command class. Use as a class decorator."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} must declare a name")
    if cls.name in COMMANDS and COMMANDS[cls.name] is not cls:
        raise registry.DuplicateCapabilityError(cls.name)
    COMMANDS[cls.name] = cls
    capability = cls.capability()
    if capability != cls.name:
        # The command word is an alias of the capability the task registers,
        # so that a policy file may name either.
        aliases = (cls.name,)
    else:
        aliases = ()
    registry.register(
        capability,
        kind=registry.COMMAND,
        default=cls.default,
        description=cls.description,
        aliases=aliases,
    )
    return cls


def parse_commands(text):
    """Parse a text and return an iterator of BotCommand objects."""
    for mo in BOT_COMMAND_RE.finditer(text):
        yield BotCommand.create(
            mo.group("command"), mo.group("options").strip().split()
        )


def usage_text():
    """The usage message, generated from the registered commands."""
    if config.OCABOT_USAGE:
        return config.OCABOT_USAGE
    prefix = BOT_COMMAND_PREFIX[0].lstrip("/")
    lines = [f"**{prefix.capitalize()} commands**"]
    for name in sorted(COMMANDS):
        description = COMMANDS[name].description or f"``{prefix} {name}``"
        lines.append(f"* {description}")
    return "\n".join(lines)
