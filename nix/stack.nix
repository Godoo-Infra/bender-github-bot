# The dev stack: the four docker-compose services, run by process-compose.
{
  lib,
  writeShellApplication,
  formats,
  cacert,
  git,
  openssh,
  pandoc,
  process-compose,
  redis,
  rsync,
  pythonEnv,
  maintainer-tools,
}:

let
  celery = "${pythonEnv}/bin/celery --app=oca_github_bot.queue.app";

  # Everything the bot shells out to at runtime: git/rsync/openssh from
  # github.py and pypi.py, the oca-gen-* commands from main_branch_bot.py.
  toolchain = lib.makeBinPath [
    pythonEnv
    maintainer-tools
    git
    openssh
    pandoc
    redis
    rsync
  ];

  dependsOnQueue = {
    queue.condition = "process_healthy";
  };

  restartOnFailure = {
    restart = "on_failure";
    backoff_seconds = 2;
    max_restarts = 10;
  };

  config = {
    version = "0.5";

    processes = {
      # docker-compose: queue (redis:4-alpine)
      queue = {
        command = lib.concatStringsSep " " [
          "redis-server"
          "--appendonly yes"
          "--auto-aof-rewrite-min-size 64mb"
          "--auto-aof-rewrite-percentage 10"
          "--dir \"$OCABOT_DATA/queue\""
          "--bind 127.0.0.1"
          "--port \"$OCABOT_REDIS_PORT\""
          "--save ''"
        ];
        readiness_probe = {
          exec.command = "redis-cli -p \"$OCABOT_REDIS_PORT\" ping";
          initial_delay_seconds = 1;
          period_seconds = 2;
          timeout_seconds = 2;
          failure_threshold = 15;
        };
        availability = restartOnFailure;
      };

      # docker-compose: bot -- the aiohttp webhook listener
      bot = {
        command = "${pythonEnv}/bin/python -m oca_github_bot";
        depends_on = dependsOnQueue;
        availability = restartOnFailure;
      };

      # docker-compose: worker
      worker = {
        command = "${celery} worker --concurrency=2 --loglevel=INFO";
        depends_on = dependsOnQueue;
        availability = restartOnFailure;
      };

      # docker-compose: beat -- scheduled tasks from src/oca_github_bot/cron.py
      beat = {
        # --schedule keeps celerybeat-schedule out of the working directory.
        command = "${celery} beat --loglevel=INFO --schedule \"$OCABOT_DATA/celerybeat-schedule\"";
        depends_on = dependsOnQueue;
        availability = restartOnFailure;
      };
    };
  };

  configFile = (formats.yaml { }).generate "process-compose.yaml" config;
in
writeShellApplication {
  name = "oca-github-bot-stack";

  runtimeInputs = [ process-compose ];

  text = ''
    # Run from the checkout unless told otherwise; state lives in ./data,
    # exactly where the docker composition's bind mounts put it.
    root=''${OCABOT_ROOT:-$PWD}

    if [ ! -f "$root/.env" ]; then
      echo "oca-github-bot: no .env in $root" >&2
      echo "  cp environment.sample .env   # then fill in GITHUB_* and GIT_*" >&2
      exit 1
    fi

    # Parse .env the way docker's env_file does -- KEY=VALUE taken literally --
    # rather than sourcing it: values such as GIT_NAME are not shell-quoted,
    # and .env should not be able to run code.
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in
        "" | \#*) continue ;;
        *=*) ;;
        *) continue ;;
      esac
      key=''${line%%=*}
      value=''${line#*=}
      case "$key" in
        *[!A-Za-z0-9_]*) continue ;;
      esac
      # docker compose strips one layer of matching quotes
      case "$value" in
        \"*\") value=''${value#\"}; value=''${value%\"} ;;
        \'*\') value=''${value#\'}; value=''${value%\'} ;;
      esac
      export "$key=$value"
    done < "$root/.env"

    OCABOT_DATA="$root/data"
    OCABOT_REDIS_PORT=''${OCABOT_REDIS_PORT:-6379}
    export OCABOT_DATA OCABOT_REDIS_PORT

    # docker-compose runs the containers as "''${UID}:''${GID}", which expands to
    # ":" in any shell that does not export UID (fish, among others) -- the
    # containers then run as root and leave root-owned files in ./data. Say so
    # plainly instead of failing later with a bare EACCES from redis.
    for dir in queue cache simple-index logs; do
      if ! mkdir -p "$OCABOT_DATA/$dir" 2>/dev/null || [ ! -w "$OCABOT_DATA/$dir" ]; then
        echo "oca-github-bot: $OCABOT_DATA/$dir is not writable by $(id -un)" >&2
        echo "  owner: $(stat -c '%U:%G' "$OCABOT_DATA/$dir" 2>/dev/null || echo "could not create it")" >&2
        echo "  fix:   sudo chown -R \"$(id -u):$(id -g)\" \"$OCABOT_DATA\"" >&2
        exit 1
      fi
    done

    # The docker composition points these at paths inside the image; rewrite
    # them for a local run so a stock .env works unchanged.
    case "''${BROKER_URI:-redis://queue}" in
      redis://queue*) BROKER_URI="redis://127.0.0.1:$OCABOT_REDIS_PORT/0" ;;
    esac
    case "''${SIMPLE_INDEX_ROOT:-}" in
      /app/run/*) SIMPLE_INDEX_ROOT="$OCABOT_DATA/simple-index" ;;
    esac
    export BROKER_URI SIMPLE_INDEX_ROOT

    # docker-compose published the webhook port as 127.0.0.1:8080 only; without
    # a HTTP_HOST aiohttp would listen on every interface.
    export HTTP_HOST="''${HTTP_HOST:-127.0.0.1}"

    # github.py caches bare clones under appdirs.user_cache_dir("oca-mqt");
    # in the container that resolved to /app/run/.cache -> ./data/cache.
    export XDG_CACHE_HOME="$OCABOT_DATA/cache"

    # The python env below is self-contained; an inherited PYTHONPATH (from a
    # nix shell, say) would only leak foreign site-packages into the bot and
    # into the venv build_wheels.py provisions.
    unset PYTHONPATH

    export PATH="${toolchain}:$PATH"
    export SSL_CERT_FILE="''${SSL_CERT_FILE:-${cacert}/etc/ssl/certs/ca-bundle.crt}"
    export GIT_SSL_CAINFO="$SSL_CERT_FILE"

    # process-compose's own API listens on 8080 by default, which is the port
    # the bot wants; keep it off TCP altogether. The socket lives in TMPDIR
    # because a unix socket path is limited to ~108 bytes, which a checkout
    # nested a few directories deep would blow past. Deriving it from $root
    # means the client subcommands below find the server without being told.
    PC_SOCKET_PATH="''${TMPDIR:-/tmp}/oca-github-bot-$(printf '%s' "$root" | cksum | cut -d' ' -f1).sock"
    export PC_SOCKET_PATH

    # --config and --log-file belong to `up` alone, while --use-uds and
    # --unix-socket are global. Passing the first two to a client subcommand
    # ("down", "process list", "attach") fails with `unknown flag: --config`,
    # so configure `up` through its environment variables instead.
    case "''${1:-}" in
      "" | -* | up)
        export PC_CONFIG_FILES="${configFile}"
        export PC_LOG_FILE="$OCABOT_DATA/logs/process-compose.log"
        ;;
    esac

    exec process-compose --use-uds "$@"
  '';
}
