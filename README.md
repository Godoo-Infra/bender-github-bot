# Bender GitHub bot

[![CI status](https://github.com/Godoo-Infra/bender-github-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Godoo-Infra/bender-github-bot/actions/workflows/ci.yml)

A GitHub bot for Odoo addon repositories. It reacts to webhooks, runs scheduled
maintenance, and takes commands typed as pull request comments — merging,
rebasing, generating addon READMEs, icons, packaging files and wheels.

It collects in one place every operation that reacts to a GitHub event and
every operation that runs against a repository on a schedule, instead of
spreading them across cron jobs and ad-hoc scripts.

Forked from [OCA/oca-github-bot](https://github.com/OCA/oca-github-bot). What
this fork adds:

- **Commands are a registry**, so adding one means adding a module rather than
  editing a dispatch chain
- **A configurable command prefix**, `/benderbot` by default
- **Per-repository policy**, so one deployment can serve repositories that want
  different things from it
- **A nix flake**, so the whole stack runs with `nix run` and no docker

---

## Contents

- [What it does](#what-it-does)
- [Commands](#commands)
- [How to run this in your org](#how-to-run-this-in-your-org)
- [Configuration](#configuration)
- [Running the stack](#running-the-stack)
- [Development](#development)
- [Releasing](#releasing)
- [Credits](#credits)

---

## What it does

Automatically, in response to GitHub events:

| When | What happens |
| --- | --- |
| a pull request is opened | Mentions the declared maintainers of every addon it modifies, or comments a call for maintainers if an addon has none. |
| a pull request is closed | Deletes the source branch, when it was merged from a branch in the same repository. |
| a pull request's CI goes green | Adds the `needs review` label, unless the title starts with `wip:` or `[wip]`, or it carries the `work in progress` label. |
| a pull request is approved | Adds `approved` at `APPROVALS_REQUIRED` reviews (2 by default), then `ready to merge` once it is also `MIN_PR_AGE` days old (5 by default). |
| a push lands on a main branch | Regenerates the addons table in `README.md`, each addon's `README.rst`, missing addon icons, and the packaging files — `pyproject.toml` from Odoo 17.0, `setup.py` before it — then pushes the result back. |

On a schedule, for every repository of every organisation in `GITHUB_ORG`:

- the main branch operations above, nightly, followed by building wheels and
  publishing them to a PEP 503 index by rsync, or to a package index with twine
- the `ready to merge` labelling, hourly

## Commands

Anyone with push access, or declared in the `maintainers` key of every addon a
pull request touches, can type a command as a pull request comment:

| Command | What it does |
| --- | --- |
| `/benderbot merge major\|minor\|patch\|nobump` | Merges the pull request onto a temporary branch off the target branch, waits for that branch's CI, optionally bumps the version of every modified addon, updates the changelog with `oca-towncrier`, runs the main branch operations, builds and publishes a wheel, then fast-forwards the target branch. |
| `/benderbot rebase` | Rebases the pull request on its target branch. |
| `/benderbot migration MODULE_NAME` | Adds the pull request to the "Migration to version x.y" issue of the target branch, creating the issue and the milestone if needed, and sets the milestone on the pull request. |
| `/benderbot config` | Reports which capabilities are enabled for this repository, and why. |

The prefix is configurable; see [Configuration](#configuration).

## How to run this in your org

### 1. Create the bot's GitHub account

The bot acts as a real GitHub account. Give it write access to the repositories
it will work on — it comments, labels, creates labels and milestones, pushes
generated files, pushes to target branches when merging, and deletes merged
branches.

Create a token for that account: the `repo` scope for a classic token, or read
and write on contents, issues and pull requests for a fine-grained one.

### 2. Configure the deployment

Copy `environment.sample` to `.env` and fill in the five settings that must be
set before anything works:

```sh
GITHUB_SECRET=   # the secret you will configure on the webhook
GITHUB_LOGIN=    # the bot account's login
GITHUB_TOKEN=    # its token
GIT_NAME=        # the author of the commits the bot pushes
GIT_EMAIL=
```

Add `GITHUB_ORG` — a comma separated list — to enable the scheduled work.
Without it the scheduler runs nothing but its heartbeat.

### 3. Start it

With nix:

```sh
nix build .#stack     # first build compiles the dependencies, once
nix run .
```

or with docker:

```sh
docker compose up --build
```

Either way you get redis, the webhook listener on port 8080, a celery worker
and a scheduler. See [Running the stack](#running-the-stack) for the details.

### 4. Put the listener on the internet

GitHub has to reach it. A reverse proxy in production; a tunnel while you are
trying things out:

```sh
ngrok http 8080
```

### 5. Point each repository at the bot

Add a webhook, on the repository or on the organisation to cover all of them at
once:

| Setting | Value |
| --- | --- |
| Payload URL | the bot's public URL; it serves the webhook at `/` |
| Content type | `application/json` |
| Secret | the same value as `GITHUB_SECRET` |
| Events | *Pull requests*, *Pull request reviews*, *Issue comments*, *Pushes*, *Statuses*, *Check runs*, *Check suites* |

No other event is handled. Issue comments are what carry the commands, so
leaving them out makes every command silently do nothing.

### 6. Check what the repositories expect

Three things have to hold, and they are easy to miss:

**Main branches are named after an Odoo series.** The generators only run on
branches named `x.y`, from `MAIN_BRANCH_BOT_MIN_VERSION` (`11.0`) upwards.
Branches named `master`, `main` or `x.y` are never deleted by the bot.

**CI runs on pushed branches, not only on pull requests.** The merge bot does
not use the GitHub merge button: it pushes
`<target>-benderbot-merge-pr-<pr>-by-<user>-bump-<mode>`, waits for that branch
to go green, then fast-forwards the target branch onto it. If your CI only
builds pull requests, the bot waits for a status that never arrives.

**The bot can push to the target branch.** A protected branch needs the bot
allowed to bypass the restriction, or the final push is refused after the CI
has already run.

Anything else keyed on the merge branch name — CI filters, branch protection
patterns — has to match `*-benderbot-merge-*`.

### 7. Decide what each repository gets

By default every repository gets everything. To narrow it, drop a `.bender.yml`
in the repository:

```yaml
version: 1
tasks:
  deny: [merge_bot]
```

Then ask the bot what it resolved to, rather than working it out:

```
/benderbot config
```

Nothing else needs creating by hand: the bot adds the labels it uses and
creates the milestone for a migration issue if it is missing.

## Configuration

### Environment variables

Set in `.env`. Everything not listed here is in `environment.sample`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GITHUB_SECRET` | *required* | Shared secret configured on the GitHub webhook. |
| `GITHUB_LOGIN` | *required* | Login of the account the bot acts as. |
| `GITHUB_TOKEN` | *required* | Token for that account. |
| `GIT_NAME`, `GIT_EMAIL` | *required* | Author identity for the commits the bot pushes. |
| `GITHUB_ORG` | empty | Organisations the scheduled work runs against. Empty means none. |
| `BOT_COMMAND_PREFIX` | `/benderbot` | What invokes a command. A list runs several at once, which is how you keep the old prefix alive during a rename. |
| `BOT_CONFIG_FILENAME` | `.bender.yml` | Name of the per-repository policy file. |
| `BOT_TASKS` | `all` | Capabilities this deployment offers at all. |
| `BOT_TASKS_DISABLED` | empty | The fleet-wide kill switch. Nothing a repository asks for can re-enable what is named here. |
| `HTTP_HOST`, `HTTP_PORT` | all interfaces, `8080` | Where the webhook listener binds. The nix stack defaults the host to `127.0.0.1`. |
| `BROKER_URI` | `redis://queue` | The celery broker. The nix stack rewrites this to the local redis. |
| `APPROVALS_REQUIRED` | `2` | Approving reviews before the `approved` label. |
| `MIN_PR_AGE` | `5` | Days before the `ready to merge` label. |
| `GITHUB_STATUS_IGNORED`, `GITHUB_CHECK_SUITES_IGNORED` | see sample | Statuses and check suites that do not count towards green. |
| `SIMPLE_INDEX_ROOT` | empty | PEP 503 index to rsync wheels into. Empty disables it. |
| `OCABOT_TWINE_REPOSITORIES` | empty | Indexes to twine-upload wheels to. Empty disables it. |
| `MODULE_LABEL_COLOR` | `#ffc` | Colour of the per-addon labels the bot creates. |
| `SENTRY_DSN` | empty | Enables Sentry reporting when set. |

`ODOO_URL`, `ODOO_DB`, `ODOO_LOGIN` and `ODOO_PASSWORD` are read into
configuration but nothing uses them: `odoo_client.py` has no importers.

### Per-repository policy

A repository may carry a policy file naming what applies to it:

```yaml
version: 1
tasks:
  allow: [deploy_staging]        # adds to the default set
  deny:  [merge_bot, rebase_bot] # removes from it
```

Resolution, highest precedence first:

1. `BOT_TASKS_DISABLED`, which is absolute
2. the repository's `deny`
3. the repository's `allow`
4. the default set, which is everything shipped, narrowed by `BOT_TASKS`

Without a file, the default set applies. A capability may be named by its
canonical name (`merge_bot`) or by the word a user types (`merge`).

Two properties worth knowing:

- The file **selects** from capabilities the bot has registered. It never
  describes what a task does, so write access to one repository cannot become
  code execution against the bot's token.
- It is read from the **target branch** of a pull request, never the branch
  proposing the change, so a pull request cannot grant itself a capability in
  the same diff that uses it. Policy may therefore differ per Odoo series.

An unreadable or malformed file falls back to the defaults; `/benderbot config`
reports the parse error and any name it did not recognise.

### Custom commands and tasks

Site-specific actions live in [`custom`](./src/oca_github_bot/custom), one
module per feature holding the celery task and the command that starts it.
Every module there is imported at startup, so adding an action means adding a
file and restarting.

Register them with `default=False`, on both the `@switchable` and the command
class, so that adding one changes nothing until a repository allows it by name.

The design and its reasoning are in
[`docs/design/configurable-commands.md`](./docs/design/configurable-commands.md).

## Running the stack

### With nix

The flake provides everything the bot shells out to — python 3.12, redis, git,
rsync, pandoc and the commands from
[maintainer-tools](https://github.com/OCA/maintainer-tools) — so nix with
flakes enabled is the only prerequisite:

```sh
nix build .#stack   # the first build compiles the dependencies locally
nix run .
```

That runs redis (`queue`), the webhook listener (`bot`), the celery `worker`
and the scheduler (`beat`), the last three waiting for redis to answer a ping.
The same command drives a stack that is already up:

```sh
nix run . -- process list
nix run . -- attach
nix run . -- down
```

State lives in `./data`, where the docker composition's bind mounts put it, so
both ways of running share the git clone cache: `data/queue` holds the redis
append-only file, `data/cache` the bare clone of each repository,
`data/simple-index` the locally published wheels, `data/logs` the
process-compose log.

It reads the same `.env`, rewriting the two settings that only make sense
inside a container: a `BROKER_URI` of `redis://queue` becomes the local redis,
and a `SIMPLE_INDEX_ROOT` under `/app/run` becomes `./data/simple-index`. Set
`OCABOT_REDIS_PORT` if 6379 is taken.

To work against a local checkout of the maintainer tools:

```sh
nix run . --override-input maintainer-tools path:../maintainer-tools
```

### With docker compose

`docker compose up --build` starts the bot on port 8080, a `worker`, a `beat`
scheduler and a `flower` monitoring UI on port 5555.

Export `UID` and `GID` first. The composition runs its containers as
`"${UID}:${GID}"`, and in a shell that does not export them — fish, among
others — that becomes `":"`, so the containers run as root and leave root-owned
files in `./data`.

## Development

`nix develop` gives a shell with the bot's dependencies, the test dependencies,
the `oca-gen-*` commands and the stack itself as `oca-github-bot-stack`:

```sh
nix develop -c pytest                          # the test suite
nix develop -c pre-commit run --all-files
```

Without nix, `tox` runs the same tests, and `pre-commit install` sets up the
formatting hooks. Formatting is ruff; tests are pytest.

Where things live:

| Directory | What goes there |
| --- | --- |
| [`webhooks`](./src/oca_github_bot/webhooks) | Handlers for GitHub events. These must be quick, and should delegate real work to a task. |
| [`tasks`](./src/oca_github_bot/tasks) | [Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html), where the work happens. |
| [`commands`](./src/oca_github_bot/commands) | One module per command, discovered at import. |
| [`custom`](./src/oca_github_bot/custom) | Site-specific commands and tasks, kept apart so upstream merges do not conflict with them. |
| [`cron.py`](./src/oca_github_bot/cron.py) | The schedule, as [celery periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html). |

## Releasing

- `towncrier --version YYYYMMDD`
- commit the updated `HISTORY.rst` and the removed newsfragments
- `git tag vYYYYMMDD`
- `git push --tags`

## Credits

Forked from [OCA/oca-github-bot](https://github.com/OCA/oca-github-bot), built
and maintained by the [Odoo Community
Association](https://odoo-community.org) and its contributors:

- Stéphane Bidoul &lt;stephane.bidoul@acsone.eu&gt;
- Holger Brunn &lt;hbrunn@therp.nl&gt;
- Miquel Raïch &lt;miquel.raich@forgeflow.com&gt;
- Florian Kantelberg &lt;florian.kantelberg@initos.com&gt;
- Laurent Mignon &lt;laurent.mignon@acsone.eu&gt;
- Jose Angel Fentanez &lt;joseangel@vauxoo.com&gt;
- Simone Rubino &lt;simone.rubino@agilebg.com&gt;
- Sylvain Le Gal (https://twitter.com/legalsylvain)
- Tecnativa - Pedro M. Baeza
- Tecnativa - Víctor Martínez

Distributed under the MIT License, as the original is.
