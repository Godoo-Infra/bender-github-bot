# Copyright (c) initOS GmbH 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from ..commands import CommandError, parse_commands, usage_text
from ..commands.dispatch import dispatch_command
from ..config import OCABOT_EXTRA_DOCUMENTATION
from ..router import router
from ..tasks.add_pr_comment import add_pr_comment


@router.register("issue_comment", action="created")
async def on_command(event, gh, *args, **kwargs):
    """On pull request review, tag if approved or ready to merge."""
    if not event.data["issue"].get("pull_request"):
        # ignore issue comments
        return
    org, repo = event.data["repository"]["full_name"].split("/")
    pr = event.data["issue"]["number"]
    username = event.data["comment"]["user"]["login"]
    text = event.data["comment"]["body"]
    await _on_command(org, repo, pr, username, text)


async def _on_command(org, repo, pr, username, text):
    try:
        # Parse here, so that a malformed command is reported at once, and
        # dispatch the rest: deciding whether the repository allows a command
        # needs a GitHub call, which does not belong in a webhook handler.
        for command in list(parse_commands(text)):
            dispatch_command.delay(
                org, repo, pr, username, command.name, command.options
            )
    except CommandError as e:
        # Add a comment on the current PR, if
        # the command was misunderstood by the bot
        add_pr_comment.delay(
            org,
            repo,
            pr,
            f"Hi @{username}. Your command failed:\n\n"
            f"``{e}``.\n\n"
            f"{usage_text()}\n\n"
            f"{OCABOT_EXTRA_DOCUMENTATION}",
        )
