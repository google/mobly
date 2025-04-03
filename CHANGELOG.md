# Mobly Release History

# Mobly Release 1.13: SL4A Deprecation and Test Suite Improvements
Removed SL4A related code. Improvements for defining test suites through the
`BaseSuite` class.

### New
* Enabled test selection and listing with test suite class.
* Support regex test case selecting for single test class.
* Support `fastboot` command execution with customized serial and binary path.
* Support getting service alias by service class.

### Breaking Changes
* Removal of SL4A code.
* Removal of the `generate_setup_tests` stage which is deprecated in 1.12.

### Fixes
* Better error message for snippet loading error.
* Updated documents and dostrings.

[Full list of changes](https://github.com/google/mobly/milestone/32?closed=1)


## Mobly Release 1.12.4: Improvements

Maintenance release with small improvements and fixes.

### New
* Introduced `apk_utils` module for Android apk install/uninstall.

### Fixes
* Bugs in snippet client.
* Noise in console output on Mac.

[Full list of changes](https://github.com/google/mobly/milestone/31?closed=1)


## Mobly Release 1.12.3: Proper Repeat and Retry Reporting
Bumping min Python version requirement to 3.11.
Modernized the repo's packaging mechanism.
Removed legacy code and dependencies.

### New
* Support am instrument options in snippet client.
* Support adb reverse in `AdbProxy`.
* Improved mechanism for tracking repeat and retry records in test report.

### Breaking Changes
* [Deprecation] `get_available_host_port` is now deprecated and will be removed
  in the next major release. Please rely on the OS to allocate ports.

### Fixes
* Eliminated redundant `fastboot` calls.

[Full list of changes](https://github.com/google/mobly/milestone/30?closed=1)


## Mobly Release 1.12.2: Improve Support for Custom Suites

Bug fixes and improvements to better support users who construct their own
suite based on `test_runner` APIs and `suite_runner`.

### Fixes
* Make print test case name feature usable.
* Ensure default log path exists.
* Missing info in test records are now populated.
* Enable Android devices in bootloader mode to be picked up in registration.

[Full list of changes](https://github.com/google/mobly/milestone/29?closed=1)


## Mobly Release 1.12.1: Minor Improvements and Fixes

### New
* A logger adapter that makes it easier for modules to add their own log line prefixes

### Fixes
* `is_emulator` property now works for Cuttlefish image
* Handle SIGTERM properly
* Fixed missing result fields and output directories

[Full list of changes](https://github.com/google/mobly/milestone/28?closed=1)


## Mobly Release 1.12: New Snippet Base Client and a New `pre_run` Stage

This release introduces the new generic Mobly snippet base client and the new
Android snippet client built on top. The new snippet base enables us to better
scale Mobly snippets across various platforms.

The old Android snippet client is now considered deprecated, and will be
removed in the following release. Please update your code accordingly:
* `snippet_client` -> `snippet_client_v2`
* `snippet_event` -> `mobly.snippet.callback_event`
* `callback_handler` -> `callback_handler_v2`

The `generate_setup_tests` stage is renamed to `pre_run` to better reflect its
true role: steps that happen before all the test case methods are finalized.
This is a pure rename with no functional changes. Please migrate your code as
the `generate_setup_tests` stage will stop working completely in the next
release.

### New
* Added the new Mobly snippet base client.
* Added the new Android snippet client v2 based on the new base client.
* Support changing Mobly's logger level to `DEBUG` via cli arg.
* Termination signal type is now included in result records.

### Breaking Changes
* The old Android snippet client is deprecated.
* The `generate_setup_tests` stage is now `pre_run`.

### Fixes
* Various issues in the Android snippet client.

[Full list of changes](https://github.com/google/mobly/milestone/27?closed=1)


## Mobly Release 1.11.1: Support Test Case `repeat` and `retry`.

### New
* Native support for `repeat` and `retry` of test cases.
* Additional assertion APIs.
* `android_device` now picks up `fastboot` devices if given `*`.

### Fixes
* Removed the usage of `psutil` in favor of native `Py3` features.

[Full list of changes](https://github.com/google/mobly/milestone/26?closed=1)


## Mobly Release 1.11: Py2 Deprecation and Repeat/Retry Support

This release focuses on code quality improvement, refactoring, and legacy
code removal.

Py2-specific workarounds and deprecated APIs are removed in this release.
We are also refactoring to use 2-space indentation and unit test system.

### New
* Framework support for test case level `repeat` and `retry`.

### Breaking Changes
* Removal of Py2 support
* Removal of the `monsoon` controller

### Fixes
* Various improvements in Android device controller
* More metadata collected for test runs

[Full list of changes](https://github.com/google/mobly/milestone/25?closed=1)


## Mobly Release 1.10.1: Incremental fixes

This release contains minor fixes and improvements.

### New
* API for taking screenshots in `AndroidDevice` 
* Option to change the logging verbosity of the Mobly snippet client. The
  default logging size is now capped.

### Fixes
* Resource leakage in `_print_test_name`.
* IDE compatibility.
* Bugs in unit tests.

[Full list of changes](https://github.com/google/mobly/milestone/24?closed=1)


## Mobly Release 1.10: Framework and `AndroidDevice` Output Improvements

*This is likely the last major release that preserves Py2 compatibility.*

### New
* `AndroidDevice` now has a new `is_emulator` property.
* Better multi-user support in `AndroidDevice`.
* Standardized logging and output file names.
* Improvement in `utils.concurrent_exec`.
* Support class-based decorator on Mobly test methods.

### Breaking Changes
Due to the standardization of output files for both Mobly and `AndroidDevice`
controller, if you have custom parser of Mobly outputs, you need to adjust
your parsing logic to accommodate the changes.

* Major change in output directory structure #650
* Names of `AndroidDevice`'s output files have been standardized #633
* Changed multiple references of `test_bed` to `testbed` in code #641

### Fixes
* `AndroidDevice`'s service manager behavior for reboot and USB disconnect.

[Full list of changes](https://github.com/google/mobly/milestone/23?closed=1)


## Mobly Release 1.9.1: Documentation Fix

Fix readthedocs documentation bug introduced in 1.9.
Strictly documentation fix, no code change.

[Full list of changes](https://github.com/google/mobly/milestone/22?closed=1)


## Mobly Release 1.9: UID Support; `AndroidDevice` and General Runner Improvements

### New
* Support specifying Unique Identifier (UID) for both static and generated test
  methods.

### Breaking Changes
* Detached logger lifecycle from `TestRunner#run`. Suite users have to
  explicitly use the new logger context around `TestRunner#run`.
* Removed the behavior of `BaseTestClass` as a context as it has been a no-op
  for several releases.
* [Deprecation] Removed `BaseTestClass#clean_up` which was deprecated in 1.8.1.
* [Deprecation] Code path for passing args directly into a test method, which
  was never used.
* [Deprecation] Service-related APIs deprecated in 1.8 are now removed,
  including `AndroidDevice#load_sl4a`.

### Fixes
* Bug fixes and reliability improvements in `AdbProxy`.
* Improved APIs for taking bugreports
* Improvements in `AndroidDevice` service management
* Improvements in `AndroidDevice`'s `getprop` calls, including caching.

[Full list of changes](https://github.com/google/mobly/milestone/21?closed=1)


## Mobly Release 1.8.1: Fix Final Cleanup Stage Error Capture

### Fixes
* Errors from the final clean up stage are now properly recorded.
  * NOTE: This may expose errors that have long existed in your tests. They are
    usually caused by your test interrupting controller object life cycle
    management. Fixing these issues would help keep your test env clean.
* Fixed docs config so `http://mobly.readthedocs.io` show all the classes
  properly.


## Mobly Release 1.8: Controller Management and `AndroidDevice` Service

### New
* Modularized controller management logic by introducing `ControllerManager`.
* Introduced the service mechanism in `AndroidDevice`, life cycles management
  of long-running processes for Android devices.
* Convenience method for creating per-test adb logcat
  `logcat.create_per_test_excerpt`.
* `AdbError` now has `serial` as a direct attribute.

### Deprecated
The following APIs in `AndroidDevice` are deprecated:
* `start_services` -> `ad.services.start_all`
* `stop_services` -> `ad.services.stop_all`
* `start_adb_logcat` -> `ad.services.logcat_start`
* `stop_adb_logcat` -> `ad.services.logcat_stop`

### Fixes
* `expects` APIs crashing in certain execution stages.
* `setup_class`'s record is not recorded correctly in summary yaml.
* Controller info recoding
* adb logcat crashes

[Full list of changes](https://github.com/google/mobly/milestone/18?closed=1)


## Mobly Release 1.7.5: Dependency Cleanup

### Fixes
* Only install test dependencies when running the unit tests.
* Allow `CallbackHandler.waitForEvent` to wait for longer than the max rpc
  timeout.

[Full list of changes.](https://github.com/google/mobly/milestone/19?closed=1)


## Mobly Release 1.7.4: Better debug logs
Added framework DEBUG level log generated by Mobly:
* Log test configuration at the beginning.
* Log boundaries of each execution stage.
* Log snippet client calls.

### New
* Support suffixing test class name in a suite.
* API to unload a single snippet from `AndroidDevice`.

### Fixes
* Fixes in `BaseTestClass`.
* Fixes for running on Windows.

[Full list of changes.](https://github.com/google/mobly/milestone/17?closed=1)


## 1.7.3: Windows support fixes

### New
  * `self.current_test_info` now exists for `setup_class` stage.
  * adb calls through `AdbProxy` can now propagate stderr.
  * Instrumentation runner now outputs timestamp for each test.

### Fixes
  * Fix several bugs for running on Windows.

[Full list of changes.](https://github.com/google/mobly/milestone/16?closed=1)


## 1.7.2: Custom Info in Test Summary

### New
  * Support adding additional blocks in test summary file.
  * `SnippetEvent` is now loggable.

### Fixes
  * Fix several bugs in error reporting.
  * Fix log persist crashing Mobly on certain devices.

[Full list of changes.](https://github.com/google/mobly/milestone/15?closed=1)


## 1.7.1: Bug Fixes

### New
  * Allow setting up logger before test class execution. Useful for suites.

### Fixes
  * Fix recording of `teardown_class` failures in new output format.
  * Properly handle calling `asserts.abort_all` in `on_fail`.
  * Minor fixes for Windows support.

[Full list of changes.](https://github.com/google/mobly/milestone/14?closed=1)


## 1.7: Expectation APIs and Instrumentation Test Runner

### New
  * APIs for specifying expectation in test for delayed test termination.
    `mobly.expects`
  * A runner class for easily running regular Instrumentation tests with Mobly.
    [Tutorial](https://github.com/google/mobly/blob/master/docs/instrumentation_tutorial.md).
  * API to get runtime test info during the test.
  * Support specifying file location and timeout in `take_bug_report`.
  * Support changing device serial during test. Needed for remote devices.
  * Allow adding custom controller info for `AndroidDevice`.

### Breaking Changes
  * Monsoon config format change:
    Old: `'Monsoon': [123, 456]` 
    New: `'Monsoon': [{'serial': 123}, {'serial': 456'}]`

### Deprecated
  * Old output files.

[Full list of changes.](https://github.com/google/mobly/milestone/13?closed=1)


## 1.6.1: New Output

### New
  * New output file scheme, with better clarity and streamable summary file.
  * Improved result reporting: more consistent, more debug info, no hiding
    errors.
  * adb commands now support timeout param.
    E.g. `adb.wait_for_device(timeout=10)`

### Breaking Changes
  * Signature change of procedure functions like `on_fail`.
    * Old: `on_fail(test_name, begin_time)`
    * New: `on_fail(record)`

### Deprecated
  * Old generated test code path
  * Support for old snippet protocol (v0)

Full list of fixes [here](https://github.com/google/mobly/milestone/12?closed=1).


## 1.5: New Snippet Startup Protocol
  * Improved compatibility between v1 snippets and older devices/emulators
  * Support temporarily disconnecting (without rebooting) Android devices from
    USB in a test, useful for power measurement.
  * Fixes critical bugs from 1.4.1


## 1.4.1 [DO NOT USE]: New Snippet Startup Protocol
  Warning: This release has multiple issues; please use 1.5.

  New
  * Support the new launch and connection mechanism in Snippet Lib 1.2.

  Fixes
  * a bug in `generate_tests` that prevents it to be called when wrapped in
    other functions.
  * a bug that exposed Mobly internal controller registry to tests.

  Deprecate
  * Old snippet launch protocol (V0)


## 1.4: Generated Test Revamp
  New
  * Brand new generated test. See `BaseTestClass.generate_tests`
    *Please switch to new one since we're deprecating the old one.*
  * Support creating test suites where each class has a different config.
  * Support usb id as device identifier.
  * The token that marks begin and end of the test in logs has changed from
    `[Test Case]` to `[Test]`.
  * Launch MBS without package name with `snippet_shell.py --mbs`
  * adb binary location can now be modified by test code.

  Fixes
  * Clear adb logcat cache before starting collection.
  * Use default `adb logcat` buffer. if you need additional logcat buffers, set
    `-b <buffer name>` with `adb_logcat_param` in the config for AndroidDevice.
  * Time out sooner when snippet server stops responding.

  Deprecate
  * Old generated tests (run_generated_tests)


## 1.3: Test Suite; Windows Support and Cli Shell Changes
  * Support running on Windows.
  * Add support for creating test suites.
  * Support UIAutomator in snippet.
  * Fixes to adb commands to avoid double-quoting and fix cross-platform issues.
      * adb commands are now run without local shell. For commands with more
        than one argument, pass in a list of arguments instead of a string. Eg
        `adb.logcat("-c -v")` becomes `adb.logcat(["-c", "-v"])`.
      * `utils.start_standing_process()` run without local shell by default
      * `utils.exe_cmd()` removed. Use `subprocess.check_output()` instead.


## 1.2.1: New Config Format and Async Rpc Support
  * Fixes critical bugs in 1.2


## 1.2 [DO NOT USE]: New Config Format and Async Rpc Support
  Warning: This release has multiple issues; please use 1.2.1.

  * New config format with clear compartmentalization of different types of
    configs.
  * Utilize yaml format instead of json for new config.
  * Added support for Mobly Snippet Lib's Asynchronous Rpc calls.
  * Added support for handling async events from async Rpc calls.
  * Various improvements and bug fixes.


## 1.1.2: SL4A Default No More
  * Stop making sl4a a default requirement.
  * Require explicitly starting sl4a with `AndroidDevice.load_sl4a`.
  * Fix in `android_device` and `snippet_client`
  * Fix various other minor issues.


## 1.1.1: AndroidDevice Controller Improvements
  * Bug fixes and improvements in AndroidDevice controller.


## 1.1: Snippet support
  * Add a client for making Rpc calls to apps built with [Mobly Snippet Library]
    (https://github.com/google/mobly-snippet-lib).
  * Add a controller lib for attenuators.
  * Add customizable log prefix tag in AndroidDevice for better device-level
    logging.


## 1.0: Initial release
