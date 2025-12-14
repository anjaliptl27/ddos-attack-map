import aiohttp
import asyncio
import logging
from typing import Dict, Optional, List
import sqlite3
import os
from datetime import datetime, timedelta

class GeoIPService:
    def __init__(self, cache_db_path: str = "geoip_cache.db"):
        self.cache_db_path = cache_db_path
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize SQLite cache database"""
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ip_geo_cache (
                ip_address TEXT PRIMARY KEY,
                country_code TEXT,
                country_name TEXT,
                region TEXT,
                city TEXT,
                latitude REAL,
                longitude REAL,
                isp TEXT,
                last_updated DATETIME
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ip_address 
            ON ip_geo_cache(ip_address)
        ''')
        
        conn.commit()
        conn.close()
    
    async def get_ip_geolocation(self, ip_address: str) -> Optional[Dict]:
        """Get geolocation for IP address with caching"""
        # First check cache
        cached_data = self._get_cached_geo(ip_address)
        if cached_data:
            return cached_data
        
        # Try multiple free geolocation services
        services = [
            self._query_ipapi,
            self._query_ipwhois,
            self._query_freeipapi
        ]
        
        for service in services:
            try:
                geo_data = await service(ip_address)
                if geo_data and geo_data.get('country_code'):
                    self._cache_geo_data(ip_address, geo_data)
                    return geo_data
            except Exception as e:
                logging.debug(f"GeoIP service {service.__name__} failed: {e}")
                continue
        
        logging.warning(f"All GeoIP services failed for IP: {ip_address}")
        return None
    
    async def _query_ipapi(self, ip_address: str) -> Optional[Dict]:
        """Query ipapi.co"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ipapi.co/{ip_address}/json/",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'ip': ip_address,
                        'country_code': data.get('country_code'),
                        'country_name': data.get('country_name'),
                        'region': data.get('region'),
                        'city': data.get('city'),
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude'),
                        'isp': data.get('org'),
                        'source': 'ipapi'
                    }
                return None
    
    async def _query_ipwhois(self, ip_address: str) -> Optional[Dict]:
        """Query ipwhois.io"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://ipwhois.app/json/{ip_address}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'ip': ip_address,
                        'country_code': data.get('country_code'),
                        'country_name': data.get('country'),
                        'region': data.get('region'),
                        'city': data.get('city'),
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude'),
                        'isp': data.get('isp'),
                        'source': 'ipwhois'
                    }
                return None
    
    async def _query_freeipapi(self, ip_address: str) -> Optional[Dict]:
        """Query freeipapi.com"""
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://freeipapi.com/api/json/{ip_address}",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'ip': ip_address,
                        'country_code': data.get('countryCode'),
                        'country_name': data.get('countryName'),
                        'region': data.get('regionName'),
                        'city': data.get('cityName'),
                        'latitude': data.get('latitude'),
                        'longitude': data.get('longitude'),
                        'isp': data.get('isp'),
                        'source': 'freeipapi'
                    }
                return None
    
    def _get_cached_geo(self, ip_address: str) -> Optional[Dict]:
        """Get cached geolocation data"""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT country_code, country_name, region, city, 
                       latitude, longitude, isp, last_updated 
                FROM ip_geo_cache 
                WHERE ip_address = ? AND last_updated > ?
            ''', (ip_address, datetime.utcnow() - timedelta(days=30)))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'ip': ip_address,
                    'country_code': row[0],
                    'country_name': row[1],
                    'region': row[2],
                    'city': row[3],
                    'latitude': row[4],
                    'longitude': row[5],
                    'isp': row[6],
                    'source': 'cache'
                }
        except Exception as e:
            logging.error(f"Error reading from geo cache: {e}")
        
        return None
    
    def _cache_geo_data(self, ip_address: str, geo_data: Dict):
        """Cache geolocation data"""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO ip_geo_cache 
                (ip_address, country_code, country_name, region, city, 
                 latitude, longitude, isp, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ip_address,
                geo_data.get('country_code'),
                geo_data.get('country_name'),
                geo_data.get('region'),
                geo_data.get('city'),
                geo_data.get('latitude'),
                geo_data.get('longitude'),
                geo_data.get('isp'),
                datetime.utcnow()
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error(f"Error caching geo data: {e}")
    
    async def batch_geolocate(self, ip_addresses: List[str]) -> Dict[str, Dict]:
        """Batch geolocate multiple IP addresses efficiently"""
        results = {}
        
        # Check cache first
        for ip in ip_addresses:
            cached = self._get_cached_geo(ip)
            if cached:
                results[ip] = cached
        
        # Find IPs that need fresh lookup
        remaining_ips = [ip for ip in ip_addresses if ip not in results]
        
        if remaining_ips:
            logging.info(f"Performing fresh GeoIP lookup for {len(remaining_ips)} IPs")
            
            # Process in batches to avoid overwhelming APIs
            batch_size = 10
            for i in range(0, len(remaining_ips), batch_size):
                batch = remaining_ips[i:i + batch_size]
                
                tasks = [self.get_ip_geolocation(ip) for ip in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for ip, result in zip(batch, batch_results):
                    if isinstance(result, dict):
                        results[ip] = result
                    else:
                        logging.warning(f"Failed to geolocate {ip}: {result}")
                        # Add fallback data
                        results[ip] = self._get_fallback_geo(ip)
                
                # Be respectful to free APIs
                await asyncio.sleep(1)
        
        return results
    
    def _get_fallback_geo(self, ip_address: str) -> Dict:
        """Get fallback geo data when all services fail"""
        import random
        return {
            'ip': ip_address,
            'country_code': 'UN',
            'country_name': 'Unknown',
            'region': 'Unknown',
            'city': 'Unknown',
            'latitude': random.uniform(-90, 90),
            'longitude': random.uniform(-180, 180),
            'isp': 'Unknown',
            'source': 'fallback'
        }