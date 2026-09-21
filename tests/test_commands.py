# Copyright (c) ACSONE SA/NV 2019
# Distributed under the MIT License (http://opensource.org/licenses/MIT).

import pytest

from oca_github_bot import registry
from oca_github_bot.commands import (
    COMMANDS,
    BotCommand,
    InvalidCommandError,
    InvalidOptionsError,
    OptionsError,
    RequiredOptionError,
    build_command_re,
    command,
    parse_commands,
    usage_text,
)
from oca_github_bot.commands import base as commands_base

from .common import set_config


def test_parse_command_not_a_command():
    with pytest.raises(InvalidCommandError):
        list(parse_commands("/benderbot not_a_command"))


def test_parse_command_multi():
    cmds = list(
        parse_commands("""
                ...
                /benderbot merge major
                /benderbot   merge   patch
                /benderbot merge patch
                /benderbot merge nobump, please
                /benderbot merge  minor, please
                /benderbot merge minor, please
                /benderbot merge nobump.
                /benderbot merge patch. blah
                /benderbot merge minor # ignored
                /benderbot rebase, please
                ...
            """)
    )
    assert [(cmd.name, cmd.options) for cmd in cmds] == [
        ("merge", ["major"]),
        ("merge", ["patch"]),
        ("merge", ["patch"]),
        ("merge", ["nobump"]),
        ("merge", ["minor"]),
        ("merge", ["minor"]),
        ("merge", ["nobump"]),
        ("merge", ["patch"]),
        ("merge", ["minor"]),
        ("rebase", []),
    ]


def test_parse_command_2():
    cmds = list(
        parse_commands(
            "Great contribution, thanks!\r\n\r\n"
            "/benderbot merge nobump\r\n\r\n"
            "Please forward port it to 12.0."
        )
    )
    assert [(cmd.name, cmd.options) for cmd in cmds] == [("merge", ["nobump"])]


def test_parse_command_merge():
    cmds = list(parse_commands("/benderbot merge major"))
    assert len(cmds) == 1
    assert cmds[0].name == "merge"
    assert cmds[0].bumpversion_mode == "major"
    cmds = list(parse_commands("/benderbot merge minor"))
    assert len(cmds) == 1
    assert cmds[0].name == "merge"
    assert cmds[0].bumpversion_mode == "minor"
    cmds = list(parse_commands("/benderbot merge patch"))
    assert len(cmds) == 1
    assert cmds[0].name == "merge"
    assert cmds[0].bumpversion_mode == "patch"
    cmds = list(parse_commands("/benderbot merge nobump"))
    assert len(cmds) == 1
    assert cmds[0].name == "merge"
    assert cmds[0].bumpversion_mode == "nobump"
    with pytest.raises(RequiredOptionError):
        list(parse_commands("/benderbot merge"))
    with pytest.raises(InvalidOptionsError):
        list(parse_commands("/benderbot merge nobump brol"))
    with pytest.raises(OptionsError):
        list(parse_commands("/benderbot merge brol"))


def test_parse_command_rebase():
    cmds = list(parse_commands("/benderbot rebase"))
    assert len(cmds) == 1
    assert cmds[0].name == "rebase"
    with pytest.raises(InvalidOptionsError):
        list(parse_commands("/benderbot rebase brol"))


def test_parse_command_comment():
    body = """
> {merge_command}
> Some comment {merge_command}
>> Double comment! {merge_command}
This is the one {merge_command} patch
    """.format(merge_command="/benderbot merge")
    command = list(parse_commands(body))
    assert len(command) == 1
    command = command[0]
    assert command.name == "merge"
    assert command.bumpversion_mode == "patch"


@pytest.fixture
def prefix(request, monkeypatch):
    """Parse commands with an alternative prefix."""
    monkeypatch.setattr(
        commands_base, "BOT_COMMAND_RE", build_command_re([request.param])
    )
    return request.param


@pytest.mark.parametrize("prefix", ["/benderbot", "/bender", "@bot"], indirect=True)
def test_parse_command_honours_the_configured_prefix(prefix):
    cmds = list(parse_commands(f"{prefix} merge patch"))
    assert [(cmd.name, cmd.options) for cmd in cmds] == [("merge", ["patch"])]


def test_parse_command_several_prefixes(monkeypatch):
    # a second prefix can run alongside the first, during a rename
    monkeypatch.setattr(
        commands_base, "BOT_COMMAND_RE", build_command_re(["/benderbot", "/bender"])
    )
    cmds = list(parse_commands("/benderbot merge patch\n/bender rebase"))
    assert [(cmd.name, cmd.options) for cmd in cmds] == [
        ("merge", ["patch"]),
        ("rebase", []),
    ]


@pytest.mark.parametrize("prefix", ["/bender"], indirect=True)
def test_the_old_prefix_stops_working_when_it_is_replaced(prefix):
    assert list(parse_commands("/benderbot merge patch")) == []


def test_parse_command_migration():
    cmds = list(parse_commands("/benderbot migration some_module"))
    assert len(cmds) == 1
    assert cmds[0].name == "migration"
    assert cmds[0].module == "some_module"
    with pytest.raises(InvalidOptionsError):
        list(parse_commands("/benderbot migration"))


def test_parse_command_config():
    cmds = list(parse_commands("/benderbot config"))
    assert len(cmds) == 1
    assert cmds[0].name == "config"
    assert cmds[0].always_available is True


def test_commands_are_registered_as_capabilities():
    assert COMMANDS["merge"].capability() == "merge_bot"
    assert registry.get("merge").kind == registry.COMMAND
    # the word a user types is an alias of the capability a policy file names
    assert registry.canonical("merge") == "merge_bot"


def test_usage_is_generated_from_the_registered_commands():
    usage = usage_text()
    for name in COMMANDS:
        assert name in usage


def test_usage_can_be_overridden_by_configuration():
    with set_config(OCABOT_USAGE="do not use this bot"):
        assert usage_text() == "do not use this bot"


def test_registering_a_command_twice_is_rejected():
    saved = registry.snapshot()
    try:

        @command
        class First(BotCommand):
            name = "duplicated"

        with pytest.raises(registry.DuplicateCapabilityError):

            @command
            class Second(BotCommand):
                name = "duplicated"

    finally:
        COMMANDS.pop("duplicated", None)
        registry.restore(saved)


def test_a_command_must_declare_a_name():
    with pytest.raises(ValueError):

        @command
        class Nameless(BotCommand):
            pass
