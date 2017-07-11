# Mobly release history

### 1.5: New Snippet Startup Protocol
  * Fixes critical bugs in 1.4.1
  * Improved compatibility between v1 snippets and older devices/emulators
  * Ability to reconnect to snippet app after USB disconnection


### 1.4.1 [DO NOT USE]: New Snippet Startup Protocol
  New
  * Support the new launch and connection mechanism in Snippet Lib 1.2.

  Fixes
  * a bug in `generate_tests` that prevents it to be called when wrapped in other functions.
  * a bug that exposed Mobly internal controller registry to tests.

  Warning: This release has multiple issues; please use 1.5.


### 1.4: Generated Test Revamp
  New
  * Brand new generated test. See `BaseTestClass.generate_tests`
    *Please switch to new one since we're deprecating the old one.*
  * Support creating test suites where each class has a different config.
  * Support usb id as device identifier.
  * The token that marks begin and end of the test in logs has changed from `[Test Case]` to `[Test]`.
  * Launch MBS without package name with `snippet_shell.py --mbs`
  * adb binary location can now be modified by test code.

  Fixes
  * Clear adb logcat cache before starting collection.
  * Use default `adb logcat` buffer. if you need additional logcat buffers, set `-b <buffer name>` with `adb_logcat_param` in the config for AndroidDevice.
  * Time out sooner when snippet server stops responding.


### 1.3: Test Suite; Windows Support and Cli Shell Changes
  * Support running on Windows.
  * Add support for creating test suites.
  * Support UIAutomator in snippet.
  * Fixes to adb commands to avoid double-quoting and fix cross-platform issues.
      * adb commands are now run without local shell. For commands with more than one argument, pass in a list of arguments instead of a string. Eg adb.logcat(“-c -v”) becomes adb.logcat([“-c”, “-v”]).
      * utils.start_standing_process run without local shell by default
      * utils.exe_cmd() removed. Use subprocess.check_output() instead.


### 1.2.1: New Config Format and Async Rpc Support
  * Fixes a critical bugs in 1.2


### 1.2 [DO NOT USE]: New Config Format and Async Rpc Support
  * New config format with clear compartmentalization of different types of configs.
  * Utilize yaml format instead of json for new config.
  * Added support for Mobly Snippet Lib's Asynchronous Rpc calls.
  * Added support for handling async events from async Rpc calls.
  * Various improvements and bug fixes.

  Warning: This release has multiple issues; please use 1.2.1.


### 1.1.2: SL4A Default No More
  * Stop making sl4a a default requirement.
  * Require explicitly starting sl4a with `AndroidDevice.load_sl4a`.
  * Fix in `android_device` and `snippet_client`
  * Fix various other minor issues.


### 1.1.1: AndroidDevice Controller Improvements
  * Bug fixes and improvements in AndroidDevice controller.


### 1.1: Snippet support
  * Add a client for making Rpc calls to apps built with [Mobly Snippet Library](https://github.com/google/mobly-snippet-lib).
  * Add a controller lib for attenuators.
  * Add customizable log prefix tag in AndroidDevice for better device-level logging.


### 1.0: Initial release
