##############
OCA GitHub bot
##############

.. image:: https://results.pre-commit.ci/badge/github/OCA/oca-github-bot/master.svg
   :target: https://results.pre-commit.ci/latest/github/OCA/oca-github-bot/master
   :alt: pre-commit.ci status
.. image:: https://github.com/OCA/oca-github-bot/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/OCA/oca-github-bot/actions/workflows/ci.yml
   :alt: GitHub CI status

The goal of this project is to collect in one place:

* all operations that react to GitHub events,
* all operations that act on GitHub repos on a scheduled basis.

This will make it easier to review changes, as well as monitor and manage
these operations, compared to the current situations where these functions
are spread across cron jobs and ad-hoc scripts.

**Table of contents**

.. contents::
   :local:

Features
========

On pull request open
--------------------

Mention declared maintainers that addons they maintain are being modified.

Comment with a call for maintainers if there are no declared maintainer.

On pull request close
---------------------

Auto-delete pull request branch
  When a pull request is merged from a branch in the same repo,
  the bot deletes the source branch.

On push to main branches
------------------------

Repo addons table generator in README.md
  For addons repositories, update the addons table in README.md.

Addon README.rst generator
  For addons repositories, generate README.rst from readme fragments
  in each addon directory, and push changes back to github.

Addon icon generator
  For addons repositories, put default OCA icon in each addon that don't have
  yet any icon, and push changes back to github.

setup.py generator
  For addons repositories, run setuptools-odoo-make-defaults, and push
  changes back to github.

These actions are also run nightly on all repos.

Also nightly, wheels are generated for all addons repositories and rsynced
to a PEP 503 simple index or twine uploaded to compatible indexes.

On Pull Request review
----------------------

When there are two approvals, set the ``approved`` label.
When the PR is at least 5 days old, set the ``ready to merge`` label.

On Pull Request CI status
-------------------------

When the CI in a Pull Request goes green, set the ``needs review`` label,
unless it has ``wip:``  or ``[wip]`` in it's title.

Commands
--------

One can ask the bot to perform some tasks by entering special commands
as merge request comments.

``/benderbot merge`` followed by one of ``major``, ``minor``, ``patch`` or ``nobump``
can be used to ask the bot to do the following:

* merge the PR onto a temporary branch created off the target branch
* merge when tests on the rebased branch are green
* optionally bump the version number of the addons modified by the PR. (e.g. 19.0. ``major`` . ``minor`` . ``patch``)
* when the version was bumped, udate the changelog with ``oca-towncrier``
* run the main branch operations (see above) on it
* when the version was bumped, generate a wheel, rsync it to a PEP 503
  simple index root, or upload it to one or more indexes with twine

``/benderbot rebase`` can be used to ask the bot to do the following:

* rebase the PR on the target branch

``/benderbot migration``, followed by the module name, performing the following:

* Look for an issue in that repository with the name "Migration to version
  ``{version}``", where ``{version}`` is the name of the target branch.
* Add or edit a line in that issue, linking the module to the pull request
  (PR) and the author of it.
* TODO: When the PR is merged, the line gets ticked.
* Put the milestone corresponding to the target branch in the PR.

TODO (help wanted)
------------------

See our open `issues <https://github.com/OCA/oca-github-bot/issues>`_,
pick one and contribute!


Developing new features
=======================

The easiest is to look at examples.

New webhooks are added in the `webhooks <./src/oca_github_bot/webhooks>`_ directory.
Webhooks execution time must be very short and they should
delegate the bulk of their work as delayed tasks, which have
the benefit of not overloading the machine and having proper
error handling and monitoring.

Tasks are in the `tasks <./src/oca_github_bot/tasks>`_ directory. They are `Celery tasks
<http://docs.celeryproject.org/en/latest/userguide/tasks.html>`_.

Tasks can be scheduled, in `cron.py <./src/oca_github_bot/cron.py>`_, using the `Celery periodic tasks
<http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html>`_ mechanism.

Running it
==========

Environment variables
---------------------

First create and customize a file named ``.env``,
based on `environment.sample <./environment.sample>`_.

Tasks performed by the bot can be specified by setting the ``BOT_TASKS``
variable. This is useful if you want to use this bot for your own GitHub
organisation.

You can also disable a selection of tasks, using ``BOT_TASKS_DISABLED``. This
is the fleet-wide kill switch: nothing a repository asks for can re-enable
what it names.

``BOT_COMMAND_PREFIX`` sets the word that invokes a command, ``/benderbot`` by
default. It accepts a list, so a second prefix can run alongside the first
during a rename::

  BOT_COMMAND_PREFIX=/benderbot,/ocabot

Per-repository policy
---------------------

A repository may carry a policy file, ``.bender.yml`` by default
(``BOT_CONFIG_FILENAME``), naming what applies to it::

  version: 1
  tasks:
    allow: [deploy_staging]        # adds to the default set
    deny:  [merge_bot, rebase_bot] # removes from it

