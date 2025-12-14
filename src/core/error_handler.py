import asyncio
import logging
from typing import Callable, Any, Optional
from datetime import datetime, timedelta

class RetryableError(Exception):
    """Custom exception for retryable errors"""
    pass

class FatalError(Exception):
    """Custom exception for fatal errors"""
    pass

class ErrorHandler:
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.circuit_breaker_state = {}
    
    async def execute_with_retry(
        self, 
        func: Callable, 
        *args, 
        service: str = "unknown",
        **kwargs
    ) -> Any:
        """Execute function with exponential backoff retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Check circuit breaker
                if self._is_circuit_open(service):
                    raise FatalError(f"Circuit breaker open for {service}")
                
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - reset circuit breaker
                self._record_success(service)
                return result
                
            except FatalError as e:
                logging.error(f"Fatal error for {service}: {e}")
                raise
                
            except Exception as e:
                last_exception = e
                self._record_failure(service)
                
                if attempt < self.max_retries:
                    if self._is_retryable_error(e):
                        delay = self.base_delay * (2 ** attempt)
                        jitter = delay * 0.1
                        actual_delay = delay + (jitter * (attempt - 0.5))
                        
                        logging.warning(
                            f"Attempt {attempt + 1}/{self.max_retries + 1} failed for {service}. "
                            f"Retrying in {actual_delay:.2f}s. Error: {e}"
                        )
                        
                        await asyncio.sleep(actual_delay)
                    else:
                        logging.error(f"Non-retryable error for {service}: {e}")
                        break
                else:
                    logging.error(f"All retries exhausted for {service}: {e}")
        
        raise last_exception or Exception("Unknown error occurred")
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable"""
        retryable_messages = [
            "timeout", "connection", "rate limit", "too many requests",
            "server error", "gateway", "service unavailable", "429", "500", "502", "503", "504"
        ]
        
        error_str = str(error).lower()
        
        # Check for retryable messages
        if any(msg in error_str for msg in retryable_messages):
            return True
        
        # Check for specific HTTP status codes
        if hasattr(error, 'status'):
            if error.status in [429, 500, 502, 503, 504]:
                return True
        
        return False
    
    def _is_circuit_open(self, service: str) -> bool:
        """Check if circuit breaker is open for service"""
        if service not in self.circuit_breaker_state:
            return False
        
        state = self.circuit_breaker_state[service]
        if state.get('state') == 'open':
            # Check if we should try again
            if datetime.utcnow() - state['last_failure'] > timedelta(minutes=5):
                state['state'] = 'half-open'
                state['failure_count'] = 0
                return False
            return True
        
        return False
    
    def _record_success(self, service: str):
        """Record successful call for circuit breaker"""
        if service not in self.circuit_breaker_state:
            self.circuit_breaker_state[service] = {
                'state': 'closed',
                'failure_count': 0,
                'last_failure': None
            }
        else:
            self.circuit_breaker_state[service]['state'] = 'closed'
            self.circuit_breaker_state[service]['failure_count'] = 0
    
    def _record_failure(self, service: str):
        """Record failed call for circuit breaker"""
        if service not in self.circuit_breaker_state:
            self.circuit_breaker_state[service] = {
                'state': 'closed',
                'failure_count': 0,
                'last_failure': datetime.utcnow()
            }
        
        state = self.circuit_breaker_state[service]
        state['failure_count'] += 1
        state['last_failure'] = datetime.utcnow()
        
        # Open circuit if too many failures
        if state['failure_count'] >= 5:
            state['state'] = 'open'
            logging.error(f"Circuit breaker opened for {service}")