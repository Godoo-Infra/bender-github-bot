{
  description = "OCA GitHub bot - development stack (process-compose)";

  inputs = {
    # Pinned to 26.05: nixpkgs-unstable ships setuptools 83, which dropped
    # pkg_resources and breaks setuptools-odoo 3.3.2 at import time.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

    # Same revision the Dockerfile installs into its /ocamt virtualenv.
    # Point it at a checkout to hack on both at once:
    #   nix run . --override-input maintainer-tools path:../maintainer-tools
    maintainer-tools = {
      url = "github:OCA/maintainer-tools/f70373fca6830e6536c3967ba5794311602b4bd4";
      flake = false;
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      maintainer-tools,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forAllSystems =
        f:
        nixpkgs.lib.genAttrs systems (
          system:
          f (
            import nixpkgs {
              inherit system;
              overlays = [ self.overlays.default ];
            }
          )
        );
    in
    {
      overlays.default = final: prev: {
        # pythonPackagesExtensions rather than overriding python312Packages:
        # only the former is picked up by python312.withPackages.
        pythonPackagesExtensions = prev.pythonPackagesExtensions ++ [
          (pyfinal: pyprev: {
            odoorpc = pyfinal.callPackage ./nix/odoorpc.nix { };
            oca-github-bot = pyfinal.callPackage ./nix/oca-github-bot.nix { };

            # The bot runs on 3.12 (as the Dockerfile does), and nixpkgs only
            # caches builds of the default interpreter's package set, so the
            # first build compiles these locally. Their test suites pull in
            # cassandra-driver, pymongo and friends, which costs far more than
            # the packages themselves.
            celery = pyprev.celery.overridePythonAttrs { doCheck = false; };
            kombu = pyprev.kombu.overridePythonAttrs { doCheck = false; };

            # setup.py caps this at <2 ("we use an old version of self-hosted
            # Sentry"), so honour the cap rather than the nixpkgs version.
            sentry-sdk = pyprev.sentry-sdk.overridePythonAttrs (old: rec {
              version = "1.45.1";
              src = pyfinal.fetchPypi {
                pname = "sentry_sdk";
                inherit version;
                hash = "sha256-oWyZfA9OPfY8D8XkIHzLGrN5AEM+D3L++IMV0xeCmiY=";
              };
              doCheck = false;
              # The 2.x expression's optional-dependency wiring does not apply.
              dontCheckRuntimeDeps = true;
            });
          })
        ];

        oca-maintainer-tools = final.callPackage ./nix/maintainer-tools.nix {
          src = maintainer-tools;
          version = "0-unstable-${builtins.substring 0 8 (maintainer-tools.lastModifiedDate or "19700101")}";
        };
      };

      packages = forAllSystems (
        pkgs:
        let
          inherit (pkgs) python312Packages;

          pythonEnv = pkgs.python312.withPackages (ps: [
            ps.oca-github-bot
            ps.pip # build_wheels.py provisions a venv at runtime
          ]);
        in
        rec {
          default = stack;

          stack = pkgs.callPackage ./nix/stack.nix {
            inherit pythonEnv;
            maintainer-tools = pkgs.oca-maintainer-tools;
          };

          inherit pythonEnv;
          oca-github-bot = python312Packages.oca-github-bot;
          oca-maintainer-tools = pkgs.oca-maintainer-tools;
        }
      );

      apps = forAllSystems (pkgs: {
        default = {
          type = "app";
          program = nixpkgs.lib.getExe self.packages.${pkgs.stdenv.hostPlatform.system}.stack;
        };
      });

      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.python312.withPackages (
              ps:
              ps.oca-github-bot.dependencies
              ++ [
                ps.pip
                ps.pytest
                ps.pytest-asyncio
                ps.pytest-cov
                ps.pytest-mock
                ps.pytest-vcr
              ]
            ))
            pkgs.oca-maintainer-tools
            self.packages.${pkgs.stdenv.hostPlatform.system}.stack
          ]
          ++ (with pkgs; [
            git
            openssh
            pandoc
            pre-commit
            process-compose
            redis
            rsync
          ]);

          shellHook = ''
            # Work against the checkout rather than an installed copy.
            #
            # This *overwrites* PYTHONPATH rather than prepending to it: python
            # packages in a shell (pre-commit, here) export their dependency
            # closure onto PYTHONPATH, and that closure is built for the
            # default interpreter. Left in place it leaks python 3.13
            # site-packages into every child process -- including the venv
            # build_wheels.py provisions, where it breaks `pip check`. The
            # console scripts carry their own wrapping and are unaffected.
            export PYTHONPATH="$PWD/src"
            export SSL_CERT_FILE="''${SSL_CERT_FILE:-${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt}"
            echo "oca-github-bot devShell: 'oca-github-bot-stack' runs redis + bot + worker + beat"
          '';
        };
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-tree);
    };
}
