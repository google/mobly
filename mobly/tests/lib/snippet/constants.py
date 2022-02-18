MOCK_RESP = (
    b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1, '
    b'"callback": null}')
MOCK_RESP_WITHOUT_CALLBACK = (
    b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1}')
MOCK_RESP_TEMPLATE = (
    '{"id": %d, "result": 123, "error": null, "status": 1, "uid": 1, '
    '"callback": null}')
MOCK_RESP_UNKNOWN_STATUS = (
    b'{"id": 0, "result": 123, "error": null, "status": 0, '
    b'"callback": null}')
MOCK_RESP_WITH_CALLBACK = (
    b'{"id": 0, "result": 123, "error": null, "status": 1, "uid": 1, '
    b'"callback": "1-0"}')
MOCK_RESP_WITH_ERROR = (
    b'{"id": 0, "result": 123, "error": 1, "callback": null}')
MOCK_CMD_RESP_WITH_ERROR = b'{"id": 0, "error": 1, "status": 1, "uid": 1}'
MOCK_CMD_RESP_UNKNOWN_STATUS = (
    b'{"id": 0, "result": 123, "error": null, "status": 0, '
    b'"callback": null}')
