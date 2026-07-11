import io
import json

import main


class FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode()

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_no_api_key_fails_open():
    original = main.os.environ.pop("GOOGLE_SAFE_BROWSING_API_KEY", None)
    try:
        assert main.check_safe_browsing("http://example.com") is True
    finally:
        if original is not None:
            main.os.environ["GOOGLE_SAFE_BROWSING_API_KEY"] = original


def test_flagged_url_returns_false():
    main.os.environ["GOOGLE_SAFE_BROWSING_API_KEY"] = "test-key"
    original = main.urllib.request.urlopen
    main.urllib.request.urlopen = lambda req, timeout=2: FakeResp(
        {"threats": [{"url": "http://evil.example.com", "threatTypes": ["MALWARE"]}]})
    try:
        assert main.check_safe_browsing("http://evil.example.com") is False
    finally:
        main.urllib.request.urlopen = original
        del main.os.environ["GOOGLE_SAFE_BROWSING_API_KEY"]


def test_api_unreachable_fails_open():
    main.os.environ["GOOGLE_SAFE_BROWSING_API_KEY"] = "test-key"
    original = main.urllib.request.urlopen

    def raise_timeout(req, timeout=2):
        raise TimeoutError("slow")
    main.urllib.request.urlopen = raise_timeout
    try:
        assert main.check_safe_browsing("http://example.com") is True
    finally:
        main.urllib.request.urlopen = original
        del main.os.environ["GOOGLE_SAFE_BROWSING_API_KEY"]


if __name__ == "__main__":
    test_no_api_key_fails_open()
    test_flagged_url_returns_false()
    test_api_unreachable_fails_open()
    print("ok")
