# Configurable commands and per-repo task policy

Status: implemented. Stages 1 to 3 below have landed; stage 4 is deferred.
What shipped differs from the proposal in two places, noted inline:
capability registration merges rather than rejecting a duplicate, and
commands are gated in a dispatch task rather than in the webhook.

## Goal

Make the bot's command surface extensible without editing its core, and let each
repository decide which of the bot's capabilities apply to it.

Three things are hardcoded today and this design addresses each:

1. the `/ocabot` prefix, compiled into a regex at `commands.py:12`;
2. the command set, an `if/elif` chain at `commands.py:59-67`;
3. the task set, which is process-global via `BOT_TASKS` (`config.py:60-63`).

## Non-goals

* Defining behaviour in configuration. The YAML selects from what the bot has
  registered; it never describes what a task does. See [Security](#security).
* Loading code at runtime. Adding a custom action requires a restart, which is
  accepted.
* Per-repo tuning of thresholds (`APPROVALS_REQUIRED`, `MIN_PR_AGE`) or labels.
  The mechanism below extends to them later; this design covers enable/disable.

## What exists today

Registration is by import side-effect: `oca_github_bot/__init__.py:5` imports
`cron`, `tasks` and `webhooks`, and each package's `__init__.py` names its
modules.

| layer | mechanism | extensible? |
| --- | --- | --- |
| GitHub event to handler | `gidgethub` router, `@router.register(...)` (`router.py:6`) | yes, already a registry |
| comment to command | `if/elif` on the command word (`commands.py:59-67`) | no |
| task on/off | `@switchable(name)` against `BOT_TASKS` (`config.py:17-33`) | globally only |

The 17 `@switchable` sites do not divide into "commands" and "tasks". Seven are
sub-steps of a larger operation -- `gen_addons_table`, `gen_addons_readme`,
`gen_addons_icon`, `setuptools_odoo`, `whool_init`, `gen_metapackage` are steps
inside `main_branch_bot_actions` (`tasks/main_branch_bot.py:100-119`), reached
from the push webhook, the nightly cron and the merge bot alike;
`merge_bot_towncrier` only runs inside a merge. Six are event-triggered and
three are command-triggered. This is why the schema below uses one flat
namespace: any split would have to file those seven under a category that
misrepresents them.

## Design

### 1. Registry

`commands.py` becomes a package, following the convention already used by
`tasks/` and `webhooks/`:

```
commands/__init__.py    framework: prefix regex, registry, BotCommand, errors
commands/merge.py       @command  -> merge_bot.merge_bot_start
commands/rebase.py      @command  -> rebase_bot.rebase_bot_start
commands/migration.py   @command  -> migration_issue_bot.migration_issue_start
```

Modules are discovered with `pkgutil.iter_modules` rather than listed by hand,
because the point of this layer is that adding a file is enough.

A command declares what it is, not how it is dispatched:

```python
@command
class Merge(BotCommand):
    name = "merge"                 # the word after the prefix
    switch = "merge_bot"           # the @switchable name it gates on
    kind = "command"               # command | event | step
    default = True                 # in the default set (see Resolution)
    help = "``merge major|minor|patch|nobump`` -- merge the pull request"
    required_choice = ["major", "minor", "patch", "nobump"]

    def delay(self, org, repo, pr, username, dry_run=False):
        merge_bot.merge_bot_start.delay(
            org, repo, pr, username, self.bumpversion_mode, dry_run=dry_run
        )
```

`BotCommand.create` becomes a dict lookup. `parse_commands` is unchanged.
`required_choice` covers the common case declaratively; `parse_options` remains
available for anything irregular (`migration` takes a free-form module name).

Two things follow immediately:

* **`OCABOT_USAGE` is generated from the registry.** Today it is hand-written at
  `config.py:117` and already drifts. Generated, the error a user sees when a
  command is rejected always matches reality -- which matters more once the
  command set is site-specific.
* **`kind` is recorded even though the schema ignores it**, so that the config
  command can group its output by trigger type, and so a group selector
  (`deny: ["@command"]`) can be added later without a migration.

### 2. Command prefix

`BOT_COMMAND_PREFIX`, default `/ocabot`, accepting a list so that a second
prefix can run alongside the first during a rename:

```
BOT_COMMAND_PREFIX=/ocabot,/bender
```

Each is `re.escape`d into the alternation that replaces the literal at
`commands.py:12`. `tests/test_commands.py` and `tests/test_on_command.py`
hardcode `/ocabot` and need parametrising.

### 3. Custom folder

Custom actions live in `src/oca_github_bot/custom/`, one module per feature,
auto-discovered the same way:

```
custom/__init__.py          discovery only
custom/deploy_staging.py    the celery task AND its @command registration
```

One module per feature rather than splitting across `custom/tasks/` and
`custom/commands/`: a custom action is almost always both, and splitting means
every feature is two files that have to agree.

The folder exists mainly for merge hygiene. This is a fork of an active
upstream; custom code in a directory upstream does not have means
`git merge upstream/master` will not conflict on it.

Custom modules register with `default = False`, so a new custom action is
inert until a repository allows it explicitly. Adding one cannot change
behaviour fleet-wide by accident.

### 4. Per-repo YAML

A file at the root of the target repository, named by `BOT_CONFIG_FILENAME`
(default `.bender.yml`):

```yaml
version: 1
tasks:
  allow: [deploy_staging]        # adds to the default set
  deny:  [merge_bot, rebase_bot] # removes from it
```

Both keys are optional; so is the file. `version` is required when the file
exists, and is the escape hatch if the schema ever has to change shape.

### 5. Resolution

Let `R` be the registered names, `D` the default set (`{n in R : n.default}`,
narrowed by `BOT_TASKS` when that is not `all`), and `G` the global deny list
(`BOT_TASKS_DISABLED`).

```
effective(repo) = ((D | repo.allow) - repo.deny) - G
```

Precedence, highest first:

| rank | source | why |
| --- | --- | --- |
| 1 | `BOT_TASKS_DISABLED` | operators keep a fleet-wide kill switch |
| 2 | repo `deny` | the restrictive statement wins |
| 3 | repo `allow` | opt in to custom or non-default actions |
| 4 | `BOT_TASKS` default set | today's behaviour, unchanged |

Deny beats allow within the file. A name in both is not an error -- it is
denied, and reported by the config command.

Worked example, with `BOT_TASKS=all`, `BOT_TASKS_DISABLED=gen_addons_icon`, and
the file above:

| name | in D | allow | deny | global deny | effective |
| --- | --- | --- | --- | --- | --- |
| `gen_addons_readme` | yes | | | | **on** |
| `gen_addons_icon` | yes | | | yes | **off** |
| `merge_bot` | yes | | yes | | **off** |
| `deploy_staging` | no (custom) | yes | | | **on** |
| `mention_maintainer` | yes | | | | **on** |

Names not in `R` are ignored and reported. A typo in `deny` therefore fails
open, which is the dangerous direction; the config command exists partly to
make that visible.

### 6. Fetching and caching

Read through the GitHub contents API, not a clone. The pattern is already in
the codebase at `manifest.py:268-287`, which reads a manifest at a ref with
`gh_repo.file_contents(path, ref=branch)` and degrades to `None`:

```python
config_file = gh_repo.file_contents(BOT_CONFIG_FILENAME, ref=branch)
```

One request per resolution against a 5000/hour budget. Cache on
`(org, repo, ref)` with a short TTL, in-process per worker to start; redis is
available if that proves insufficient.

Which ref:

| trigger | ref |
| --- | --- |
| pull request events and commands | the **target** branch, never the PR head |
| push and status events | the pushed branch |
| cron fan-out | the branch being processed |

Falling back to the repository's default branch when the ref has no file.

### 7. Enforcement points

**As implemented**, in two places rather than the four proposed. Every
switchable function turned out to name its arguments `org` and `repo`, even
where the order differs (`tag_needs_review` takes `org, pr, repo`), so they can
be found by name:

| path | where |
| --- | --- |
| everything switchable | inside `switchable` itself (`config.py`), which binds the call's arguments and resolves the policy of the repository it names |
| commands | `dispatch_command` (`commands/dispatch.py`), so that a denied command is answered rather than silently dropped |

Gating inside `switchable` covers the event tasks, the nightly fan-out and the
sub-steps in one place instead of editing seven webhook handlers and two cron
loops. The command path needs the second gate because a user deserves an
answer, and because deciding needs the pull request's target branch -- a
GitHub call, which does not belong in a webhook handler. The webhook still
parses, so a malformed command is reported at once.

`@switchable` stays as the global layer; per-repo resolution narrows within
it, and fails open if the policy cannot be read.

### 8. Security

The trust boundary is the thing to keep straight: the bot's token has write
access to **every** repository it serves, so anything a single repository can
make the bot do is a potential escalation across all of them.

* **Selection, not definition.** The YAML may only name capabilities the bot has
  registered. No shell strings, no command templates, no paths. Custom actions
  are code in the deployed image, reviewed and released like any other code.
* **Target branch only.** Reading config from the PR head would let a pull
  request enable commands for itself in the same diff that uses them. This
  mirrors `user_can_push` (`manifest.py:228`), which deliberately reads
  manifests from the target branch.
* **Global deny is absolute.** No repository file can re-enable something the
  deployment has switched off.
* **Who may invoke is unchanged.** Per-repo policy decides *what is available*;
  `user_can_push` still decides *who may ask for it*.

### 9. Observability

A `config` command that replies with the resolved policy:

```
/bender config
```

reporting the effective set grouped by `kind`, which ref the file was read from
(or that defaults applied), names that were not recognised, and any parse error.

With policy spread across N repositories, "why did the bot do nothing" is
otherwise answerable only by reading logs on the host. This is roughly thirty
lines and should land with the resolution layer, not after it.

### 10. Failure modes

| situation | behaviour |
| --- | --- |
| no file | default set, silently -- the normal case |
| malformed YAML | default set, warning logged; if a command was attempted, reply with the parse error |
| unknown `version` | treated as malformed |
| unrecognised names | ignored, listed by the config command |
| contents API fails | default set, warning logged -- config must not take the bot down |

Silent fallback on a malformed file is deliberately *not* silent at the point of
use: a user who types a command gets told why their file was ignored.

## Dependencies

PyYAML becomes a runtime dependency. It is not one today -- it arrives only via
maintainer-tools and the test extras. Add to `setup.py` and `requirements.txt`;
`nix/oca-github-bot.nix` gains `pyyaml`, which is already in nixpkgs.

Parse with `yaml.safe_load`.

## Rollout

Four stages, each independently shippable, the first two with no functional
change:

1. **Registry and prefix.** Convert `commands.py` to a package, add the
   decorator, generate `OCABOT_USAGE`, make the prefix configurable. Rider: fix
   `dry_run`, which is dead today -- parsed at `config.py:56`, read nowhere, and
   hardcoded to `False` at `commands.py:90-93` and `commands.py:103-104` even
   though the method accepts it. Having it work is what makes a custom action
   safe to test.
2. **Custom folder.** Add `custom/` with discovery and `default = False`.
3. **Per-repo policy.** Resolution, fetching, caching, enforcement points, and
   the `config` command together.
4. **Deferred, only when wanted.** Group selectors (`deny: ["@command"]`), an
   `only:` key, org-level defaults, per-repo thresholds and labels.

Repositories without a file keep today's behaviour at every stage, so stage 3 is
a no-op until someone adds one.

## Testing

* `tests/test_commands.py` parametrised over prefixes, including two at once.
* A table-driven test of `effective()` covering the precedence matrix above,
  including the deny-beats-allow case and unknown names.
* Registry tests: duplicate command `name` rejected at import; `switch`
  defaulting to `name`; custom modules defaulting to off. Registering the same
  *capability* twice merges instead of failing, because a command is registered
  both by the `@switchable` on its task and by the command class.
* Fetching tested against the existing `pytest-vcr` setup, as `manifest.py`'s
  API path already is.

## Open questions

* Should `allow` be able to name a capability the deployment has not put in
  `BOT_TASKS`, or only ones it has? The table above lets it (rank 3 beats rank
  4), which is what makes custom actions opt-in per repo. The stricter reading
  would require operators to list custom actions globally too.
* Does an org-level layer (defaults for `Godoo-Infra/*`) earn its complexity, or
  is flat per-repo plus a global default enough? Deferred until a concrete case.
