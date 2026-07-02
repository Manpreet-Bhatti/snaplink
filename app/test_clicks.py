from main import hash_ip, parse_ua

MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"


def test_hash_ip_deterministic_and_not_reversible():
    a = hash_ip("1.2.3.4")
    b = hash_ip("1.2.3.4")
    assert a == b
    assert "1.2.3.4" not in a


def test_ua_device_detection():
    assert parse_ua(MOBILE_UA).is_mobile
    assert parse_ua(DESKTOP_UA).is_pc


if __name__ == "__main__":
    test_hash_ip_deterministic_and_not_reversible()
    test_ua_device_detection()
    print("ok")
