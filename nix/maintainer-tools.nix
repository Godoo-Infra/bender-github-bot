# OCA maintainer-tools. The bot shells out to these commands by name (see
# src/oca_github_bot/tasks/main_branch_bot.py), so they only need to be on
# PATH -- keeping them in their own derivation mirrors the Dockerfile's
# isolation between the bot's dependencies and the tools' dependencies.
#
# The source comes from the `maintainer-tools` flake input, pinned by default
# to the revision the Dockerfile installs. To build a local checkout instead:
#
#   nix run . --override-input maintainer-tools path:../maintainer-tools
{
  lib,
  python312Packages,
  pandoc,
  src,
  version,
}:

python312Packages.buildPythonApplication {
  pname = "oca-maintainers-tools";
  inherit src version;
  pyproject = true;

  # hatch-vcs derives the version from git metadata, which the source closure
  # does not carry.
  env.SETUPTOOLS_SCM_PRETEND_VERSION = "0.0.0";

  build-system = with python312Packages; [
    hatchling
    hatch-vcs
  ];

  dependencies = with python312Packages; [
    appdirs
    click
    docutils
    freezegun
    github3-py
    jinja2
    manifestoo-core
    polib
    pygments
    pypandoc
    pyyaml
    requests
    setuptools-odoo
    toml
    towncrier
    twine
    wheel
    whool
  ];

  # erppeek, selenium and pyproject-dependencies are declared dependencies of
  # the distribution but are only imported by tools the bot never invokes
  # (odoo_login, publish_modules). erppeek is not in nixpkgs, so drop them
  # rather than package a dependency nothing here uses.
  dontCheckRuntimeDeps = true;

  # pypandoc.ensure_pandoc_installed() downloads a pandoc release unless one is
  # already on PATH; oca-gen-addon-readme calls it for every markdown fragment.
  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath [ pandoc ]}"
  ];

  # pythonImportsCheck is inherited from dependencies via setup hooks here, which
  # drags in setuptools-odoo test fixtures; check the console scripts instead.
  dontUsePythonImportsCheck = true;

  postInstallCheck = ''
    $out/bin/oca-gen-addons-table --help > /dev/null
    $out/bin/oca-gen-addon-readme --help > /dev/null
    $out/bin/oca-gen-addon-icon --help > /dev/null
    $out/bin/oca-gen-metapackage --help > /dev/null
    $out/bin/oca-towncrier --help > /dev/null
  '';

  # No test suite is shipped in the wheel.
  doCheck = false;

  meta = {
    description = "Set of tools to help managing Odoo Community projects";
    homepage = "https://github.com/OCA/maintainer-tools";
    license = lib.licenses.agpl3Only;
  };
}
