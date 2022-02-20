"""TODO(minghaoli): Mock socket file for snippet client tests.

"""

from unittest import mock

MOCK_RESP = (
    b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1, '
    b'"callback": null}')

class MockSocketFile:

  def __init__(self, resp):
    self.resp = resp
    self.last_write = None

  def write(self, msg):
    self.last_write = msg

  def readline(self):
    return self.resp

  def flush(self):
    pass

def setup_mock_socket_file(mock_create_connection, resp=MOCK_RESP):
  """Sets up a fake socket file from the mock connection.

  Args:
    mock_create_connection: The mock method for creating a method.
    resp: (str) response to give. MOCK_RESP by default.

  Returns:
    The mock file that will be injected into the code.
  """
  fake_file = MockSocketFile(resp)
  fake_conn = mock.MagicMock()
  fake_conn.makefile.return_value = fake_file
  mock_create_connection.return_value = fake_conn
  return fake_file