Without the file, the default set applies, which is everything the bot ships
with. ``deny`` wins over ``allow``, and ``BOT_TASKS_DISABLED`` wins over both.

The file only selects from capabilities the bot has registered; it never
describes what a task does. It is read from the **target branch** of a pull
request, so a pull request cannot grant itself a capability in the same diff
that uses it, and policy may differ per Odoo series.

Ask the bot what is in effect, rather than working it out::

  /benderbot config

Custom commands and tasks
-------------------------

Site-specific actions live in `custom <./src/oca_github_bot/custom>`_, one
module per feature, holding the celery task and the command that starts it.
Every module there is imported at startup, so adding an action means adding a
file and restarting.

Register custom capabilities with ``default=False``, on both the
``@switchable`` and the command class, so that adding one changes nothing
until a repository allows it by name.

The design and its rationale are in
`docs/design/configurable-commands.md <./docs/design/configurable-commands.md>`_.

Using docker-compose
--------------------

``docker-compose up --build`` will start

* the bot, listening for webhooks calls on port 8080
* a celery ``worker`` to process long running tasks
* a celery ``beat`` to launch scheduled tasks
* a ``flower`` celery monitoring tool on port 5555

The bot URL must be exposed on the internet through a reverse
proxy and configured as a GitHub webhook, using the secret configured
in ``GITHUB_SECRET``.

Getting started with nix
------------------------

The flake provides everything the bot shells out to -- python 3.12, redis,
git, rsync, pandoc and the commands from `maintainer-tools
<https://github.com/OCA/maintainer-tools>`_ -- so nix with flakes enabled is
the only prerequisite.

1. Create ``.env`` from `environment.sample <./environment.sample>`_. Five
   variables have to be filled in before the bot can do anything:

   ``GITHUB_SECRET``
     the secret shared with the GitHub webhook
   ``GITHUB_LOGIN``
     the login of the account the bot acts as
   ``GITHUB_TOKEN``
     a token for that account
   ``GIT_NAME`` and ``GIT_EMAIL``
     the author identity for the commits the bot pushes

   Add ``GITHUB_ORG`` to enable the scheduled tasks -- the nightly main
   branch bot and the hourly ``ready to merge`` tagging. Without it the
   scheduler runs nothing but its heartbeat.

2. Warm the build. The first one compiles the python 3.12 dependencies
   locally, as nixpkgs only caches the default interpreter's package set::

     nix build .#stack

3. Start the stack::

     nix run .

   This brings up redis (``queue``), the webhook listener (``bot``, on
   ``HTTP_PORT``, default 8080), the celery ``worker`` and the celery
   scheduler (``beat``), the last three waiting for redis to answer a ping.

4. Expose the listener, so that GitHub can reach it: a reverse proxy in
   production, or a tunnel while developing::

     ngrok http 8080

5. Configure each repository the bot should act on, as described in
   `Setting up a repository for the bot`_.

The same command drives a stack that is already running, locating it by a
socket path derived from the checkout::

  nix run . -- process list
  nix run . -- attach
  nix run . -- down

State lives in ``./data``, where the docker composition's bind mounts put it,
so both ways of running share the git clone cache: ``data/queue`` holds the
redis append-only file, ``data/cache`` the bare clone the bot keeps of each
repository, ``data/simple-index`` the locally published wheels, and
``data/logs`` the process-compose log.

The stack reads the same ``.env`` as the docker composition, and rewrites the
two settings that only make sense inside a container: a ``BROKER_URI`` of
``redis://queue`` becomes the local redis, and a ``SIMPLE_INDEX_ROOT`` under
``/app/run`` becomes ``./data/simple-index``. Set ``OCABOT_REDIS_PORT`` if
6379 is already taken.

``nix develop`` gives a shell with the bot's dependencies, the test
dependencies, the ``oca-gen-*`` commands and the stack itself as
``oca-github-bot-stack``, so ``pytest`` and ``pre-commit run --all-files``
work directly. The maintainer tools are a flake input, pinned to the revision
the ``Dockerfile`` installs; to work against a local checkout of them::

  nix run . --override-input maintainer-tools path:../maintainer-tools

Setting up a repository for the bot
-----------------------------------

The bot account
~~~~~~~~~~~~~~~

``GITHUB_TOKEN`` must belong to an account with write access to the
repository. The bot comments on pull requests, adds labels, creates labels
and milestones, pushes generated files to main branches, pushes to the target
branch when merging, and deletes merged branches. With a classic token that
is the ``repo`` scope; with a fine-grained token, read and write on contents,
issues and pull requests.

The webhook
~~~~~~~~~~~

Add a webhook on the repository -- or on the organisation, to cover all of
them at once -- pointing at the bot:

