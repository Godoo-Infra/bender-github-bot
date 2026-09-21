# Copyright (c) ACSONE SA/NV 2018
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import ast
import inspect
import logging
import os
from functools import wraps

from . import registry
from .pypi import MultiDistPublisher, RsyncDistPublisher, TwineDistPublisher
from .registry import COMMAND, STEP, TASK  # noqa: F401

_logger = logging.getLogger("oca_gihub_bot.tasks")


def _org_repo_ref_of_call(func, args, kwargs):
    """Find the repository a switchable call is acting on, from its arguments.

    Every switchable function names its arguments ``org`` and ``repo``, though
    not always in that order (``tag_needs_review`` takes ``org, pr, repo``), so
    they are located by name rather than by position.
    """
    try:
        bound = inspect.signature(func).bind_partial(*args, **kwargs)
    except TypeError:
        return None, None, None
    arguments = bound.arguments
    ref = arguments.get("branch") or arguments.get("target_branch")
    return arguments.get("org"), arguments.get("repo"), ref


def _repo_allows(name, org, repo, ref):
    # Imported here, not at module level: policy reads the repository through
    # github.py, which imports this module.
    from . import policy

    try:
        return policy.is_allowed(name, org, repo, ref)
    except Exception:
        _logger.exception(
            "Could not resolve the policy of %s/%s for %s; allowing it",
            org,
            repo,
            name,
        )
        # Fail open: an unreadable policy must not stop the bot working.
        return True


def switchable(switch_name=None, kind=registry.TASK, default=True, description=""):
    """Make a function switchable on and off by configuration.

    Registers the capability so that it can be named in ``BOT_TASKS``, in
    ``BOT_TASKS_DISABLED`` and in a repository's policy file, then gates every
    call on both.
    """

    def wrap(func):
        sname = switch_name if switch_name is not None else func.__name__
        registry.register(sname, kind=kind, default=default, description=description)

        @wraps(func)
        def func_wrapper(*args, **kwargs):
            if (
                BOT_TASKS != ["all"] and sname not in BOT_TASKS
            ) or sname in BOT_TASKS_DISABLED:
                _logger.debug("Method %s skipped (Disabled by config)", sname)
                return
            org, repo, ref = _org_repo_ref_of_call(func, args, kwargs)
            if org and repo and not _repo_allows(sname, org, repo, ref):
                _logger.info(
                    "Method %s skipped for %s/%s (disabled by repository policy)",
                    sname,
                    org,
                    repo,
                )
                return
            return func(*args, **kwargs)

        return func_wrapper

    return wrap


HTTP_HOST = os.environ.get("HTTP_HOST")
HTTP_PORT = int(os.environ.get("HTTP_PORT") or "8080")

GITHUB_SECRET = os.environ.get("GITHUB_SECRET")
GITHUB_LOGIN = os.environ.get("GITHUB_LOGIN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_ORG = (
    os.environ.get("GITHUB_ORG") and os.environ.get("GITHUB_ORG").split(",") or []
)
GIT_NAME = os.environ.get("GIT_NAME")
GIT_EMAIL = os.environ.get("GIT_EMAIL")

ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_LOGIN = os.environ.get("ODOO_LOGIN")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD")

BROKER_URI = os.environ.get("BROKER_URI", os.environ.get("REDIS_URI", "redis://queue"))

SENTRY_DSN = os.environ.get("SENTRY_DSN")

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# Coma separated list of task to run.
# By default all tasks registered with default=True are run. The authoritative
# list is the capability registry, which the ``config`` bot command reports.
BOT_TASKS = os.environ.get("BOT_TASKS", "all").split(",")

BOT_TASKS_DISABLED = os.environ.get("BOT_TASKS_DISABLED", "").split(",")

# Coma separated list of prefixes a command may be invoked with. Several allow
# a second prefix to run alongside the first, during a rename.
BOT_COMMAND_PREFIX = [
    prefix.strip()
    for prefix in os.environ.get("BOT_COMMAND_PREFIX", "/ocabot").split(",")
    if prefix.strip()
]

# Name of the per-repository policy file, read from the target branch.
BOT_CONFIG_FILENAME = os.environ.get("BOT_CONFIG_FILENAME", ".bender.yml")

