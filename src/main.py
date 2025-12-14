import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from src.api.cloudflare_public import CloudflarePublicClient

# Add the src directory to Python path
sys.path.append(str(Path(__file__).parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from src.core.config import settings
from src.api.cloudflare_client import CloudflareClient
from src.api.abuseipdb_client import AbuseIPDBClient
from src.core.geoip_service import GeoIPService
from src.core.error_handler import ErrorHandler
from src.database.attack_database import AttackDatabase
from src.ml.ddos_classifier import DDOSClassifier
from src.ml.feature_extractor import FeatureExtractor
from src.models.attack_models import AttackResponse, AttackStats, HealthStatus, StatsResponse, APIResponse


# Configure logging for Windows compatibility
class WindowsSafeFormatter(logging.Formatter):
    """Custom formatter that handles emojis on Windows"""
    def format(self, record):
        # Replace emojis with text on Windows to avoid encoding issues
        if os.name == 'nt':
            emoji_map = {
                '🚀': '[LAUNCH]',
                '✅': '[OK]',
                '❌': '[ERROR]',
                '🎯': '[TARGET]',
                '📡': '[RADAR]',
                '🛑': '[STOP]',
                '🌐': '[GLOBE]',
                '⚠️': '[WARN]',
                '🔧': '[CONFIG]'
            }
            for emoji, text in emoji_map.items():
                record.msg = record.msg.replace(emoji, text)
        return super().format(record)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.logs_dir / 'ddos_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Apply Windows-safe formatter to console handler
for handler in logging.getLogger().handlers:
    if isinstance(handler, logging.StreamHandler):
        handler.setFormatter(WindowsSafeFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))

logger = logging.getLogger(__name__)

# Global components
clients = {}
db = None
classifier = None
feature_extractor = None
error_handler = None

abuseipdb_request_count = 0

class EnhancedConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.connection_stats = {
            'total_connections': 0,
            'current_connections': 0,
            'messages_sent': 0
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_stats['total_connections'] += 1
        self.connection_stats['current_connections'] += 1
        logger.info(f"WebSocket connected. Total: {self.connection_stats['current_connections']}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.connection_stats['current_connections'] -= 1
            logger.info(f"WebSocket disconnected. Remaining: {self.connection_stats['current_connections']}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
            self.connection_stats['messages_sent'] += 1
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
                self.connection_stats['messages_sent'] += 1
            except Exception as e:
                logger.error(f"Error broadcasting to WebSocket: {e}")
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect(connection)

    def get_stats(self) -> dict:
        return self.connection_stats.copy()

manager = EnhancedConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global clients, db, classifier, feature_extractor, error_handler
    
    logger.info("Initializing DDoS Attack Monitor...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"Log level: {settings.log_level}")

    try:
        # Initialize components
        error_handler = ErrorHandler(
            max_retries=settings.max_retries,
            base_delay=settings.base_retry_delay
        )
        
        #clients['cloudflare'] = CloudflareClient(settings.cloudflare_api_token)
       
        clients['cloudflare_public'] = CloudflarePublicClient()
        clients['abuseipdb'] = AbuseIPDBClient(settings.abuseipdb_api_key)
        clients['geoip'] = GeoIPService(settings.get_geoip_db_path())
        
        db = AttackDatabase(settings.get_database_path())
        classifier = DDOSClassifier(settings.get_ml_model_path())
        feature_extractor = FeatureExtractor()

        # Test database connection
        await asyncio.get_event_loop().run_in_executor(None, db._init_database)
        
        logger.info("All components initialized successfully")
        
        # Start background tasks
        asyncio.create_task(continuous_data_collection())
        asyncio.create_task(health_monitor())
        
        logger.info("Background tasks started")
        logger.info("DDoS Attack Monitor is ready!")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

    yield  # Application runs here

    # Shutdown
    logger.info("Shutting down DDoS Attack Monitor...")
    
    # Close API client sessions
    for name, client in clients.items():
        if hasattr(client, 'close'):
            await client.close()
            logger.info(f"Closed {name} client")
    
    logger.info("DDoS Attack Monitor shutdown complete")

app = FastAPI(
    title="Live DDoS Attack Map",
    description="Real-time DDoS attack monitoring and visualization system",
    version="2.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
def read_home():
    return FileResponse(settings.base_dir / "src" / "static" / "home.html")

@app.get("/instructions")
def read_instructions():
    return FileResponse(settings.base_dir / "src" / "static" / "instructions.html")

'''@app.get("/analytics")
def read_analytics():
    return FileResponse(settings.base_dir / "src" / "static" / "analytics.html")
    '''

@app.get("/about")
def read_about():
    return FileResponse(settings.base_dir / "src" / "static" / "about.html")

@app.get("/globe", response_class=HTMLResponse)
async def get_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GitHub-style DDoS Attack Globe</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                margin: 0; 
                padding: 0; 
                background: #0d1117;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                overflow: hidden;
                color: #f0f6fc;
            }
            #globeContainer { 
                width: 100vw; 
                height: 100vh; 
                position: relative;
            }
            .github-controls {
                position: absolute;
                top: 30px;
                right: 30px;
                background: rgba(13, 17, 23, 0.9);
                padding: 15px;
                border-radius: 12px;
                border: 1px solid #30363d;
                backdrop-filter: blur(10px);
                z-index: 1000;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
            }
            .github-btn {
                background: #238636;
                color: white;
                border: none;
                padding: 8px 16px;
                margin: 4px;
                border-radius: 6px;
                font-family: inherit;
                font-size: 14px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .github-btn:hover {
                background: #2ea043;
            }
            .github-btn.secondary {
                background: #21262d;
                border: 1px solid #30363d;
            }
            .github-btn.secondary:hover {
                background: #30363d;
            }
        </style>
    </head>
    <body>
        <div id="globeContainer"></div>
        
       <div class="github-controls">
    <button class="github-btn" onclick="toggleRotation()">🔄 Rotation</button>
    <button class="github-btn secondary" onclick="adjustIntensity(0.1)">✨ Brighter</button>
    <button class="github-btn secondary" onclick="adjustIntensity(-0.1)">🌙 Darker</button>
    <button class="github-btn secondary" onclick="toggleLabels()">🏷️ Labels</button>
    <button class="github-btn" onclick="clearAttacks()">🗑️ Clear</button>
</div>
        
        <!-- Load Three.js and OrbitControls from CDN -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
        <script src="/static/globe.js"></script>
    </body>
    </html>
    """
    

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time attack data"""
    await manager.connect(websocket)
    try:
        # Send initial stats
        initial_data = {
            'type': 'initial',
            'stats': db.get_global_stats() if db else {},
            'connections': manager.get_stats()
        }
        await manager.send_personal_message(initial_data, websocket)
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Handle client messages if needed
            if data == 'ping':
                await manager.send_personal_message({'type': 'pong'}, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

# API Routes
@app.get("/api/health", response_model=HealthStatus)
async def health_check():
    """Comprehensive health check endpoint"""
    services_status = {
        'cloudflare': 'unknown',
        'abuseipdb': 'unknown',
        'database': 'unknown',
        'geoip': 'unknown',
        'ml_model': 'unknown',
        'websocket': 'healthy'
    }
    
    # Check Cloudflare
    try:
        if clients.get('cloudflare'):
            test_data = await clients['cloudflare'].get_radar_attacks_summary("1h")
            services_status['cloudflare'] = 'healthy' if test_data else 'degraded'
    except Exception:
        services_status['cloudflare'] = 'unhealthy'
    
    # Check AbuseIPDB
    try:
        if clients.get('abuseipdb'):
            test_data = await clients['abuseipdb'].get_blacklist(limit=1)
            services_status['abuseipdb'] = 'healthy' if test_data else 'degraded'
    except Exception:
        services_status['abuseipdb'] = 'unhealthy'
    
    # Check Database
    try:
        if db:
            test_data = db.get_recent_attacks(limit=1)
            services_status['database'] = 'healthy'
    except Exception:
        services_status['database'] = 'unhealthy'
    
    # Check GeoIP
    try:
        if clients.get('geoip'):
            test_data = await clients['geoip'].get_ip_geolocation("8.8.8.8")
            services_status['geoip'] = 'healthy' if test_data else 'degraded'
    except Exception:
        services_status['geoip'] = 'unhealthy'
    
    # Check ML Model
    try:
        if classifier and classifier.model is not None:
            services_status['ml_model'] = 'healthy'
        else:
            services_status['ml_model'] = 'unhealthy'
    except Exception:
        services_status['ml_model'] = 'unhealthy'
    
    # Overall status
    unhealthy_services = [svc for svc, status in services_status.items() if status == 'unhealthy']
    overall_status = 'degraded' if unhealthy_services else 'healthy'
    
    return HealthStatus(
        status=overall_status,
        timestamp=asyncio.get_event_loop().time(),
        services=services_status,
        stats=manager.get_stats()
    )

@app.get("/api/attacks", response_model=list[AttackResponse])
async def get_recent_attacks(limit: int = 100, hours: int = 24):
    """Get recent attacks with optional filtering"""
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 1000")
    if hours > 720:  # 30 days
        raise HTTPException(status_code=400, detail="Time range cannot exceed 30 days")
    
    try:
        attacks = db.get_recent_attacks(limit=limit, hours=hours) if db else []
        return attacks
    except Exception as e:
        logger.error(f"Error fetching attacks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

from src.models.attack_models import StatsResponse  # Use the flexible model

@app.get("/api/stats")  # Remove response_model temporarily
async def get_attack_stats():
    """Get global attack statistics"""
    try:
        stats = db.get_global_stats() if db else {}
        
        # Convert to flexible response
        response = StatsResponse(**stats)
        
        # Ensure all required fields have values
        if response.total_attacks is None:
            response.total_attacks = stats.get('total_today', 0)
        if response.attacks_today is None:
            response.attacks_today = stats.get('total_today', 0)
        if response.average_confidence is None:
            response.average_confidence = stats.get('avg_confidence', 0.0)
        if response.attacks_by_country is None:
            response.attacks_by_country = stats.get('by_country', {})
        if response.attacks_by_type is None:
            response.attacks_by_type = stats.get('by_type', {})
        if response.top_source_ips is None:
            response.top_source_ips = []
            
        return response.dict()
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        # Return basic stats to avoid frontend errors
        return {
            "total_attacks": 0,
            "attacks_today": 0,
            "attacks_by_country": {},
            "attacks_by_type": {},
            "top_source_ips": [],
            "average_confidence": 0.0
        }

@app.get("/api/attacks/country/{country_code}")
async def get_attacks_by_country(country_code: str, hours: int = 24):
    """Get attacks from specific country"""
    if hours > 168:  # 1 week
        raise HTTPException(status_code=400, detail="Time range cannot exceed 1 week")
    
    try:
        attacks = db.get_attacks_by_country(country_code, hours=hours) if db else []
        return {
            'country': country_code,
            'time_range_hours': hours,
            'attack_count': len(attacks),
            'attacks': attacks
        }
    except Exception as e:
        logger.error(f"Error fetching country attacks: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/maintenance/cleanup")
async def cleanup_old_data(days_to_keep: int = 30):
    """Clean up old attack data (admin endpoint)"""
    if days_to_keep < 1:
        raise HTTPException(status_code=400, detail="Days to keep must be at least 1")
    
    try:
        deleted_count = db.cleanup_old_data(days_to_keep) if db else 0
        return {
            'message': f'Cleaned up {deleted_count} old records',
            'days_kept': days_to_keep,
            'records_deleted': deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up data: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Background tasks
async def continuous_data_collection():
    """Background task for continuous data collection"""
    collection_count = 0
    
    while True:
        try:
            logger.debug(f"Starting data collection cycle #{collection_count + 1}")
            
            attacks = await collect_all_data()
            
            if attacks:
                # Store in database
                db.store_attacks(attacks)
                
                # Broadcast to WebSocket clients
                await manager.broadcast({
                    'type': 'new_attacks',
                    'attacks': attacks,
                    'timestamp': datetime.utcnow().isoformat(),
                    'collection_id': collection_count
                })
                
                logger.info(f"Collection #{collection_count + 1}: Broadcast {len(attacks)} new attacks")
            else:
                logger.debug(f"Collection #{collection_count + 1}: No new attacks")
            
            collection_count += 1
            await asyncio.sleep(settings.collection_interval)
            
        except Exception as e:
            logger.error(f"Critical error in data collection cycle #{collection_count}: {e}")
            await asyncio.sleep(60)  # Emergency backoff

async def collect_all_data() -> list:
    """Collect and blend data from all available sources - DDoS ONLY"""
    all_attacks = []
    
    # Collect from all sources
    abuse_attacks = await collect_abuseipdb_data()
    cf_attacks = await collect_cloudflare_data()
    
    # Combine all attacks
    all_raw_attacks = abuse_attacks + cf_attacks
    
    # Filter only DDoS attacks
    ddos_attacks = [
        attack for attack in all_raw_attacks 
        if 'ddos' in attack.get('attack_type', '').lower()
    ]
    
    if ddos_attacks:
        all_attacks.extend(ddos_attacks)
        logging.info(f"🎯 Filtered {len(ddos_attacks)} DDoS attacks")
    
    # If no DDoS attacks found, generate synthetic DDoS attacks
    if len(all_attacks) < 2:
        supplemental = await generate_ddos_attacks(3 - len(all_attacks))
        all_attacks.extend(supplemental)
        logging.info(f"➕ Added {len(supplemental)} synthetic DDoS attacks")
    
    # Enrich all data
    if all_attacks:
        enriched_attacks = await enrich_attacks(all_attacks)
        logging.info(f"🚀 Total DDoS attacks ready: {len(enriched_attacks)}")
        return enriched_attacks
    
    return []

async def generate_ddos_attacks(count: int = 3) -> list:
    """Generate synthetic DDoS attack data"""
    import random
    from datetime import datetime
    
    attacks = []
    source_countries = [
        {'country': 'CN', 'country_name': 'China', 'city': 'Beijing', 'lat': 39.9042, 'lng': 116.4074},
        {'country': 'RU', 'country_name': 'Russia', 'city': 'Moscow', 'lat': 55.7558, 'lng': 37.6173},
        {'country': 'US', 'country_name': 'United States', 'city': 'New York', 'lat': 40.7128, 'lng': -74.0060},
        {'country': 'IN', 'country_name': 'India', 'city': 'Mumbai', 'lat': 19.0760, 'lng': 72.8777},
        {'country': 'BR', 'country_name': 'Brazil', 'city': 'São Paulo', 'lat': -23.5505, 'lng': -46.6333}
    ]
    
    target_countries = [
        {'country': 'US', 'country_name': 'United States', 'city': 'New York', 'lat': 40.7128, 'lng': -74.0060},
        {'country': 'DE', 'country_name': 'Germany', 'city': 'Frankfurt', 'lat': 50.1109, 'lng': 8.6821},
        {'country': 'GB', 'country_name': 'United Kingdom', 'city': 'London', 'lat': 51.5074, 'lng': -0.1278},
        {'country': 'JP', 'country_name': 'Japan', 'city': 'Tokyo', 'lat': 35.6762, 'lng': 139.6503},
        {'country': 'SG', 'country_name': 'Singapore', 'city': 'Singapore', 'lat': 1.3521, 'lng': 103.8198}
    ]
    
    for i in range(count):
        source = random.choice(source_countries)
        target = random.choice(target_countries)
        
        attack = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'synthetic_ddos',
            'source_ip': f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
            'attack_type': 'DDoS Attack',
            'magnitude': random.uniform(50, 95),
            'confidence': random.uniform(0.7, 0.95),
            
            # Source location
            'source_country': source['country'],
            'source_country_name': source['country_name'],
            'source_city': source['city'],
            'source_coordinates': {
                'lat': source['lat'] + random.uniform(-2, 2),
                'lng': source['lng'] + random.uniform(-2, 2)
            },
            
            # Target location
            'target_country': target['country'],
            'target_country_name': target['country_name'],
            'target_city': target['city'],
            'target_coordinates': {
                'lat': target['lat'] + random.uniform(-2, 2),
                'lng': target['lng'] + random.uniform(-2, 2)
            },
            
            'metadata': {
                'synthetic': True,
                'ddos_type': random.choice(['Volumetric', 'Application Layer', 'Protocol']),
                'duration_minutes': random.randint(5, 60)
            }
        }
        attacks.append(attack)
    
    logging.info(f"Generated {len(attacks)} synthetic DDoS attacks")
    return attacks

async def collect_cloudflare_data() -> list:
    """Collect data from Cloudflare public sources"""
    try:
        # Fix: Use the correct client name 'cloudflare_public'
        async with clients['cloudflare_public'] as public_client:
            # Get synthetic attack insights
            attacks = await public_client.get_attack_insights()
            if attacks:
                logging.info(f"Generated {len(attacks)} synthetic attacks from Cloudflare insights")
                return attacks
            
            # Fallback: try to get any public data
            public_data = await public_client.get_public_attack_data()
            if public_data and public_data.get('attacks'):
                return public_data['attacks']
                
    except Exception as e:
        logging.error(f"Error collecting Cloudflare public data: {e}")
    
    return []

async def generate_supplemental_data(count: int = 5) -> list:
    """Generate supplemental attack data when APIs return little data"""
    import random
    from datetime import datetime
    
    attacks = []
    attack_types = ['DDoS', 'Port Scan', 'Brute Force', 'Web Attack', 'SSH Attack']
    countries = ['US', 'CN', 'RU', 'DE', 'FR', 'GB', 'JP', 'KR', 'IN', 'BR', 'NL', 'CA']
    
    for i in range(count):
        attack = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'supplemental',
            'source_ip': f"203.0.113.{random.randint(1, 255)}",  # Example IP range
            'attack_type': random.choice(attack_types),
            'magnitude': random.uniform(10, 80),
            'confidence': random.uniform(0.6, 0.9),
            'country': random.choice(countries),
            'coordinates': {
                'lat': random.uniform(-90, 90),
                'lng': random.uniform(-180, 180)
            },
            'metadata': {
                'supplemental': True,
                'reason': 'Low API data'
            }
        }
        attacks.append(attack)
    
    logging.info(f"Generated {len(attacks)} supplemental attacks")
    return attacks

async def collect_abuseipdb_data() -> list:
    """Collect data from AbuseIPDB with rate limit handling"""
    global abuseipdb_request_count
    
    # Check if we've hit daily limits
    if abuseipdb_request_count >= 4:  # Leave 1 request for safety
        logging.warning("AbuseIPDB daily limit reached, using cached data")
        return await get_cached_abuseipdb_data()
    
    try:
        async with clients['abuseipdb'] as abuse_client:
            # Try with lower limit to avoid hitting limits
            blacklist = await abuse_client.get_blacklist(limit=20, confidence_minimum=80)
            abuseipdb_request_count += 1
            
            if blacklist:
                attacks = abuse_client.parse_blacklist_data(blacklist)
                logging.info(f"Collected {len(attacks)} attacks from AbuseIPDB (request #{abuseipdb_request_count})")
                return attacks
                
    except Exception as e:
        if "429" in str(e) or "rate limit" in str(e):
            logging.warning("AbuseIPDB rate limit hit, using fallback data")
            abuseipdb_request_count = 5  # Mark as limited
            return await get_cached_abuseipdb_data()
        else:
            logging.error(f"Error collecting AbuseIPDB data: {e}")
    
    return []

async def get_cached_abuseipdb_data() -> list:
    """Get cached or synthetic data when API limits are hit"""
    # Return recent data from database
    if db:
        recent_attacks = db.get_recent_attacks(limit=10)
        if recent_attacks:
            logging.info(f"Using {len(recent_attacks)} cached attacks")
            return recent_attacks[:5]
    
    # Generate synthetic data as fallback
    return await generate_supplemental_data(3)

async def enrich_attacks(attacks: list) -> list:
    """Enrich attacks with ML classification and GeoIP data for both source and target"""
    enriched_attacks = []
    
    # Extract unique IPs for batch geolocation
    source_ips = []
    target_ips = []
    
    for attack in attacks:
        if attack.get('source_ip'):
            source_ips.append(attack['source_ip'])
        if attack.get('target_ip'):
            target_ips.append(attack['target_ip'])
    
    # Batch geolocate IPs
    all_ips = list(set(source_ips + target_ips))
    geo_data = await clients['geoip'].batch_geolocate(all_ips)
    
    for attack in attacks:
        try:
            # Add ML classification
            if feature_extractor:
                features = feature_extractor.extract_features(attack)
                ml_confidence = classifier.predict(features)
                original_confidence = attack.get('confidence', 0.5)
                attack['confidence'] = (original_confidence + ml_confidence) / 2
                attack['ml_confidence'] = ml_confidence
        except Exception as e:
            logging.warning(f"ML classification failed for attack: {e}")
            attack['confidence'] = attack.get('confidence', 0.5)
        
        # Add source GeoIP data
        source_ip = attack.get('source_ip')
        if source_ip and source_ip in geo_data:
            geo_info = geo_data[source_ip]
            attack.update({
                'source_country': geo_info.get('country_code'),
                'source_country_name': geo_info.get('country_name'),
                'source_region': geo_info.get('region'),
                'source_city': geo_info.get('city'),
                'source_coordinates': {
                    'lat': geo_info.get('latitude'),
                    'lng': geo_info.get('longitude')
                },
                'source_isp': geo_info.get('isp')
            })
        else:
            # Generate fallback source coordinates
            import random
            attack['source_coordinates'] = {
                'lat': random.uniform(-90, 90),
                'lng': random.uniform(-180, 180)
            }
            attack['source_country'] = attack.get('source_country', 'Unknown')
            attack['source_country_name'] = attack.get('source_country_name', 'Unknown Country')
            attack['source_city'] = attack.get('source_city', 'Unknown City')
        
        # Add target GeoIP data
        target_ip = attack.get('target_ip')
        if target_ip and target_ip in geo_data:
            geo_info = geo_data[target_ip]
            attack.update({
                'target_country': geo_info.get('country_code'),
                'target_country_name': geo_info.get('country_name'),
                'target_region': geo_info.get('region'),
                'target_city': geo_info.get('city'),
                'target_coordinates': {
                    'lat': geo_info.get('latitude'),
                    'lng': geo_info.get('longitude')
                }
            })
        else:
            # Generate realistic target locations
            common_targets = [
                {'country': 'US', 'country_name': 'United States', 'city': 'New York', 'lat': 40.7128, 'lng': -74.0060},
                {'country': 'DE', 'country_name': 'Germany', 'city': 'Frankfurt', 'lat': 50.1109, 'lng': 8.6821},
                {'country': 'GB', 'country_name': 'United Kingdom', 'city': 'London', 'lat': 51.5074, 'lng': -0.1278},
                {'country': 'JP', 'country_name': 'Japan', 'city': 'Tokyo', 'lat': 35.6762, 'lng': 139.6503},
                {'country': 'SG', 'country_name': 'Singapore', 'city': 'Singapore', 'lat': 1.3521, 'lng': 103.8198}
            ]
            import random
            target = random.choice(common_targets)
            attack.update({
                'target_country': target['country'],
                'target_country_name': target['country_name'],
                'target_city': target['city'],
                'target_coordinates': {
                    'lat': target['lat'] + random.uniform(-2, 2),
                    'lng': target['lng'] + random.uniform(-2, 2)
                }
            })
        
        # Ensure we have coordinates for the frontend (backward compatibility)
        if not attack.get('coordinates') and attack.get('source_coordinates'):
            attack['coordinates'] = attack['source_coordinates']
        if not attack.get('country') and attack.get('source_country'):
            attack['country'] = attack['source_country']
        
        # Add metadata
        attack['collection_timestamp'] = datetime.utcnow().isoformat()
        attack['attack_id'] = f"{attack.get('source', 'unknown')}_{attack.get('source_ip', 'unknown')}_{int(datetime.utcnow().timestamp())}"
        
        enriched_attacks.append(attack)
    
    return enriched_attacks

async def health_monitor():
    """Background health monitoring"""
    while True:
        try:
            # Log connection stats periodically
            ws_stats = manager.get_stats()
            if ws_stats['current_connections'] > 0:
                logger.debug(f"WebSocket stats: {ws_stats}")
            
            await asyncio.sleep(300)  # Check every 5 minutes
            
        except Exception as e:
            logger.error(f"Health monitor error: {e}")
            await asyncio.sleep(60)

# Mount static files
app.mount("/static", StaticFiles(directory=settings.base_dir / "src" / "static"), name="static")



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
        ws_ping_interval=settings.websocket_ping_interval,
        ws_ping_timeout=settings.websocket_ping_timeout
    )