# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import pytest

from oca_github_bot import policy, registry
from oca_github_bot.commands.bot_config import format_report, report_config

from .common import set_config


@pytest.fixture
def capabilities():
    saved = registry.snapshot()
    registry.restore(({}, {}))
    registry.register("merge_bot", kind=registry.COMMAND, aliases=("merge",))
    registry.register("mention_maintainer")
    registry.register("gen_addons_readme", kind=registry.STEP)
    yield registry
    registry.restore(saved)


def report_for(text=None, ref=None):
    if text is None:
        repo_policy = policy.RepoPolicy()
    else:
        repo_policy = policy.parse(text, ref=ref)
    return format_report(repo_policy, policy.effective(repo_policy))


def test_report_without_a_file(capabilities):
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        report = report_for()
    assert "the default capabilities apply" in report
    # everything on, grouped by what triggers it
    assert "**Commands**" in report
    assert "**Tasks**" in report
    assert "**Steps**" in report
    assert "* [x] `merge_bot`" in report


def test_report_marks_what_is_off(capabilities):
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        report = report_for("version: 1\ntasks:\n  deny: [merge_bot]\n", ref="16.0")
    assert "* [ ] `merge_bot`" in report
    assert "* [x] `mention_maintainer`" in report
    # says which ref it read, since policy can differ per branch
    assert "on `16.0`" in report


def test_report_surfaces_a_parse_error(capabilities):
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        report = report_for("version: 1\ntasks: [nope]\n")
    assert "⚠️" in report
    assert "must be a mapping" in report
    # and the defaults still apply
    assert "* [x] `merge_bot`" in report


def test_report_lists_names_it_did_not_recognise(capabilities):
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        report = report_for("version: 1\ntasks:\n  deny: [merge_bo]\n")
    assert "Not recognised" in report
    assert "`merge_bo`" in report


def test_report_config_comments_on_the_pull_request(capabilities, mocker):
    mocker.patch(
        "oca_github_bot.commands.bot_config.policy.fetch",
        return_value=policy.RepoPolicy(ref="16.0"),
    )
    comment = mocker.patch("oca_github_bot.commands.bot_config.add_pr_comment.delay")
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        message = report_config("OCA", "some-repo", 42, ref="16.0")
    comment.assert_called_once_with("OCA", "some-repo", 42, message)


def test_report_config_dry_run_does_not_comment(capabilities, mocker):
    mocker.patch(
        "oca_github_bot.commands.bot_config.policy.fetch",
        return_value=policy.RepoPolicy(),
    )
    comment = mocker.patch("oca_github_bot.commands.bot_config.add_pr_comment.delay")
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        report_config("OCA", "some-repo", 42, dry_run=True)
    comment.assert_not_called()
