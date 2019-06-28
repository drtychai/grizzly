Grizzly
=======

Grizzly is a general purpose browser fuzzing harness made up of multiple modules.
The intention is to create a platform that can be extended by the creation of adapters
and target platforms to support different fuzzers that target browsers.
An adapter is used to wrap an existing fuzzer to allow it to be run via Grizzly.
Adapters take the content output by fuzzers and transform it (if needed) into a format that can
be served to and processed by the browser.
Cross platform compatibility should be maintained for Windows, Linux and OSX.
However not all features may be available.

Installation
------------
The following modules are required:
* https://github.com/MozillaSecurity/ffpuppet
* https://github.com/giampaolo/psutil

The FuzzManager module is required to support reporting results via FM:
 * https://github.com/MozillaSecurity/FuzzManager

FFPuppet must be installed first. Steps can be found [here](https://github.com/MozillaSecurity/ffpuppet#installation)

##### To install after cloning the repository
    pip install --user -e <grizzly_repository>

Fuzzing builds & prefs.js
-------------------------
Fuzzing builds can be found in [taskcluster](https://tools.taskcluster.net/index/gecko.v2.mozilla-central.latest.firefox) or the [fuzzfetch](https://github.com/MozillaSecurity/fuzzfetch) (**recommended**) tool can be used to download a build.

prefs.js files can be found [here](https://github.com/MozillaSecurity/fuzzdata/tree/master/settings/firefox) in the [fuzzdata](https://github.com/MozillaSecurity/fuzzdata) repository along with other fuzzing input and configuration files.

**NOTE:** prefs.js files must be used when running with Mozilla browsers.

Example
-------
To verify everything is installed and working correctly run the *no-op* adapter. If everything is working correctly the browser should launch and open the *harness* in the first tab and a second tab should open and close rapidly.

`python -m grizzly /path/to/browser/firefox no-op -p prefs/prefs-default-e10s.js`

Target platforms
-------
Other target platforms can be defined as [setuptools entry-points](https://setuptools.readthedocs.io/en/latest/setuptools.html#dynamic-discovery-of-services-and-plugins),
using the name "grizzly_targets".  Targets must implement `grizzly.target.Target`.
