from fastapi import HTTPException
from main import hash_ip, hash_password, lookup_country, make_token, parse_ua, verify_password, verify_token

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


def test_password_hash_verifies_and_rejects():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)


def test_lookup_country_returns_none_without_a_db():
    # dev/CI has no GeoLite2 mmdb on disk — must degrade to None, not raise
    assert lookup_country("8.8.8.8") is None


def test_token_roundtrip_and_tamper_detection():
    token = make_token("user-123", "a@b.com")
    payload = verify_token(token)
    assert payload["sub"] == "user-123"
    try:
        verify_token(token + "x")
        assert False, "tampered token should not verify"
    except HTTPException as e:
        assert e.status_code == 401


if __name__ == "__main__":
    test_hash_ip_deterministic_and_not_reversible()
    test_ua_device_detection()
    test_lookup_country_returns_none_without_a_db()
    test_password_hash_verifies_and_rejects()
    test_token_roundtrip_and_tamper_detection()
    print("ok")
