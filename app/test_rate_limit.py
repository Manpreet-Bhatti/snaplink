from fastapi import HTTPException
import main


class FakeRedis:
    def __init__(self):
        self.counts = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, ttl):
        pass


class FakeRequest:
    headers = {}
    client = None


def test_rate_limiter_blocks_after_limit():
    original = main.redis_client
    main.redis_client = FakeRedis()
    try:
        check = main.rate_limiter("test", 2)
        req = FakeRequest()
        check(req)
        check(req)
        try:
            check(req)
            assert False, "3rd call should have raised"
        except HTTPException as e:
            assert e.status_code == 429
    finally:
        main.redis_client = original


if __name__ == "__main__":
    test_rate_limiter_blocks_after_limit()
    print("ok")
