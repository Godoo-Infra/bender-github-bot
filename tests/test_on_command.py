# Copyright (c) initOS GmbH 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import pytest

from oca_github_bot.webhooks import on_command

from .common import EventMock


def create_test_data(pr, user, body):
    return {
        "repository": {"full_name": "OCA/some-repo"},
        "issue": {"number": pr if pr else None, "pull_request": bool(pr)},
        "comment": {"body": body, "user": {"login": user}},
    }


@pytest.mark.asyncio
async def test_on_command_no_pr(mocker):
    mocker.patch("oca_github_bot.webhooks.on_command.parse_commands")

    data = create_test_data(False, "test-user", "/ocabot merge")
    event = EventMock(data)
    await on_command.on_command(event, None)
    on_command.parse_commands.assert_not_called()


@pytest.mark.asyncio
async def test_on_command_valid_pr(mocker):
    cmd_mock = mocker.Mock()
    cmd_mock.name = "merge"
    cmd_mock.options = ["patch"]
    mocker.patch("oca_github_bot.webhooks.on_command.parse_commands").return_value = [
        cmd_mock
    ]
    dispatch = mocker.patch("oca_github_bot.webhooks.on_command.dispatch_command.delay")

    body = "test_message"

    # Completed
    data = create_test_data(42, "test-user", body)
    event = EventMock(data)
    await on_command.on_command(event, None)
    on_command.parse_commands.assert_called_once_with(body)
    # the webhook hands the command over rather than running it: whether the
    # repository allows it needs a GitHub call
    dispatch.assert_called_once_with(
        "OCA", "some-repo", 42, "test-user", "merge", ["patch"]
    )


@pytest.mark.asyncio
async def test_on_command_malformed_is_reported_at_once(mocker):
    comment = mocker.patch("oca_github_bot.webhooks.on_command.add_pr_comment.delay")
    dispatch = mocker.patch("oca_github_bot.webhooks.on_command.dispatch_command.delay")

    data = create_test_data(42, "test-user", "/ocabot merge nonsense")
    event = EventMock(data)
    await on_command.on_command(event, None)

    dispatch.assert_not_called()
    comment.assert_called_once()
    message = comment.call_args[0][3]
    assert "Your command failed" in message
    # the usage shown is generated, so it lists the commands that exist
    assert "merge" in message and "rebase" in message
