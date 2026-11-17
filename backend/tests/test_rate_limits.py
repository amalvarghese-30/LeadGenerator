import pytest
from app.services.rate_limit_service import RateLimitService, ResponseClassifier, HeaderAnalyzer


@pytest.mark.asyncio
async def test_rate_limit_recording_and_retry_after(test_db):
    service = RateLimitService(db=test_db)

    # 1. Successful request
    m1 = await service.record_request_metric(
        url_or_domain="https://api.example.com/v1/test",
        status_code=200,
        response_time_ms=120.0,
    )
    assert m1["status_code"] == 200
    assert m1["classification"] == "SUCCESS"

    # 2. Throttled request with Retry-After header
    m2 = await service.record_request_metric(
        url_or_domain="https://api.example.com/v1/test",
        status_code=429,
        response_time_ms=45.0,
        headers={"retry-after": "5"},
    )
    assert m2["status_code"] == 429
    assert m2["classification"] == "RATE_LIMITED"
    assert m2["retry_after"] == 5

    # 3. Policy recommendation should reflect backoff
    policy = await service.get_domain_policy("api.example.com")
    assert policy["recommended_delay_seconds"] >= 5.0
    assert policy["max_concurrency"] <= 2


@pytest.mark.asyncio
async def test_adaptive_backoff_and_domain_profiles(test_db):
    service = RateLimitService(db=test_db)

    # Trigger multiple 429s without explicit Retry-After
    for _ in range(3):
        await service.record_request_metric(
            url_or_domain="https://throttled-site.org/page",
            status_code=429,
            response_time_ms=80.0,
        )

    policy = await service.get_domain_policy("throttled-site.org")
    assert policy["max_concurrency"] == 1
    assert policy["status"] in ("cautious", "attention_required")


@pytest.mark.asyncio
async def test_summary_breakdown_and_pause_resume(test_db):
    service = RateLimitService(db=test_db)

    await service.record_request_metric("https://alpha.com", 200, 100.0)
    await service.record_request_metric("https://alpha.com", 429, 50.0)
    await service.record_request_metric("https://beta.com", 200, 200.0)
    await service.record_request_metric("https://beta.com", 500, 300.0)

    summary = await service.get_summary_metrics()
    assert summary["total_requests"] >= 4
    assert summary["successful_requests"] >= 2
    assert summary["throttled_429_count"] >= 1

    breakdown = await service.get_domain_breakdown()
    domains = [b["domain"] for b in breakdown]
    assert "alpha.com" in domains
    assert "beta.com" in domains

    # Test Pause and Resume
    pause_res = await service.pause_domain("alpha.com", "Manual maintenance")
    assert pause_res["is_paused"] is True

    pol = await service.get_domain_policy("alpha.com")
    assert pol["is_paused"] is True

    resume_res = await service.resume_domain("alpha.com")
    assert resume_res["is_paused"] is False


@pytest.mark.asyncio
async def test_header_analyzer_and_classifier():
    # Numeric seconds
    sec = HeaderAnalyzer.parse_retry_after("120")
    assert sec == 120

    # HTTP-date format
    date_val = "Wed, 21 Oct 2026 07:28:00 GMT"
    parsed_sec = HeaderAnalyzer.parse_retry_after(date_val)
    assert parsed_sec is not None

    # Classification
    c1, _ = ResponseClassifier.classify(200, {})
    assert c1 == "SUCCESS"

    c2, _ = ResponseClassifier.classify(429, {})
    assert c2 == "RATE_LIMITED"

    c3, _ = ResponseClassifier.classify(403, {"server": "cloudflare"})
    assert c3 == "BOT_PROTECTION"


@pytest.mark.asyncio
async def test_csv_export(test_db):
    service = RateLimitService(db=test_db)
    await service.record_request_metric("https://csv-test.com", 200, 120.0)
    csv_str = await service.export_logs_csv()
    assert "Timestamp,Domain,Endpoint" in csv_str
    assert "csv-test.com" in csv_str
