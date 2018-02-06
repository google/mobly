# Mobly release history

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
