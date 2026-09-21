# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import pytest

from oca_github_bot import registry


@pytest.fixture
def empty_registry():
    """An empty registry, restored afterwards."""
    saved = registry.snapshot()
    registry.restore(({}, {}))
    yield registry
    registry.restore(saved)


def test_register_and_resolve(empty_registry):
    empty_registry.register("some_task")
    assert empty_registry.canonical("some_task") == "some_task"
    assert empty_registry.canonical("nope") is None
    assert empty_registry.get("some_task").kind == registry.TASK
    assert empty_registry.get("nope") is None


def test_aliases_resolve_to_the_canonical_name(empty_registry):
    empty_registry.register("merge_bot", kind=registry.COMMAND, aliases=("merge",))
    assert empty_registry.canonical("merge") == "merge_bot"
    assert empty_registry.get("merge").name == "merge_bot"


def test_registering_twice_merges(empty_registry):
    # a command is registered twice: by the @switchable on the task it starts,
    # then by the command itself
    empty_registry.register("merge_bot", kind=registry.TASK)
    empty_registry.register(
        "merge_bot",
        kind=registry.COMMAND,
        description="merge it",
        aliases=("merge",),
    )
    capability = empty_registry.get("merge_bot")
    assert capability.kind == registry.COMMAND  # the more specific kind wins
    assert capability.description == "merge it"
    assert capability.aliases == ("merge",)
    assert empty_registry.canonical("merge") == "merge_bot"


def test_opting_out_wins_when_merging(empty_registry):
    empty_registry.register("custom_task", default=False)
    empty_registry.register("custom_task", default=True)
    assert empty_registry.get("custom_task").default is False


def test_default_names_excludes_opt_in_capabilities(empty_registry):
    empty_registry.register("on_by_default")
    empty_registry.register("custom_task", default=False)
    assert empty_registry.default_names() == {"on_by_default"}


def test_unknown_kind_is_rejected(empty_registry):
    with pytest.raises(ValueError):
        empty_registry.register("some_task", kind="nonsense")


def test_the_real_registry_knows_the_shipped_capabilities():
    capabilities = registry.all_capabilities()
    # commands, and the alias a user actually types
    assert capabilities["merge_bot"].kind == registry.COMMAND
    assert registry.canonical("merge") == "merge_bot"
    assert registry.canonical("rebase") == "rebase_bot"
    assert registry.canonical("migration") == "migration_issue_bot"
    # steps of main_branch_bot, which are neither commands nor triggered alone
    assert capabilities["gen_addons_readme"].kind == registry.STEP
    assert capabilities["merge_bot_towncrier"].kind == registry.STEP
    # event triggered
    assert capabilities["mention_maintainer"].kind == registry.TASK
    # everything shipped is on by default
    assert registry.default_names() == set(capabilities)
