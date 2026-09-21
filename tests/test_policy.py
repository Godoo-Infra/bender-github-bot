# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import pytest

from oca_github_bot import policy, registry

from .common import set_config


@pytest.fixture
def capabilities():
    """A registry holding a known set of capabilities."""
    saved = registry.snapshot()
    registry.restore(({}, {}))
    registry.register("gen_addons_readme")
    registry.register("gen_addons_icon")
    registry.register("merge_bot", kind=registry.COMMAND, aliases=("merge",))
    registry.register("deploy_staging", default=False)
    yield registry
    registry.restore(saved)


@pytest.fixture(autouse=True)
def no_cache():
    policy.clear_cache()
    yield
    policy.clear_cache()


def parse(text):
    return policy.parse(text)


def test_no_file_gives_the_default_set(capabilities):
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective() == {
            "gen_addons_readme",
            "gen_addons_icon",
            "merge_bot",
        }
        # registered with default=False, so opt-in only
        assert "deploy_staging" not in policy.effective()


def test_allow_adds_and_deny_removes(capabilities):
    repo_policy = parse(
        """
        version: 1
        tasks:
          allow: [deploy_staging]
          deny: [merge_bot]
        """
    )
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective(repo_policy) == {
            "gen_addons_readme",
            "gen_addons_icon",
            "deploy_staging",
        }


def test_deny_beats_allow(capabilities):
    repo_policy = parse(
        """
        version: 1
        tasks:
          allow: [deploy_staging]
          deny: [deploy_staging]
        """
    )
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert "deploy_staging" not in policy.effective(repo_policy)


def test_global_deny_beats_repository_allow(capabilities):
    repo_policy = parse(
        """
        version: 1
        tasks:
          allow: [deploy_staging, gen_addons_icon]
        """
    )
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=["deploy_staging"]):
        effective = policy.effective(repo_policy)
        assert "deploy_staging" not in effective
        assert "gen_addons_icon" in effective


def test_bot_tasks_narrows_the_default_set(capabilities):
    with set_config(BOT_TASKS=["gen_addons_readme"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective() == {"gen_addons_readme"}


def test_a_repository_may_name_a_command_by_the_word_users_type(capabilities):
    repo_policy = parse(
        """
        version: 1
        tasks:
          deny: [merge]
        """
    )
    assert repo_policy.deny == {"merge_bot"}
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert "merge_bot" not in policy.effective(repo_policy)


def test_unknown_names_are_reported_not_applied(capabilities):
    repo_policy = parse(
        """
        version: 1
        tasks:
          deny: [gen_addons_readmee]
        """
    )
    assert repo_policy.unknown == ["gen_addons_readmee"]
    assert repo_policy.deny == set()
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        # a typo in a deny list fails open; the config command reports it
        assert "gen_addons_readme" in policy.effective(repo_policy)


@pytest.mark.parametrize(
    "text,expected_error",
    [
        ("version: 1\ntasks: [1, 2]", "'tasks' must be a mapping"),
        ("version: 2\n", "unsupported version"),
        ("- a\n- b\n", "must be a mapping at the top level"),
        ("version: 1\ntasks:\n  deny: nope\n", "'tasks.deny' must be a list"),
        ("version: 1\ntasks: {,,}", "could not be parsed"),
    ],
)
def test_malformed_files_fall_back_to_the_defaults(capabilities, text, expected_error):
    repo_policy = parse(text)
    assert repo_policy.error is not None
    assert expected_error in repo_policy.error
    assert repo_policy.found is True
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective(repo_policy) == policy.effective()


def test_an_empty_file_is_not_an_error(capabilities):
    repo_policy = parse("")
    assert repo_policy.error is None
    assert repo_policy.found is True
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective(repo_policy) == policy.effective()


def test_fetch_falls_back_to_the_defaults_when_github_fails(capabilities, mocker):
    mocker.patch("oca_github_bot.policy.repository", side_effect=Exception("boom"))
    with set_config(GITHUB_TOKEN="DUMMY"):
        repo_policy = policy.fetch("OCA", "some-repo", "16.0")
    assert repo_policy.found is False
    assert repo_policy.allow == set()
    with set_config(BOT_TASKS=["all"], BOT_TASKS_DISABLED=[""]):
        assert policy.effective(repo_policy) == policy.effective()


def test_fetch_is_cached_per_repository_and_ref(capabilities, mocker):
    repository = mocker.patch(
        "oca_github_bot.policy.repository", side_effect=Exception("boom")
    )
    with set_config(GITHUB_TOKEN="DUMMY"):
        policy.fetch("OCA", "some-repo", "16.0")
        policy.fetch("OCA", "some-repo", "16.0")
        assert repository.call_count == 1
        policy.fetch("OCA", "some-repo", "17.0")
        assert repository.call_count == 2


def test_fetch_does_not_call_github_without_a_token(capabilities, mocker):
    repository = mocker.patch("oca_github_bot.policy.repository")
    with set_config(GITHUB_TOKEN=None):
        repo_policy = policy.fetch("OCA", "some-repo", "16.0")
    repository.assert_not_called()
    assert repo_policy is policy.DEFAULT_POLICY
