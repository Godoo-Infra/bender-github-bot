# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Registry of the capabilities a repository may enable or disable.

Every ``@switchable`` task and every bot command records itself here when its
module is imported. The registry is the vocabulary per-repository policy is
resolved against: a repository can only allow or deny something the bot has
registered, never describe new behaviour.

Names form a single flat namespace, because the switchable names do not divide
cleanly into commands and tasks: most of them are steps of a larger operation
(``gen_addons_readme`` runs from a push, from the nightly cron and from the
merge bot alike). ``kind`` records the distinction for reporting without the
policy schema having to model it.
"""

import dataclasses

COMMAND = "command"  # invoked by a user, in a pull request comment
TASK = "task"  # triggered by a GitHub event or by the scheduler
STEP = "step"  # a step within a larger operation

KINDS = (COMMAND, TASK, STEP)


class DuplicateCapabilityError(Exception):
    def __init__(self, name):
        super().__init__(f"Capability {name} is already registered")


@dataclasses.dataclass(frozen=True)
class Capability:
    #: canonical name, which is the ``@switchable`` name
    name: str
    kind: str
    #: whether the capability is part of the default set; custom capabilities
    #: register with ``default=False`` so that adding one cannot change
    #: behaviour until a repository asks for it
    default: bool = True
    #: one line, used to generate the usage message for commands
    description: str = ""
    #: other names accepted in policy files, such as the word a command is
    #: invoked with (``merge`` for ``merge_bot``)
    aliases: tuple[str, ...] = ()


_capabilities: dict[str, Capability] = {}
_aliases: dict[str, str] = {}


#: most specific kind first; a capability registered under several kinds keeps
#: the most specific one. A command is registered twice: once by the
#: ``@switchable`` on the task it starts, once by the command itself.
_KIND_PRECEDENCE = (COMMAND, TASK, STEP)


def register(name, kind=TASK, default=True, description="", aliases=()):
    """Record a capability, merging with an earlier registration of the name.

    Returns the Capability.
    """
    if kind not in KINDS:
        raise ValueError(f"Unknown capability kind {kind!r} for {name}")
    existing = _capabilities.get(name)
    if existing is not None:
        kind = min(
            (existing.kind, kind),
            key=_KIND_PRECEDENCE.index,
        )
        # Opting in wins over opting out: a capability is in the default set
        # only if every registration of it says so.
        default = existing.default and default
        description = description or existing.description
        aliases = tuple(set(existing.aliases) | set(aliases))
    capability = Capability(
        name=name,
        kind=kind,
        default=default,
        description=description,
        aliases=tuple(sorted(aliases)),
    )
    _capabilities[name] = capability
    for alias in capability.aliases:
        _aliases[alias] = name
    return capability


def canonical(name):
    """Resolve a name or alias to its canonical name, or None if unknown."""
    if name in _capabilities:
        return name
    return _aliases.get(name)


def get(name):
    """Return the Capability for a name or alias, or None if unknown."""
    canonical_name = canonical(name)
    if canonical_name is None:
        return None
    return _capabilities[canonical_name]


def all_capabilities():
    return dict(_capabilities)


def default_names():
    """The capabilities that apply to a repository with no policy file."""
    return {c.name for c in _capabilities.values() if c.default}


def snapshot():
    """Capture the registry, for tests that register throwaway capabilities."""
    return dict(_capabilities), dict(_aliases)


def restore(state):
    capabilities, aliases = state
    _capabilities.clear()
    _capabilities.update(capabilities)
    _aliases.clear()
    _aliases.update(aliases)
