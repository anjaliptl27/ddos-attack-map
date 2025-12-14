# enhanced_data_collector.py
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from rate_limiter import RateLimiter
from error_handler import ErrorHandler, RetryableError, FatalError
from geoip_service import GeoIPService

class EnhancedDDoSDataCollector:
    def __init__(self, cloudflare_token: str, abuseipdb_key: str):
        self.cf_client = CloudflareClient(cloudflare_token)
        self.abuse_client = AbuseIPDBClient(abuseipdb_key)
        self.rate_limiter = RateLimiter()
        self.error_handler = ErrorHandler(max_retries=3, base_delay=1.0)
        self.geoip_service = GeoIPService()
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'last_successful_fetch': None
        }
    
    async def collect_cloudflare_attacks(self) -> List[Dict]:
        """Collect attack data from Cloudflare with enhanced error handling"""
        await self.rate_limiter.wait_if_needed('cloudflare')
        
        try:
            attacks = await self.error_handler.execute_with_retry(
                self._fetch_cloudflare_data,
                service='cloudflare'
            )
            
            self.stats['successful_requests'] += 1
            self.stats['last_successful_fetch'] = datetime.utcnow()
            logging.info(f"Successfully collected {len(attacks)} attacks from Cloudflare")
            return attacks
            
        except Exception as e:
            self.stats['failed_requests'] += 1
            logging.error(f"Failed to collect Cloudflare data: {e}")
            return []
    
    async def _fetch_cloudflare_data(self) -> List[Dict]:
        """Actual Cloudflare data fetching logic"""
        attacks = []
        
        # Get summary data
        summary_data = await self.cf_client.get_radar_attacks_summary("1h")
        if summary_data:
            summary_attacks = self.cf_client.parse_attack_data(summary_data)
            attacks.extend(summary_attacks)
        
        # Get timeseries data
        timeseries_data = await self.cf_client.get_radar_attacks_timeseries("1h")
        if timeseries_data:
            timeseries_attacks = self.cf_client.parse_attack_data(timeseries_data)
            attacks.extend(timeseries_attacks)
        
        return attacks
    
    async def collect_abuseipdb_attacks(self) -> List[Dict]:
        """Collect attack data from AbuseIPDB with enhanced error handling"""
        await self.rate_limiter.wait_if_needed('abuseipdb')
        
        try:
            attacks = await self.error_handler.execute_with_retry(
                self._fetch_abuseipdb_data,
                service='abuseipdb'
            )
            
            self.stats['successful_requests'] += 1
            logging.info(f"Successfully collected {len(attacks)} attacks from AbuseIPDB")
            return attacks
            
        except Exception as e:
            self.stats['failed_requests'] += 1
            logging.error(f"Failed to collect AbuseIPDB data: {e}")
            return []
    
    async def _fetch_abuseipdb_data(self) -> List[Dict]:
        """Actual AbuseIPDB data fetching logic"""
        blacklist = await self.abuse_client.get_blacklist(limit=100, confidence_minimum=80)
        if blacklist:
            return self.abuse_client.parse_blacklist_data(blacklist)
        return []
    
    async def collect_all_data(self) -> List[Dict]:
        """Collect and enrich data from all sources"""
        self.stats['total_requests'] += 1
        
        # Collect from both sources concurrently
        cloudflare_task = asyncio.create_task(self.collect_cloudflare_attacks())
        abuseipdb_task = asyncio.create_task(self.collect_abuseipdb_attacks())
        
        cloudflare_attacks, abuseipdb_attacks = await asyncio.gather(
            cloudflare_task, abuseipdb_task, return_exceptions=True
        )
        
        # Combine results
        all_attacks = []
        
        if not isinstance(cloudflare_attacks, Exception):
            all_attacks.extend(cloudflare_attacks)
        
        if not isinstance(abuseipdb_attacks, Exception):
            all_attacks.extend(abuseipdb_attacks)
        
        # Enrich with GeoIP data
        if all_attacks:
            enriched_attacks = await self.enrich_with_geo_data(all_attacks)
            logging.info(f"Total enriched attacks: {len(enriched_attacks)}")
            return enriched_attacks
        
        return []
    
    async def enrich_with_geo_data(self, attacks: List[Dict]) -> List[Dict]:
        """Enrich attacks with real GeoIP data"""
        # Extract unique IPs for batch geolocation
        source_ips = []
        for attack in attacks:
            # Handle both 'source_ip' and 'ipAddress' field names
            source_ip = attack.get('source_ip') or attack.get('ipAddress')
            if source_ip:
                source_ips.append(source_ip)
        
        if not source_ips:
            logging.warning("No source IPs found to geolocate")
            return self._add_fallback_geo_to_attacks(attacks)
        
        # Batch geolocate all IPs
        geo_data = await self.geoip_service.batch_geolocate(list(set(source_ips)))
        
        # Enrich attacks with geo data
        for attack in attacks:
            # Handle both 'source_ip' and 'ipAddress' field names
            source_ip = attack.get('source_ip') or attack.get('ipAddress')
            
            try:
                if source_ip and source_ip in geo_data:
                    geo_info = geo_data[source_ip]
                    attack['coordinates'] = {
                        'lat': geo_info.get('latitude'),
                        'lng': geo_info.get('longitude')
                    }
                    attack['country'] = geo_info.get('country_code')
                    attack['country_name'] = geo_info.get('country_name')
                    attack['region'] = geo_info.get('region')
                    attack['city'] = geo_info.get('city')
                    attack['isp'] = geo_info.get('isp')
                    attack['geo_source'] = geo_info.get('source', 'unknown')
                else:
                    # Fallback to mock data if geolocation fails
                    self._add_fallback_geo_to_attack(attack)
            except Exception as e:
                logging.warning(f"Error enriching attack data: {e}")
                # Ensure coordinates are always present
                self._add_fallback_geo_to_attack(attack)
            
            # Add metadata
            attack['collection_timestamp'] = datetime.utcnow().isoformat()
            attack['attack_id'] = self._generate_attack_id(attack)
        
        return attacks

    def _add_fallback_geo_to_attack(self, attack: Dict) -> None:
        """Add fallback geo data to a single attack"""
        attack['coordinates'] = self._get_fallback_coordinates()
        attack['country'] = 'Unknown'
        attack['country_name'] = 'Unknown'
        attack['region'] = 'Unknown'
        attack['city'] = 'Unknown'
        attack['isp'] = 'Unknown'
        attack['geo_source'] = 'fallback'

    def _add_fallback_geo_to_attacks(self, attacks: List[Dict]) -> List[Dict]:
        """Add fallback geo data to all attacks"""
        for attack in attacks:
            self._add_fallback_geo_to_attack(attack)
            attack['collection_timestamp'] = datetime.utcnow().isoformat()
            attack['attack_id'] = self._generate_attack_id(attack)
        return attacks

    def _get_fallback_coordinates(self) -> Dict[str, float]:
        """Get fallback coordinates when GeoIP fails"""
        import random
        # Ensure coordinates are always valid
        return {
            'lat': float(random.uniform(-90, 90)),
            'lng': float(random.uniform(-180, 180))
        }
    
    def _generate_attack_id(self, attack: Dict) -> str:
        """Generate unique ID for each attack"""
        source = attack.get('source', 'unknown')
        timestamp = attack.get('timestamp', '')
        identifier = attack.get('source_ip', attack.get('attack_type', ''))
        return f"{source}_{identifier}_{hash(timestamp) % 10000:04d}"
    
    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['successful_requests'] / self.stats['total_requests'] * 100
                if self.stats['total_requests'] > 0 else 0
            ),
            'remaining_cloudflare_calls': self.rate_limiter.get_remaining_calls('cloudflare'),
            'remaining_abuseipdb_calls': self.rate_limiter.get_remaining_calls('abuseipdb')
        }