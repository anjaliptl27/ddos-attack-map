import aiohttp
import asyncio
from datetime import datetime
import logging
from typing import Dict, List, Optional
import json

class AbuseIPDBClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.abuseipdb.com/api/v2"
        self.headers = {
            "Key": api_key,
            "Accept": "application/json"
        }
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_blacklist(self, limit: int = 100, confidence_minimum: int = 90) -> Optional[List[Dict]]:
        """Get blacklisted IPs with high confidence of abuse"""
        endpoint = f"{self.base_url}/blacklist"
        params = {
            "limit": limit,
            "confidenceMinimum": confidence_minimum
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    error_text = await response.text()
                    logging.error(f"AbuseIPDB Blacklist API error: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching AbuseIPDB blacklist: {e}")
            return None
    
    async def check_ip(self, ip_address: str, max_age_in_days: int = 30) -> Optional[Dict]:
        """Check specific IP address for abuse reports"""
        endpoint = f"{self.base_url}/check"
        params = {
            "ipAddress": ip_address,
            "maxAgeInDays": max_age_in_days,
            "verbose": True
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', {})
                else:
                    logging.error(f"AbuseIPDB Check API error: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Error checking IP {ip_address}: {e}")
            return None
    
    async def get_reports(self, page: int = 1, per_page: int = 100) -> Optional[List[Dict]]:
        """Get recent abuse reports"""
        endpoint = f"{self.base_url}/reports"
        params = {
            "page": page,
            "perPage": per_page
        }
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(endpoint, headers=self.headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('data', [])
                else:
                    logging.error(f"AbuseIPDB Reports API error: {response.status}")
                    return None
        except Exception as e:
            logging.error(f"Error fetching AbuseIPDB reports: {e}")
            return None
    
    def parse_blacklist_data(self, blacklist_data: List[Dict]) -> List[Dict]:
        """Parse AbuseIPDB blacklist into attack format"""
        attacks = []
        
        for ip_data in blacklist_data:
            # Only consider IPs with high abuse confidence
            if ip_data.get('abuseConfidenceScore', 0) >= 80:
                attack = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'abuseipdb',
                    'source_ip': ip_data.get('ipAddress'),
                    'abuse_confidence': ip_data.get('abuseConfidenceScore', 0),
                    'country_code': ip_data.get('countryCode'),
                    'isp': ip_data.get('isp'),
                    'domain': ip_data.get('domain'),
                    'total_reports': ip_data.get('totalReports', 0),
                    'last_reported_at': ip_data.get('lastReportedAt'),
                    'attack_type': self._classify_attack_type(ip_data),
                    'magnitude': self._calculate_magnitude(ip_data),
                    'confidence': ip_data.get('abuseConfidenceScore', 0) / 100.0,
                    'metadata': {
                        'categories': ip_data.get('categories', []),
                        'is_whitelisted': ip_data.get('isWhitelisted', False)
                    }
                }
                attacks.append(attack)
        
        return attacks
    
    def _classify_attack_type(self, ip_data: Dict) -> str:
        """Classify attack type based on reported categories"""
        categories = ip_data.get('categories', [])
        
        # AbuseIPDB category mapping
        category_map = {
            '3': 'DDoS Attack',
            '4': 'FTP Brute-force',
            '5': 'SSH Brute-force', 
            '6': 'Web Attack',
            '9': 'Port Scan',
            '10': 'Web App Attack',
            '11': 'SSH Attack',
            '14': 'Port Scan',
            '18': 'Brute Force',
            '19': 'DDoS Attack',
            '21': 'Web Attack'
        }
        
        # Prioritize DDoS categories
        for category_id in categories:
            category_str = str(category_id)
            if category_str in ['3', '19']:  # DDoS categories
                return category_map.get(category_str, 'DDoS Attack')
        
        # Return first matching category
        for category_id in categories:
            category_str = str(category_id)
            if category_str in category_map:
                return category_map[category_str]
        
        return 'Suspicious Activity'
    
    def _calculate_magnitude(self, ip_data: Dict) -> float:
        """Calculate attack magnitude based on reports and confidence"""
        base_score = ip_data.get('abuseConfidenceScore', 0)
        reports_multiplier = min(ip_data.get('totalReports', 0) / 10.0, 5.0)
        return (base_score / 100.0) * reports_multiplier
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()