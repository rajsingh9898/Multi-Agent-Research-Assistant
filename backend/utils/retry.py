import asyncio
import logging
import time
import functools
from typing import Type, Tuple, Callable, Any

logger = logging.getLogger(__name__)

def async_retry(
  max_attempts: int = 3,
  base_delay: float = 2.0,
  exponential: bool = True,
  exceptions: Tuple[Type[Exception], ...] = (Exception,),
  exclude_exceptions: Tuple[Type[Exception], ...] = (),
  on_retry: Callable = None
):
  """
  Decorator for async functions that should retry on failure.
  
  Args:
    max_attempts: Total attempts (not retries)
    base_delay: Seconds before first retry
    exponential: If True, delay *= base on each retry
    exceptions: Exception types that trigger retry
    exclude_exceptions: Exception types that DON'T retry
    on_retry: Optional callback(attempt, error, delay)
  """
  def decorator(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
      last_exception = None
      
      for attempt in range(1, max_attempts + 1):
        try:
          return await func(*args, **kwargs)
        
        except exclude_exceptions as e:
          # Don't retry these
          logger.debug(
            f"{func.__name__}: Non-retryable "
            f"error: {type(e).__name__}"
          )
          raise
        
        except exceptions as e:
          last_exception = e
          
          if attempt == max_attempts:
            logger.error(
              f"{func.__name__}: All "
              f"{max_attempts} attempts failed. "
              f"Last error: {e}"
            )
            raise
          
          # Calculate delay
          if exponential:
            delay = base_delay ** attempt
          else:
            delay = base_delay
          
          logger.warning(
            f"{func.__name__}: Attempt "
            f"{attempt}/{max_attempts} failed "
            f"({type(e).__name__}). "
            f"Retrying in {delay:.1f}s..."
          )
          
          if on_retry:
            if asyncio.iscoroutinefunction(on_retry):
              await on_retry(attempt, e, delay)
            else:
              on_retry(attempt, e, delay)
          
          await asyncio.sleep(delay)
    
    return wrapper
  return decorator

async def with_timeout(
  coro,
  timeout_seconds: float,
  fallback=None,
  operation_name: str = "operation"
):
  """
  Wraps a coroutine with a timeout.
  Returns fallback value if timeout exceeded.
  Never raises TimeoutError - always returns.
  
  Args:
    coro: The async function call to wrap
    timeout_seconds: Max seconds to wait
    fallback: Value to return on timeout
    operation_name: For logging
  """
  try:
    return await asyncio.wait_for(
      coro,
      timeout=timeout_seconds
    )
  except asyncio.TimeoutError:
    logger.warning(
      f"{operation_name} timed out after "
      f"{timeout_seconds}s. Using fallback."
    )
    return fallback
  except Exception as e:
    logger.error(
      f"{operation_name} failed: {e}"
    )
    return fallback

async def retry_with_fallback(
  func: Callable,
  args: tuple = (),
  kwargs: dict = None,
  max_attempts: int = 3,
  base_delay: float = 2.0,
  fallback=None,
  operation_name: str = "operation"
):
  """
  Retries a function and returns fallback if all attempts fail. Never raises.
  
  Use when you MUST have a result, even if it's a fallback value.
  """
  kwargs = kwargs or {}
  
  for attempt in range(1, max_attempts + 1):
    try:
      # If func is async, await it, else call it synchronously
      if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
      else:
        return func(*args, **kwargs)
    except Exception as e:
      logger.warning(
        f"{operation_name}: Attempt "
        f"{attempt}/{max_attempts} failed: "
        f"{type(e).__name__}: {e}"
      )
      
      if attempt < max_attempts:
        delay = base_delay ** attempt
        await asyncio.sleep(delay)
  
  logger.error(
    f"{operation_name}: All {max_attempts} "
    f"attempts failed. Using fallback."
  )
  return fallback

# Try to import OpenAI exceptions
try:
  from openai import (
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    BadRequestError
  )
  OPENAI_RETRY_EXCEPTIONS = (
    RateLimitError,
    APITimeoutError,
    APIConnectionError
  )
  OPENAI_NO_RETRY_EXCEPTIONS = (
    BadRequestError,
  )
except ImportError:
  OPENAI_RETRY_EXCEPTIONS = (Exception,)
  OPENAI_NO_RETRY_EXCEPTIONS = ()
