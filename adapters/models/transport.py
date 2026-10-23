"""Private trusted HTTP child. Input and output are bounded, never a shell.

No repository imports, filesystem requests or model-supplied endpoint selection.
"""
import json
import os
import sys
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run():
    request = json.loads(sys.stdin.buffer.read(262145))
    config, payload = request["config"], request["body"]
    secret = os.environ.get(config["key_env"], "")
    if not secret:
        return {"status": "REJECTED", "code": "credential_missing"}
    headers = {"Authorization": "Bearer " + secret, "Content-Type": "application/json"}
    message = urllib.request.Request(config["endpoint"], data=json.dumps(payload).encode(), headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect()).open(message, timeout=90) as response:
            raw = response.read(262145)
        if len(raw) > 262144:
            return {"status": "UNKNOWN", "code": "model_output_limit"}
        return {"status": "RECEIVED", "body": json.loads(raw)}
    except urllib.error.HTTPError as exc:
        # Never echo provider messages or request headers. Failed 5xx may be billed.
        return {"status": "REJECTED" if 400 <= exc.code < 500 else "UNKNOWN", "code": "http_" + str(exc.code)}
    except Exception:
        return {"status": "UNKNOWN", "code": "transport_interrupted"}


if __name__ == "__main__":
    try:
        result = run()
    except Exception:
        result = {"status": "UNKNOWN", "code": "transport_invalid"}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
