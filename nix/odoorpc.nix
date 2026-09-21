# odoorpc is not packaged in nixpkgs; it is a small pure-python XML-RPC/JSON-RPC
# client with no runtime dependencies outside the stdlib.
{
  lib,
  buildPythonPackage,
  fetchPypi,
  setuptools,
}:

buildPythonPackage rec {
  pname = "odoorpc";
  version = "0.10.1";
  pyproject = true;

  src = fetchPypi {
    pname = "OdooRPC";
    inherit version;
    hash = "sha256-0LxSTFuWB4EWVXW62cE9Ay1vlow8CSdicQRd27tIOqU=";
  };

  build-system = [ setuptools ];

  # The test suite talks to a live Odoo server.
  doCheck = false;

  pythonImportsCheck = [ "odoorpc" ];

  meta = {
    description = "Python module providing an easy way to pilot Odoo servers through RPC";
    homepage = "https://github.com/OCA/odoorpc";
    license = lib.licenses.lgpl3Plus;
  };
}
