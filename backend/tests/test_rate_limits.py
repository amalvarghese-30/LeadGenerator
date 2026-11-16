import pytest
from app.services.rate_limit_service import RateLimitService


@pytest.mark.asyncio
async def test_rate_limit_recording_and_retry_after():
    service = RateLimitService(db=None)

    # 1. Successful request
    m1 = await service.record_request_metric(
        url_or_domain="https://api.example.com/v1/test",
        status_code=200,
        response_time_ms=120.0,
    )
    assert m1["is_throttled"] is False
    assert m1["status_code"] == 200

    # 2. Throttled request with Retry-After header
    m2 = await service.record_request_metric(
        url_or_domain="https://api.example.com/v1/test",
        status_code=429,
        response_time_ms=45.0,
        headers={"retry-after": "5"},
    )
    assert m2["is_throttled"] is True
    assert m2["retry_after"] == 5
    assert "honor_retry_after_5s" in m2["action_taken"]

    # 3. Policy recommendation should reflect backoff
    policy = await service.get_domain_policy("api.example.com")
    assert policy["recommended_delay_seconds"] >= 5.0
    assert policy["max_concurrency"] <= 2
    assert policy["backoff_level"] == 1


@pytest.mark.asyncio
async def test_adaptive_backoff_exponential():
    service = RateLimitService(db=None)

    # Trigger multiple 429s without explicit Retry-After
    for _ in range(3):
        await service.record_request_metric(
            url_or_domain="https://throttled-site.org",
            status_code=429,
            response_time_ms=80.0,
        )

    policy = await service.get_domain_policy("throttled-site.org")
    assert policy["backoff_level"] == 3
    # 2^3 = 8 + jitter -> delay >= 8s
    assert policy["recommended_delay_seconds"] >= 8.0
    assert policy["max_concurrency"] == 1


@pytest.mark.asyncio
async def test_summary_and_domain_breakdown():
    service = RateLimitService(db=None)

    await service.record_request_metric("https://alpha.com", 200, 100.0)
    await service.record_request_metric("https://alpha.com", 429, 50.0)
    await service.record_request_metric("https://beta.com", 200, 200.0)
    await service.record_request_metric("https://beta.com", 500, 300.0)

    summary = await service.get_summary_metrics()
    assert summary["total_requests"] == 4
    assert summary["successful_requests"] == 2
    assert summary["throttled_429_count"] == 1
    assert summary["other_error_count"] == 1
    assert summary["error_percentage"] == 50.0

    breakdown = await service.get_domain_breakdown()
    assert len(breakdown) == 2
    domains = [b["domain"] for b in breakdown]
    assert "alpha.com" in domains
    assert "beta.com" in domains
