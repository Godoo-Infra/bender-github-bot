# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

from contextlib import contextmanager

import pytest

from oca_github_bot.commands.dispatch import dispatch_command


@pytest.fixture
def gh_pr(mocker):
    """Stub the GitHub call that finds the pull request's target branch."""
    gh_pr = mocker.Mock()
    gh_pr.base.ref = "16.0"
    gh = mocker.Mock()
    gh.pull_request.return_value = gh_pr

    @contextmanager
    def login():
        yield gh

    mocker.patch("oca_github_bot.commands.dispatch.github.login", login)
    return gh_pr


def test_an_allowed_command_runs(mocker, gh_pr):
    is_allowed = mocker.patch(
        "oca_github_bot.commands.dispatch.policy.is_allowed", return_value=True
    )
    start = mocker.patch("oca_github_bot.tasks.rebase_bot.rebase_bot_start.delay")

    dispatch_command("OCA", "some-repo", 42, "test-user", "rebase", [])

    # the policy is resolved against the target branch, not the branch the
    # pull request proposes
    is_allowed.assert_called_once_with("rebase_bot", "OCA", "some-repo", "16.0")
    start.assert_called_once_with("OCA", "some-repo", 42, "test-user", dry_run=False)


def test_a_denied_command_says_so_instead_of_running(mocker, gh_pr):
    mocker.patch(
        "oca_github_bot.commands.dispatch.policy.is_allowed", return_value=False
    )
    start = mocker.patch("oca_github_bot.tasks.rebase_bot.rebase_bot_start.delay")
    comment = mocker.patch("oca_github_bot.commands.dispatch.add_pr_comment.delay")

    dispatch_command("OCA", "some-repo", 42, "test-user", "rebase", [])

    start.assert_not_called()
    comment.assert_called_once()
    message = comment.call_args[0][3]
    assert "not enabled for this repository" in message
    assert "config" in message


def test_dry_run_is_passed_through(mocker, gh_pr):
    mocker.patch(
        "oca_github_bot.commands.dispatch.policy.is_allowed", return_value=True
    )
    start = mocker.patch("oca_github_bot.tasks.merge_bot.merge_bot_start.delay")

    dispatch_command(
        "OCA", "some-repo", 42, "test-user", "merge", ["patch"], dry_run=True
    )

    start.assert_called_once_with(
        "OCA", "some-repo", 42, "test-user", "patch", dry_run=True
    )


def test_an_always_available_command_skips_the_policy(mocker, gh_pr):
    is_allowed = mocker.patch("oca_github_bot.commands.dispatch.policy.is_allowed")
    report = mocker.patch("oca_github_bot.commands.bot_config.report_config.delay")

    dispatch_command("OCA", "some-repo", 42, "test-user", "config", [])

    # a repository that has denied everything can still be asked why
    is_allowed.assert_not_called()
    report.assert_called_once_with("OCA", "some-repo", 42, ref="16.0", dry_run=False)
