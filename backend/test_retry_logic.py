import asyncio
import time
import sys
from utils.retry import (
  async_retry, with_timeout,
  retry_with_fallback
)

# Set stdout/stderr to UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def test_async_retry_success():
    call_count = 0
    
    @async_retry(max_attempts=3, base_delay=0.1)
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"
    
    result = await flaky_function()
    assert result == "success", f"Expected 'success', got {result}"
    assert call_count == 3, f"Expected call_count == 3, got {call_count}"
    print("✅ Test 1: Retries until success PASSED")
    return True

async def test_async_retry_fails_all():
    @async_retry(max_attempts=3, base_delay=0.1)
    async def always_fails():
        raise Exception("Always fails")
    
    try:
        await always_fails()
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Always fails" in str(e), f"Unexpected error: {e}"
        print("✅ Test 2: Raises after all attempts PASSED")
    return True

async def test_async_retry_excluded():
    call_count = 0
    class BadInputError(Exception):
        pass
    
    @async_retry(
        max_attempts=3,
        base_delay=0.1,
        exclude_exceptions=(BadInputError,)
    )
    async def sensitive_function():
        nonlocal call_count
        call_count += 1
        raise BadInputError("Bad input!")
    
    try:
        await sensitive_function()
        assert False, "Should have raised BadInputError"
    except BadInputError:
        assert call_count == 1, f"Expected 1 call, got {call_count}"
        print("✅ Test 3: No retry on excluded PASSED")
    return True

async def test_with_timeout_fallback():
    async def slow_operation():
        await asyncio.sleep(5)
        return "finished"
    
    start = time.time()
    result = await with_timeout(
        slow_operation(),
        timeout_seconds=0.1,
        fallback="timeout_fallback",
        operation_name="slow test"
    )
    elapsed = time.time() - start
    
    assert result == "timeout_fallback", f"Expected fallback, got {result}"
    assert elapsed < 1.0, f"Waited too long: {elapsed}s"
    print("✅ Test 4: Timeout returns fallback PASSED")
    return True

async def test_with_timeout_success():
    async def fast_operation():
        await asyncio.sleep(0.01)
        return "fast result"
    
    result = await with_timeout(
        fast_operation(),
        timeout_seconds=5.0,
        fallback="not used",
        operation_name="fast test"
    )
    
    assert result == "fast result", f"Expected 'fast result', got {result}"
    print("✅ Test 5: Fast operation succeeds PASSED")
    return True

async def test_retry_with_fallback_returns_fallback():
    async def always_fails():
        raise Exception("Failure!")
    
    result = await retry_with_fallback(
        func=always_fails,
        max_attempts=2,
        base_delay=0.1,
        fallback={"error": "used fallback"},
        operation_name="test fallback"
    )
    
    assert result == {"error": "used fallback"}, f"Expected fallback dict, got {result}"
    print("✅ Test 6: Fallback returned PASSED")
    return True

async def test_exponential_delays():
    delays_recorded = []
    call_count = 0
    
    @async_retry(
        max_attempts=3,
        base_delay=2.0,
        exponential=True
    )
    async def record_delays():
        nonlocal call_count
        call_count += 1
        delays_recorded.append(time.time())
        if call_count < 3:
            raise Exception("fail")
        return "done"
    
    await record_delays()
    
    assert len(delays_recorded) == 3, f"Expected 3 timestamps, got {len(delays_recorded)}"
    delay1 = delays_recorded[1] - delays_recorded[0]
    delay2 = delays_recorded[2] - delays_recorded[1]
    
    # We use a lower bound to account for sleep granularity
    assert delay1 >= 1.8, f"Expected delay1 around 2.0s, got {delay1}"
    assert delay2 >= 3.8, f"Expected delay2 around 4.0s, got {delay2}"
    print("✅ Test 7: Exponential delays PASSED")
    return True

async def run_retry_tests():
    print("=========================================")
    print("Testing retry utilities...")
    print("=========================================")
    await test_async_retry_success()
    await test_async_retry_fails_all()
    await test_async_retry_excluded()
    await test_with_timeout_fallback()
    await test_with_timeout_success()
    await test_retry_with_fallback_returns_fallback()
    await test_exponential_delays()
    print("=========================================")
    print("✅ All retry tests complete")
    print("=========================================")

if __name__ == "__main__":
    asyncio.run(run_retry_tests())
