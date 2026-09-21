# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""Run a parsed command, once the repository is known to allow it.

The webhook parses the comment, so that a malformed command is reported
straight away, then hands the command here. Resolving the policy needs the
pull request's target branch and a GitHub call, neither of which belongs in a
webhook handler.
"""

from .. import github, policy
from ..config import BOT_COMMAND_PREFIX
from ..queue import getLogger, task
from ..tasks.add_pr_comment import add_pr_comment
from .base import BotCommand

_logger = getLogger(__name__)


@task()
def dispatch_command(org, repo, pr, username, name, options, dry_run=False):
    bot_command = BotCommand.create(name, options)
    if not bot_command.always_available:
        with github.login() as gh:
            gh_pr = github.gh_call(gh.pull_request, org, repo, pr)
            target_branch = gh_pr.base.ref
        if not policy.is_allowed(bot_command.capability(), org, repo, target_branch):
            _logger.info(
                "Command %s not available in %s/%s@%s", name, org, repo, target_branch
            )
            prefix = BOT_COMMAND_PREFIX[0]
            add_pr_comment.delay(
                org,
                repo,
                pr,
                f"Sorry @{username}, the `{name}` command is not enabled for "
                f"this repository.\n\n"
                f"Use `{prefix} config` to see what is.",
            )
            return
    bot_command.delay(org, repo, pr, username, dry_run=dry_run)
