# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from ..tasks import migration_issue_bot
from .base import BotCommand, InvalidOptionsError, command


@command
class BotCommandMigrationIssue(BotCommand):
    name = "migration"
    switch = "migration_issue_bot"
    description = "``migration {MODULE_NAME}`` -- update the migration issue"

    module = None  # mandatory str: module name

    def parse_options(self, options):
        if len(options) == 1:
            self.module = options[0]
        else:
            raise InvalidOptionsError(self.name, options)

    def delay(self, org, repo, pr, username, dry_run=False):
        migration_issue_bot.migration_issue_start.delay(
            org, repo, pr, username, module=self.module, dry_run=dry_run
        )
