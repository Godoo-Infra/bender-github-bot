# Copyright (c) ForgeFlow, S.L. 2021
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from ..tasks import rebase_bot
from .base import BotCommand, command


@command
class BotCommandRebase(BotCommand):
    name = "rebase"
    switch = "rebase_bot"
    description = "``rebase`` -- rebase the pull request on its target branch"

    def delay(self, org, repo, pr, username, dry_run=False):
        rebase_bot.rebase_bot_start.delay(org, repo, pr, username, dry_run=dry_run)
