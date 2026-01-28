"""
Minimal HTTP proxy that forwards every request to https://api.openai.com/v1.
"""

import argparse
import base64
import json
import http.client
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

TARGET_HOST = "api.openai.com"
TARGET_BASE_PATH = "/v1"
LOG_BODY_PREVIEW_LIMIT = 4096
REDACTED_HEADERS = {"authorization", "proxy-authorization"}
REDACTED_RESPONSE_HEADERS = {"set-cookie"}
LOG_FILE_PATH = Path(__file__).resolve().parent / "openai_forwarder.log.jsonl"


class ForwardingHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self._forward()

    def do_POST(self):
        self._forward()

    def do_PUT(self):
        self._forward()

    def do_DELETE(self):
        self._forward()

    def do_PATCH(self):
        self._forward()

    def do_OPTIONS(self):
        self._forward()

    def do_HEAD(self):
        self._forward(expect_body=False)

    def _forward(self, expect_body: bool = True):
        try:
            upstream_path = self._build_target_path(self.path)
            print(f"Received {self.command} {self.path} from {self.client_address[0]}:{self.client_address[1]}")
            body = self._read_body()
            self._log_request_debug(body)
            response = self._send_upstream_request(upstream_path, body)
            self._relay_response(response, body, expect_body=expect_body)
        except Exception as exc:  # pragma: no cover - defensive catch-all
            self.send_error(502, f"Upstream forwarding failed: {exc}")
            self.log_error("proxy error: %s", exc)

    def _read_body(self):
        length_value = self.headers.get("Content-Length")
        if not length_value:
            return None

        try:
            length = int(length_value)
        except ValueError:
            return None

        if length <= 0:
            return None

        return self.rfile.read(length)

    def _send_upstream_request(self, path: str, body):
        connection = http.client.HTTPSConnection(TARGET_HOST)
        header_names = {k.lower() for k in self.headers.keys()}
        connection.putrequest(self.command, path, skip_host=True, skip_accept_encoding=True)

        for key, value in self.headers.items():
            lower = key.lower()
            if lower == "host":
                connection.putheader("Host", TARGET_HOST)
            elif lower == "connection":
                continue  # enforce close below
            else:
                connection.putheader(key, value)

        connection.putheader("Connection", "close")
        connection.endheaders()

        if body is not None:
            connection.send(body)

        return connection.getresponse()

    def _relay_response(self, upstream_response, request_body, expect_body: bool):
        raw_body = upstream_response.read()
        response_headers = upstream_response.getheaders()

        self._log_response_debug(upstream_response, response_headers, raw_body)
        self._write_jsonl_entry(
            request_body,
            response_headers,
            raw_body,
            upstream_response.status,
            upstream_response.reason,
        )

        self.send_response(upstream_response.status, upstream_response.reason)
        excluded = {"content-length", "transfer-encoding", "connection"}

        for key, value in response_headers:
            if key.lower() in excluded:
                continue
            self.send_header(key, value)

        self.send_header("Content-Length", str(len(raw_body)))
        self.send_header("Connection", "close")
        self.end_headers()

        if expect_body and raw_body:
            self.wfile.write(raw_body)

        upstream_response.close()

    def _build_target_path(self, original: str) -> str:
        if not original.startswith("/"):
            original = f"/{original}"

        if original.startswith(TARGET_BASE_PATH):
            return original

        base = TARGET_BASE_PATH.rstrip("/")
        return f"{base}{original}"

    def log_message(self, fmt, *args):
        # Mirror default logging but clearly label as proxy log.
        super().log_message("proxy: " + fmt, *args)

    def _log_request_debug(self, body):
        header_lines = "\n  ".join(self._format_header(k, v, REDACTED_HEADERS) for k, v in self.headers.items())
        print(">> Request headers:\n  " + (header_lines or "(none)"))
        print(f">> Request body ({self._describe_bytes(body)}):")
        print(self._decode_bytes(body))

    def _log_response_debug(self, upstream_response, headers, body: bytes):
        header_lines = "\n  ".join(self._format_header(k, v, REDACTED_RESPONSE_HEADERS) for k, v in headers)
        print(f"<< Response status: {upstream_response.status} {upstream_response.reason}")
        print("<< Response headers:\n  " + (header_lines or "(none)"))
        print(f"<< Response body ({self._describe_bytes(body)}):")
        print(self._decode_bytes(body))

    @staticmethod
    def _format_header(key: str, value: str, redacted_fields) -> str:
        display_value = value
        if key.lower() in redacted_fields:
            display_value = "[redacted]"
        return f"{key}: {display_value}"

    @staticmethod
    def _describe_bytes(data):
        length = len(data) if data else 0
        return f"{length} bytes" + (" (empty)" if length == 0 else "")

    @staticmethod
    def _decode_bytes(data):
        if not data:
            return "(empty)"
        preview = data[:LOG_BODY_PREVIEW_LIMIT]
        suffix = ""
        if len(data) > LOG_BODY_PREVIEW_LIMIT:
            suffix = f"\n... ({len(data) - LOG_BODY_PREVIEW_LIMIT} more bytes truncated)"
        try:
            decoded = preview.decode("utf-8")
        except UnicodeDecodeError:
            decoded = repr(preview)
        return decoded + suffix

    def _write_jsonl_entry(self, request_body, response_headers, response_body, status, reason):
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client": {"host": self.client_address[0], "port": self.client_address[1]},
            "request": {
                "method": self.command,
                "path": self.path,
                "headers": self._headers_to_loggable(self.headers.items(), REDACTED_HEADERS),
                "body": self._body_to_loggable(request_body),
            },
            "response": {
                "status": status,
                "reason": reason,
                "headers": self._headers_to_loggable(response_headers, REDACTED_RESPONSE_HEADERS),
                "body": self._body_to_loggable(response_body),
            },
        }

        try:
            with LOG_FILE_PATH.open("a", encoding="utf-8") as logfile:
                json.dump(record, logfile, separators=(",", ":"))
                logfile.write("\n")
        except OSError as exc:
            self.log_error("unable to write jsonl log: %s", exc)

    @staticmethod
    def _headers_to_loggable(headers, redacted_fields):
        return [
            {
                "name": key,
                "value": "[redacted]" if key.lower() in redacted_fields else value,
            }
            for key, value in headers
        ]

    @staticmethod
    def _body_to_loggable(data):
        if data is None:
            return None

        length = len(data)

        try:
            content = data.decode("utf-8")
            encoding = "utf-8"
            content_type = "text"
        except UnicodeDecodeError:
            content = base64.b64encode(data).decode("ascii")
            encoding = "base64"
            content_type = "binary"

        return {
            "length": length,
            "encoding": encoding,
            "type": content_type,
            "content": content,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Local interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    args = parser.parse_args()

    server_address = (args.host, args.port)
    httpd = HTTPServer(server_address, ForwardingHandler)

    print(f"Forwarding http://{args.host}:{args.port} -> https://{TARGET_HOST}{TARGET_BASE_PATH}")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down proxy")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
