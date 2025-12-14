# rate_limiter.py
import asyncio
import time
from typing import Dict, Optional
from collections import defaultdict
import logging

class RateLimiter:
    def __init__(self):
        self.rate_limits = {
            'cloudflare': {
                'calls': 0,
                'max_calls': 1000,  # Cloudflare's typical limit
                'timeframe': 300,   # 5 minutes
                'last_reset': time.time()
            },
            'abuseipdb': {
                'calls': 0,
                'max_calls': 1000,  # AbuseIPDB free tier limit
                'timeframe': 86400, # 24 hours
                'last_reset': time.time()
            }
        }
        
    async def wait_if_needed(self, service: str) -> None:
        """Wait if rate limit is approaching"""
        limit_info = self.rate_limits[service]
        
        # Reset counter if timeframe has passed
        if time.time() - limit_info['last_reset'] > limit_info['timeframe']:
            limit_info['calls'] = 0
            limit_info['last_reset'] = time.time()
        
        # Check if we're approaching limit
        remaining_calls = limit_info['max_calls'] - limit_info['calls']
        
        if remaining_calls <= 10:  # Low threshold
            wait_time = limit_info['timeframe'] - (time.time() - limit_info['last_reset'])
            if wait_time > 0:
                logging.warning(f"Rate limit low for {service}. Waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                limit_info['calls'] = 0
                limit_info['last_reset'] = time.time()
        
        # Increment call counter
        limit_info['calls'] += 1
        
        # Add slight delay between calls to be respectful
        await asyncio.sleep(0.1)
    
    def get_remaining_calls(self, service: str) -> int:
        """Get remaining API calls for service"""
        limit_info = self.rate_limits[service]
        remaining = limit_info['max_calls'] - limit_info['calls']
        return max(0, remaining)