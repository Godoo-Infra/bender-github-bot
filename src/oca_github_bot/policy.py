# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Per-repository policy: which capabilities apply to a given repository.

A repository may carry a policy file (``.bender.yml`` by default) naming
capabilities to add to, or remove from, the default set:

.. code:: yaml

    version: 1
    tasks:
      allow: [deploy_staging]
      deny:  [merge_bot]

The file selects from what the bot has registered; it never describes
behaviour. It is read from the target branch of a pull request, never from the
branch proposing the change, so that a pull request cannot grant itself
capabilities in the same diff that uses them.

Resolution, highest precedence first:

1. ``BOT_TASKS_DISABLED`` -- the fleet-wide kill switch, always wins
2. the repository's ``deny`` list
3. the repository's ``allow`` list
4. the default set (``BOT_TASKS`` narrowed to capabilities registered by
   default)
"""

import time

import yaml

from . import config, registry
from .github import gh_call, repository
from .queue import getLogger

_logger = getLogger(__name__)

#: how long a fetched policy is reused before being read again
CACHE_TTL = 300


class PolicyError(Exception):
    pass


class RepoPolicy:
    """The policy file of one repository at one ref, parsed."""

    def __init__(
        self, allow=(), deny=(), unknown=(), error=None, found=False, ref=None
    ):
        self.allow = set(allow)
        self.deny = set(deny)
        #: names in the file that no capability is registered under
        self.unknown = list(unknown)
        #: the parse error, when the file could not be understood
        self.error = error
        #: whether a file was found at all
        self.found = found
        self.ref = ref

    def __repr__(self):
        return (
            f"RepoPolicy(allow={sorted(self.allow)}, deny={sorted(self.deny)}, "
            f"found={self.found}, error={self.error!r})"
        )


#: the policy used when a repository has no file, or it could not be read
DEFAULT_POLICY = RepoPolicy()


def _global_default_names():
    """The default set: registered defaults, narrowed by BOT_TASKS."""
    defaults = registry.default_names()
    if config.BOT_TASKS == ["all"]:
        return defaults
    configured = set()
    for name in config.BOT_TASKS:
        canonical = registry.canonical(name)
        configured.add(canonical or name)
    return defaults & configured


def _global_denied_names():
    denied = set()
    for name in config.BOT_TASKS_DISABLED:
        if not name:
            continue
        canonical = registry.canonical(name)
        denied.add(canonical or name)
    return denied


def effective(policy=DEFAULT_POLICY):
    """The set of capability names in effect, given a repository policy."""
    names = _global_default_names() | policy.allow
    names -= policy.deny
    names -= _global_denied_names()
    return names


def parse(text, ref=None):
    """Parse the contents of a policy file.

    Never raises: a file that cannot be understood yields a policy equal to the
    defaults, carrying the error so that it can be reported where a user will
    see it.
    """
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return RepoPolicy(error=f"could not be parsed: {e}", found=True, ref=ref)
    if document is None:
        return RepoPolicy(found=True, ref=ref)
    if not isinstance(document, dict):
        return RepoPolicy(
            error="must be a mapping at the top level", found=True, ref=ref
        )
    version = document.get("version")
    if version != 1:
        return RepoPolicy(
            error=f"unsupported version {version!r}, expected 1", found=True, ref=ref
        )
    tasks = document.get("tasks") or {}
    if not isinstance(tasks, dict):
        return RepoPolicy(error="'tasks' must be a mapping", found=True, ref=ref)

    allow, deny, unknown = set(), set(), []
    for key, target in (("allow", allow), ("deny", deny)):
        names = tasks.get(key) or []
        if not isinstance(names, list):
            return RepoPolicy(
                error=f"'tasks.{key}' must be a list", found=True, ref=ref
            )
        for name in names:
            canonical = registry.canonical(str(name))
            if canonical is None:
                unknown.append(str(name))
            else:
                target.add(canonical)
    return RepoPolicy(allow=allow, deny=deny, unknown=unknown, found=True, ref=ref)


_cache = {}


def _cache_get(key):
    entry = _cache.get(key)
    if entry is None:
        return None
    expires_at, policy = entry
    if expires_at < time.monotonic():
        del _cache[key]
        return None
    return policy


def _cache_put(key, policy):
    _cache[key] = (time.monotonic() + CACHE_TTL, policy)


def clear_cache():
    _cache.clear()


def fetch(org, repo, ref=None):
    """Read the policy of a repository, through the GitHub API.

    A single file is read at a single ref, which costs one API call rather than
    a clone. Failures fall back to the defaults: policy must never be able to
    take the bot down.
    """
    if not config.GITHUB_TOKEN:
        # Nothing to read the file with; the default capabilities apply.
        return DEFAULT_POLICY
    key = (org.lower(), repo.lower(), ref)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    try:
        with repository(org, repo) as gh_repo:
            contents = gh_call(
                gh_repo.file_contents, config.BOT_CONFIG_FILENAME, ref=ref
            )
    except Exception as e:
        _logger.debug(
            "Could not read %s in %s/%s@%s: %s",
            config.BOT_CONFIG_FILENAME,
            org,
            repo,
            ref,
            e,
        )
        contents = None
    if contents is None:
        policy = RepoPolicy(ref=ref)
    else:
        policy = parse(contents.decoded.decode("utf-8"), ref=ref)
        if policy.error:
            _logger.warning(
                "%s in %s/%s@%s %s; using the default capabilities",
                config.BOT_CONFIG_FILENAME,
                org,
                repo,
                ref,
                policy.error,
            )
        if policy.unknown:
            _logger.warning(
                "%s in %s/%s@%s names unknown capabilities: %s",
                config.BOT_CONFIG_FILENAME,
                org,
                repo,
                ref,
                ", ".join(policy.unknown),
            )
    _cache_put(key, policy)
    return policy


def is_allowed(name, org, repo, ref=None):
    """Whether a capability applies to a repository."""
    canonical = registry.canonical(name) or name
    return canonical in effective(fetch(org, repo, ref))