GEN_ADDONS_TABLE_EXTRA_ARGS = (
    os.environ.get("GEN_ADDONS_TABLE_EXTRA_ARGS", "")
    and os.environ.get("GEN_ADDONS_TABLE_EXTRA_ARGS").split(" ")
    or []
)

GEN_ADDON_README_EXTRA_ARGS = (
    os.environ.get("GEN_ADDON_README_EXTRA_ARGS", "")
    and os.environ.get("GEN_ADDON_README_EXTRA_ARGS").split(" ")
    or []
)

GEN_ADDON_ICON_EXTRA_ARGS = (
    os.environ.get("GEN_ADDON_ICON_EXTRA_ARGS", "")
    and os.environ.get("GEN_ADDON_ICON_EXTRA_ARGS").split(" ")
    or []
)

GITHUB_STATUS_IGNORED = os.environ.get(
    "GITHUB_STATUS_IGNORED",
    "ci/runbot,codecov/project,codecov/patch,coverage/coveralls",
).split(",")

GITHUB_CHECK_SUITES_IGNORED = os.environ.get(
    "GITHUB_CHECK_SUITES_IGNORED", "Codecov,Dependabot"
).split(",")

MERGE_BOT_INTRO_MESSAGES = [
    "On my way to merge this fine PR!",
    "This PR looks fantastic, let's merge it!",
    "Hey, thanks for contributing! Proceeding to merge this for you.",
    "What a great day to merge this nice PR. Let's do it!",
]

APPROVALS_REQUIRED = int(os.environ.get("APPROVALS_REQUIRED", "2"))
MIN_PR_AGE = int(os.environ.get("MIN_PR_AGE", "5"))

MODULE_LABEL_COLOR = os.environ.get("MODULE_LABEL_COLOR", "#ffc")

dist_publisher = MultiDistPublisher()
SIMPLE_INDEX_ROOT = os.environ.get("SIMPLE_INDEX_ROOT")
if SIMPLE_INDEX_ROOT:
    dist_publisher.add(RsyncDistPublisher(SIMPLE_INDEX_ROOT))
if os.environ.get("OCABOT_TWINE_REPOSITORIES"):
    for index_url, repository_url, username, password in ast.literal_eval(
        os.environ["OCABOT_TWINE_REPOSITORIES"]
    ):
        dist_publisher.add(
            TwineDistPublisher(index_url, repository_url, username, password)
        )

# Generated from the registered commands when unset, so that the usage message
# a user is shown always matches the commands this deployment actually has.
OCABOT_USAGE = os.environ.get("OCABOT_USAGE")

OCABOT_EXTRA_DOCUMENTATION = os.environ.get(
    "OCABOT_EXTRA_DOCUMENTATION",
    "**More information**\n"
    " * [ocabot documentation](https://github.com/OCA/oca-github-bot/#commands)\n"
    " * [OCA guidelines](https://github.com/OCA/odoo-community.org/blob/master/"
    "website/Contribution/CONTRIBUTING.rst), "
    'specially the "Version Numbers" section.',
)

ADOPT_AN_ADDON_MENTION = os.environ.get("ADOPT_AN_ADDON_MENTION")

MAINTAINER_CHECK_ODOO_RELEASES = (
    os.environ.get("MAINTAINER_CHECK_ODOO_RELEASES")
    and os.environ.get("MAINTAINER_CHECK_ODOO_RELEASES").split(",")
    or []
)

WHEEL_BUILD_TOOLS = os.environ.get(
    "WHEEL_BUILD_TOOLS",
    "build,pip,setuptools<70,wheel,setuptools-odoo,whool",
).split(",")

# minimum Odoo series supported by the bot
MAIN_BRANCH_BOT_MIN_VERSION = os.environ.get("MAIN_BRANCH_BOT_MIN_VERSION", "11.0")

# First Odoo Series for which the whool_init and gen_metapackage tasks are run on main
# branches. For previous versions, the setuptools_odoo task is run and generates
# setup.py instead of pyproject.toml.
GEN_PYPROJECT_MIN_VERSION = os.environ.get("GEN_PYPROJECT_MIN_VERSION", "17.0")
