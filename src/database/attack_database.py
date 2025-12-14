# src/database/attack_database.py
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import logging
from contextlib import contextmanager
from pathlib import Path

class AttackDatabase:
    def __init__(self, db_path: str = "data/attacks.db"):
        # Convert to absolute path and ensure it's a proper file path
        self.db_path = str(Path(db_path).absolute())
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        # Create parent directories if they don't exist
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create attacks table with new schema
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    collection_timestamp DATETIME,
                    source TEXT,
                    attack_type TEXT,
                    magnitude REAL,
                    confidence REAL,
                    
                    -- Attacker information
                    source_ip TEXT,
                    source_country TEXT,
                    source_country_name TEXT,
                    source_region TEXT,
                    source_city TEXT,
                    source_coordinates TEXT,
                    source_isp TEXT,
                    
                    -- Target information
                    target_ip TEXT,
                    target_country TEXT,
                    target_country_name TEXT,
                    target_region TEXT,
                    target_city TEXT,
                    target_coordinates TEXT,
                    
                    attack_id TEXT UNIQUE,
                    metadata TEXT
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON attacks(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_source 
                ON attacks(source)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_attack_type 
                ON attacks(attack_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_source_country 
                ON attacks(source_country)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_target_country 
                ON attacks(target_country)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_attack_id 
                ON attacks(attack_id)
            ''')
            
            conn.commit()
            logging.info(f"Database initialized at: {self.db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def store_attacks(self, attacks: List[Dict]):
        """Store attacks in the database"""
        if not attacks:
            return
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for attack in attacks:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO attacks 
                        (timestamp, collection_timestamp, source, attack_type, magnitude, 
                        confidence, source_ip, source_country, source_country_name, 
                        source_region, source_city, source_coordinates, source_isp,
                        target_ip, target_country, target_country_name, target_region, 
                        target_city, target_coordinates, attack_id, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        attack.get('timestamp'),
                        attack.get('collection_timestamp', datetime.utcnow().isoformat()),
                        attack.get('source'),
                        attack.get('attack_type'),
                        attack.get('magnitude', 0),
                        attack.get('confidence', 0),
                        
                        # Attacker info
                        attack.get('source_ip'),
                        attack.get('source_country'),
                        attack.get('source_country_name'),
                        attack.get('source_region'),
                        attack.get('source_city'),
                        json.dumps(attack.get('source_coordinates')) if attack.get('source_coordinates') else None,
                        attack.get('source_isp'),
                        
                        # Target info
                        attack.get('target_ip'),
                        attack.get('target_country'),
                        attack.get('target_country_name'),
                        attack.get('target_region'),
                        attack.get('target_city'),
                        json.dumps(attack.get('target_coordinates')) if attack.get('target_coordinates') else None,
                        
                        attack.get('attack_id'),
                        json.dumps(attack.get('metadata', {}))
                    ))
                except sqlite3.IntegrityError:
                    logging.warning(f"Duplicate attack ID: {attack.get('attack_id')}")
                except Exception as e:
                    logging.error(f"Error storing attack: {e}")
            
            conn.commit()
            logging.info(f"Stored {len(attacks)} attacks in database")

    def get_global_stats(self) -> Dict:
        """Get global attack statistics with enhanced location data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Total attacks today
            cursor.execute('''
                SELECT COUNT(*) FROM attacks 
                WHERE timestamp > ?
            ''', (datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),))
            total_today = cursor.fetchone()[0]
            
            # Active attacks (last hour)
            cursor.execute('''
                SELECT COUNT(*) FROM attacks 
                WHERE timestamp > ?
            ''', (datetime.utcnow() - timedelta(hours=1),))
            active_attacks = cursor.fetchone()[0]
            
            # Attacks by source country
            cursor.execute('''
                SELECT source_country, COUNT(*) as count 
                FROM attacks 
                WHERE timestamp > ? AND source_country IS NOT NULL
                GROUP BY source_country 
                ORDER BY count DESC
                LIMIT 10
            ''', (datetime.utcnow() - timedelta(days=1),))
            by_source_country = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Attacks by target country
            cursor.execute('''
                SELECT target_country, COUNT(*) as count 
                FROM attacks 
                WHERE timestamp > ? AND target_country IS NOT NULL
                GROUP BY target_country 
                ORDER BY count DESC
                LIMIT 10
            ''', (datetime.utcnow() - timedelta(days=1),))
            by_target_country = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Top source countries with details
            cursor.execute('''
                SELECT source_country, source_country_name, COUNT(*) as count,
                    AVG(confidence) as avg_confidence
                FROM attacks 
                WHERE timestamp > ? AND source_country IS NOT NULL
                GROUP BY source_country, source_country_name
                ORDER BY count DESC
                LIMIT 5
            ''', (datetime.utcnow() - timedelta(days=1),))
            top_source_countries = [
                {
                    'country': row[0],
                    'country_name': row[1],
                    'attack_count': row[2],
                    'avg_confidence': round(row[3] or 0, 3)
                }
                for row in cursor.fetchall()
            ]
            
            # Top target countries with details
            cursor.execute('''
                SELECT target_country, target_country_name, COUNT(*) as count
                FROM attacks 
                WHERE timestamp > ? AND target_country IS NOT NULL
                GROUP BY target_country, target_country_name
                ORDER BY count DESC
                LIMIT 5
            ''', (datetime.utcnow() - timedelta(days=1),))
            top_target_countries = [
                {
                    'country': row[0],
                    'country_name': row[1],
                    'attack_count': row[2]
                }
                for row in cursor.fetchall()
            ]
            
            # Attacks by type
            cursor.execute('''
                SELECT attack_type, COUNT(*) as count 
                FROM attacks 
                WHERE timestamp > ?
                GROUP BY attack_type 
                ORDER BY count DESC
            ''', (datetime.utcnow() - timedelta(days=1),))
            by_type = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Average confidence
            cursor.execute('''
                SELECT AVG(confidence) FROM attacks 
                WHERE timestamp > ?
            ''', (datetime.utcnow() - timedelta(days=1),))
            avg_confidence = cursor.fetchone()[0] or 0
            
            return {
                'total_today': total_today,
                'active_attacks': active_attacks,
                'attacks_by_source_country': by_source_country,
                'attacks_by_target_country': by_target_country,
                'top_source_countries': top_source_countries,
                'top_target_countries': top_target_countries,
                'by_type': by_type,
                'avg_confidence': round(avg_confidence, 3),
                'timestamp': datetime.utcnow().isoformat()
            }
        
    def get_recent_attacks(self, limit: int = 100, hours: int = 24) -> List[Dict]:
        """Get recent attacks from the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM attacks 
                WHERE timestamp > ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (datetime.utcnow() - timedelta(hours=hours), limit))
            
            attacks = []
            for row in cursor.fetchall():
                attack = dict(row)
                # Parse JSON fields
                if attack['coordinates']:
                    attack['coordinates'] = json.loads(attack['coordinates'])
                if attack['metadata']:
                    attack['metadata'] = json.loads(attack['metadata'])
                attacks.append(attack)
            
            return attacks
    
   
    
    def get_attacks_by_country(self, country_code: str, hours: int = 24) -> List[Dict]:
        """Get attacks from specific country"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM attacks 
                WHERE country = ? AND timestamp > ?
                ORDER BY timestamp DESC
            ''', (country_code, datetime.utcnow() - timedelta(hours=hours)))
            
            attacks = []
            for row in cursor.fetchall():
                attack = dict(row)
                if attack['coordinates']:
                    attack['coordinates'] = json.loads(attack['coordinates'])
                if attack['metadata']:
                    attack['metadata'] = json.loads(attack['metadata'])
                attacks.append(attack)
            
            return attacks
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old attack data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            cursor.execute('DELETE FROM attacks WHERE timestamp < ?', (cutoff_date,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            logging.info(f"Cleaned up {deleted_count} old attack records")
            return deleted_count
