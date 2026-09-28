import json

from app.middleware import configure_logging, request_id_ctx
import logging


def test_logs_are_json_with_request_id(capsys):
    configure_logging("INFO")
    token = request_id_ctx.set("req-42")
    logging.getLogger("t").info("hello")
    request_id_ctx.reset(token)
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["message"] == "hello" and data["request_id"] == "req-42"