* **Payload URL** -- the public URL of the bot, which serves the webhook at ``/``
* **Content type** -- ``application/json``
* **Secret** -- the same value as ``GITHUB_SECRET``
* **Events** -- *Pull requests*, *Pull request reviews*, *Issue comments*,
  *Pushes*, *Statuses*, *Check runs* and *Check suites*

No other event is handled. Issue comments are what carry the ``/benderbot``
commands, so leaving them out makes every command silently do nothing.

Branches
~~~~~~~~

The main branch operations only run on branches named after an Odoo series,
``x.y``, from ``MAIN_BRANCH_BOT_MIN_VERSION`` (default ``11.0``) upwards.
From ``GEN_PYPROJECT_MIN_VERSION`` (default ``17.0``) the bot generates
``pyproject.toml`` rather than ``setup.py``. Branches named ``master``,
``main`` or ``x.y`` are never deleted by the bot.

What ``/benderbot merge`` needs
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The merge bot does not use the GitHub merge button. It pushes a temporary
branch named ``<target>-ocabot-merge-pr-<pr>-by-<user>-bump-<mode>`` to the
repository, waits for the CI to go green on that branch, then fast-forwards
the target branch onto it and deletes the temporary branch. Two consequences
for the repository:

* the CI must run on pushed branches, not only on pull requests, or the bot
  waits for a status that never arrives;
* the bot account must be able to push to the target branch. A protected
  branch needs the bot allowed to bypass the restriction, otherwise the final
  push is refused after the CI has already run.

``GITHUB_STATUS_IGNORED`` and ``GITHUB_CHECK_SUITES_IGNORED`` list the
statuses and check suites that do not count towards green.

Who may invoke commands
~~~~~~~~~~~~~~~~~~~~~~~

A ``/benderbot`` command is honoured when the commenter has push access to the
repository, or is declared in the ``maintainers`` key of every addon the pull
request modifies. ``MAINTAINER_CHECK_ODOO_RELEASES`` lists the branches
searched for that declaration.

Labels and milestones
~~~~~~~~~~~~~~~~~~~~~

Nothing has to be created by hand. The bot adds ``needs review`` when the CI
goes green, ``approved`` once a pull request has ``APPROVALS_REQUIRED``
approving reviews (default 2), ``ready to merge`` once it is also
``MIN_PR_AGE`` days old (default 5), and ``bot is merging ⏳`` then
``merged 🎉`` while merging. It also creates one label per modified addon at
repository level, coloured with ``MODULE_LABEL_COLOR``. ``/benderbot migration``
creates the milestone named after the target branch, and the "Migration to
version x.y" issue, if they do not exist yet.

One label is read rather than written: ``work in progress`` on a pull request
suppresses ``needs review``, as does a title starting with ``wip:`` or
``[wip]``.

Development
===========

This project uses `black <https://github.com/ambv/black>`_
as code formatting convention, as well as isort and flake8.
To make sure local coding convention are respected before
you commit, install
`pre-commit <https://github.com/pre-commit/pre-commit>`_ and
run ``pre-commit install`` after cloning the repository.

To run tests, type ``tox``. Test are written with pytest.

Here is a recommended procedure to test locally:

* Prepare an ``environment`` file by cloning and adapting ``environment.sample``.
* Load ``environment`` in your shell, for instance with bash:

.. code::

  set -o allexport
  source environment
  set +o allexport

* Launch the ``redis`` message queue:

.. code::

  docker run -p 6379:6379 redis

* Install the `maintainer tools <https://github.com/OCA/maintainer-tools>`_ and add the generated binaries to your path:

.. code::

  PATH=/path/to/maintainer-tools/env/bin/:$PATH

* Create a virtual environment and install the project in it:

.. code::

  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt -e .

* Then you can debug the two processes in your favorite IDE:

  - the webhook server: ``python -m oca_github_bot``
  - the task worker: ``python -m celery --app=oca_github_bot.queue.app  worker --pool=solo --loglevel=INFO``

* To expose the webhook server on your local machine to internet,
  you can use `ngrok <https://ngrok.com/>`_
* Then configure a GitHub webhook in a sandbox project in your organization
  so you can start receiving webhook calls to your local machine.

Releasing
=========

To release a new version, follow these steps:
- ``towncrier --version YYYYMMDD``
- git commit the updated `HISTORY.rst` and removed newfragments
- ``git tag vYYYYMMDD``
- ``git push --tags``

Contributors
============

* Stéphane Bidoul <stephane.bidoul@acsone.eu>
* Holger Brunn <hbrunn@therp.nl>
* Miquel Raïch <miquel.raich@forgeflow.com>
* Florian Kantelberg <florian.kantelberg@initos.com>
* Laurent Mignon <laurent.mignon@acsone.eu>
* Jose Angel Fentanez <joseangel@vauxoo.com>
* Simone Rubino <simone.rubino@agilebg.com>
* Sylvain Le Gal (https://twitter.com/legalsylvain)
* Tecnativa - Pedro M. Baeza
* Tecnativa - Víctor Martínez

Maintainers
===========

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.
