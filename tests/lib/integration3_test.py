from mobly import asserts
from mobly import base_test
from mobly import test_runner

from tests.lib import mock_controller


class Integration3Test(base_test.BaseTestClass):
    def setup_class(self):
        self.register_controller(mock_controller)
        asserts.fail('Setup failure.')

    def on_fail(self, record):
        asserts.abort_all('Skip tests.')

    def test_empty(self):
        pass


if __name__ == '__main__':
    test_runner.main()
