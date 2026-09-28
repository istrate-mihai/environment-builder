#!/usr/bin/env python3
"""Small HTTP wrapper around the validator, used for the minikube deployment.

  GET  /health    -> 200 "ok"
  POST /validate  -> body = YAML config; 200 if valid, 422 with the errors if not
"""
from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

from validate import DEFAULT_SUPPORTED, load_supported, validate

MAX_BODY_BYTES = 64 * 1024
SUPPORTED = load_supported(DEFAULT_SUPPORTED)
log = logging.getLogger("validator-api")


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict | str) -> None:
        is_json = isinstance(payload, dict)
        body = (json.dumps(payload, indent=2) if is_json else payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json" if is_json else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        if self.path == "/health":
            self._send(200, "ok")
        elif self.path == "/supported":
            self._send(200, {name: spec["versions"] for name, spec in SUPPORTED.items()})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/validate":
            self._send(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_BODY_BYTES:
            self._send(413, {"error": "config too large"})
            return

        try:
            config = yaml.safe_load(self.rfile.read(length))
        except yaml.YAMLError as exc:
            self._send(400, {"valid": False, "errors": [f"invalid YAML: {exc}"]})
            return

        techs, errors = validate(config, SUPPORTED)
        if errors:
            self._send(422, {"valid": False, "errors": errors})
        else:
            self._send(200, {"valid": True, "technologies": [t.__dict__ for t in techs]})

    def log_message(self, fmt: str, *args: object) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    port = int(os.environ.get("PORT", "8080"))
    log.info("Listening on :%d", port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
