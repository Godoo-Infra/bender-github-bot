{
  lib,
  buildPythonPackage,
  setuptools,
  setuptools-scm,
  aiohttp,
  appdirs,
  celery,
  flower,
  gidgethub,
  github3-py,
  lxml,
  odoorpc,
  packaging,
  redis,
  sentry-sdk,
  setuptools-odoo,
  twine,
  whool,
  version ? "20240706",
}:

buildPythonPackage {
  pname = "oca-github-bot";
  inherit version;
  pyproject = true;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../setup.py
      ../setup.cfg
      ../README.rst
      ../src
    ];
  };

  # setup.py uses setuptools_scm and there is no .git in the source closure.
  env.SETUPTOOLS_SCM_PRETEND_VERSION = version;

  build-system = [
    setuptools
    setuptools-scm
  ];

  dependencies = [
    aiohttp
    appdirs
    celery
    flower
    gidgethub
    github3-py
    lxml
    odoorpc
    packaging
    redis # celery[redis] extra
    sentry-sdk
    setuptools # build_wheels.py and setuptools-odoo need it at runtime
    setuptools-odoo
    twine
    whool
  ];

  pythonImportsCheck = [ "oca_github_bot" ];

  # Tests live outside the package and need the checkout; run them from the
  # devShell (pytest) instead.
  doCheck = false;

  meta = {
    description = "GitHub bot for the Odoo Community Association";
    homepage = "https://github.com/OCA/oca-github-bot";
    license = lib.licenses.mit;
    mainProgram = "oca-github-bot";
  };
}
