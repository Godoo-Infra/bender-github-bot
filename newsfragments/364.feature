Commands and tasks are now a registry rather than a dispatch chain: adding a
command means adding a module to ``oca_github_bot.commands``, or to
``oca_github_bot.custom`` for site-specific ones. The prefix that invokes a
command is configurable with ``BOT_COMMAND_PREFIX``, and the usage message is
generated from the registered commands.

A repository may carry a policy file (``.bender.yml``) allowing or denying
capabilities by name, read from the target branch of a pull request. The
``config`` command reports what is in effect.
