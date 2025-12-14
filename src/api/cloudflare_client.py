import aiohttp
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import json

class CloudflareClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_radar_attacks_summary(self, time_range: str = "1h") -> Optional[Dict]:
        """Get attack summary from Cloudflare Radar"""
        endpoint = f"{self.base_url}/radar/attacks/layer3/summary"
        params = {
            "dateRange": time_range,
            "format": "JSON"
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('result', {})
                    else:
                        logging.error(f"Cloudflare API error: {data.get('errors', [])}")
                        return None
                else:
                    logging.error(f"Cloudflare API HTTP error: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching Cloudflare data: {e}")
            return None
    
    async def get_radar_attacks_timeseries(self, time_range: str = "1h") -> Optional[Dict]:
        """Get attack timeseries data"""
        endpoint = f"{self.base_url}/radar/attacks/layer3/timeseries"
        params = {
            "dateRange": time_range,
            "aggInterval": "1m",
            "name": "global",
            "format": "JSON"
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('result', {})
                    else:
                        logging.error(f"Cloudflare Timeseries API error: {data.get('errors', [])}")
                        return None
                else:
                    logging.error(f"Cloudflare Timeseries HTTP error: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching Cloudflare timeseries: {e}")
            return None
    
    async def get_attack_annotations(self, limit: int = 50) -> Optional[List[Dict]]:
        """Get recent attack annotations"""
        endpoint = f"{self.base_url}/radar/annotations"
        params = {
            "dataset": "attacks",
            "limit": limit
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('success'):
                        return data.get('result', [])
                    else:
                        logging.error(f"Cloudflare Annotations API error: {data.get('errors', [])}")
                        return None
                else:
                    logging.error(f"Cloudflare Annotations HTTP error: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching annotations: {e}")
            return None
    
    def parse_attack_data(self, raw_data: Dict) -> List[Dict]:
        """Parse Cloudflare attack data into standardized format"""
        attacks = []
        
        # Handle summary data
        if 'summary' in raw_data:
            summary = raw_data['summary']
            
            # Parse attack types
            for attack_type, count in summary.get('attack_types', {}).items():
                attack = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'cloudflare',
                    'attack_type': attack_type,
                    'magnitude': count,
                    'confidence': 0.8,
                    'source_ip': None,  # Add this field
                    'metadata': {
                        'source_ips': [],
                        'target_countries': summary.get('target_countries', {}),
                        'source_countries': summary.get('source_countries', {}),
                        'total_attacks': summary.get('total_attacks', 0)
                    }
                }
                attacks.append(attack)
        
        # Handle timeseries data
        if 'timeseries' in raw_data:
            for timeseries in raw_data['timeseries']:
                if 'attacks' in timeseries:
                    for attack_point in timeseries['attacks']:
                        attack = {
                            'timestamp': attack_point.get('timestamp', datetime.utcnow().isoformat()),
                            'source': 'cloudflare_timeseries',
                            'attack_type': 'various',
                            'magnitude': attack_point.get('value', 0),
                            'source_ip': None,  # Add this field
                            'confidence': 0.7,
                            'metadata': {
                                'timeline_point': True,
                                'timeline_data': attack_point
                            }
                        }
                        attacks.append(attack)
        
        return attacks
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()