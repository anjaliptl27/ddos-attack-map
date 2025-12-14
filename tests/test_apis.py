import asyncio
import os
from src.api.cloudflare_client import CloudflareClient
from src.api.abuseipdb_client import AbuseIPDBClient
from dotenv import load_dotenv

load_dotenv()

async def test_cloudflare():
    print("Testing Cloudflare API...")
    client = CloudflareClient(os.getenv('CLOUDFLARE_API_TOKEN'))
    async with client:
        data = await client.get_radar_attacks_summary("1h")
        if data:
            print("✅ Cloudflare API working!")
            print(f"Data keys: {list(data.keys())}")
        else:
            print("❌ Cloudflare API failed")

async def test_abuseipdb():
    print("Testing AbuseIPDB API...")
    client = AbuseIPDBClient(os.getenv('ABUSEIPDB_API_KEY'))
    async with client:
        data = await client.get_blacklist(limit=5)
        if data:
            print("✅ AbuseIPDB API working!")
            print(f"Found {len(data)} blacklisted IPs")
        else:
            print("❌ AbuseIPDB API failed")

async def main():
    await test_cloudflare()
    await test_abuseipdb()

if __name__ == "__main__":
    asyncio.run(main())