# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

"""The ``config`` command: report the capabilities in effect for a repository.

With policy spread across repositories, "why did the bot do nothing" is
otherwise answerable only by reading the logs on the host.
"""

from .. import github, policy, registry
from ..config import BOT_CONFIG_FILENAME
from ..queue import task
from ..tasks.add_pr_comment import add_pr_comment
from .base import BotCommand, command

_KIND_TITLES = {
    registry.COMMAND: "Commands",
    registry.TASK: "Tasks",
    registry.STEP: "Steps",
}


def format_report(repo_policy, effective_names):
    """Render the resolved policy of a repository as markdown."""
    lines = []
    if not repo_policy.found:
        lines.append(f"No `{BOT_CONFIG_FILENAME}`; the default capabilities apply.")
    else:
        where = f"`{BOT_CONFIG_FILENAME}`"
        if repo_policy.ref:
            where += f" on `{repo_policy.ref}`"
        lines.append(f"Read {where}.")
    if repo_policy.error:
        lines.append("")
        lines.append(
            f"⚠️ The file {repo_policy.error}. "
            f"The default capabilities are used instead."
        )
    if repo_policy.unknown:
        unknown = ", ".join(f"`{name}`" for name in sorted(repo_policy.unknown))
        lines.append("")
        lines.append(f"⚠️ Not recognised, and ignored: {unknown}.")

    capabilities = registry.all_capabilities()
    for kind in (registry.COMMAND, registry.TASK, registry.STEP):
        of_kind = sorted(c.name for c in capabilities.values() if c.kind == kind)
        if not of_kind:
            continue
        lines.append("")
        lines.append(f"**{_KIND_TITLES[kind]}**")
        for name in of_kind:
            mark = "x" if name in effective_names else " "
            lines.append(f"* [{mark}] `{name}`")
    return "\n".join(lines)


@task()
def report_config(org, repo, pr, ref=None, dry_run=False):
    repo_policy = policy.fetch(org, repo, ref)
    message = format_report(repo_policy, policy.effective(repo_policy))
    if not dry_run:
        add_pr_comment.delay(org, repo, pr, message)
    return message


@command
class BotCommandConfig(BotCommand):
    name = "config"
    switch = "bot_config"
    description = "``config`` -- report the capabilities enabled for this repository"
    # Diagnostics must survive a repository that has denied everything.
    always_available = True

    def delay(self, org, repo, pr, username, dry_run=False):
        with github.login() as gh:
            gh_pr = github.gh_call(gh.pull_request, org, repo, pr)
            ref = gh_pr.base.ref
        report_config.delay(org, repo, pr, ref=ref, dry_run=dry_run)
