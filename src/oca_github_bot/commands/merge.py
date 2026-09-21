# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from ..tasks import merge_bot
from .base import BotCommand, command


@command
class BotCommandMerge(BotCommand):
    name = "merge"
    switch = "merge_bot"
    description = "``merge major|minor|patch|nobump`` -- merge the pull request"
    required_choice = ["major", "minor", "patch", "nobump"]

    @property
    def bumpversion_mode(self):
        return self.choice

    def delay(self, org, repo, pr, username, dry_run=False):
        merge_bot.merge_bot_start.delay(
            org, repo, pr, username, self.bumpversion_mode, dry_run=dry_run
        )
