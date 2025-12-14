import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

async def test_all_endpoints():
    token = os.getenv('CLOUDFLARE_API_TOKEN')
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    endpoints_to_test = [
        # Current endpoint
        ("https://api.cloudflare.com/client/v4/radar/attacks/layer3/summary", {"dateRange": "1h", "format": "JSON"}),
        
        # Alternative endpoints
        ("https://api.cloudflare.com/client/v4/radar/attacks/summary", {"dateRange": "1h", "format": "JSON"}),
        ("https://api.cloudflare.com/client/v4/radar/attacks", {"dateRange": "1h", "format": "JSON"}),
        
        # Without parameters
        ("https://api.cloudflare.com/client/v4/radar/attacks/layer3/summary", {}),
        
        # Different time ranges
        ("https://api.cloudflare.com/client/v4/radar/attacks/layer3/summary", {"dateRange": "24h"}),
        ("https://api.cloudflare.com/client/v4/radar/attacks/layer3/summary", {"dateRange": "7d"}),
    ]
    
    async with aiohttp.ClientSession() as session:
        for endpoint, params in endpoints_to_test:
            print(f"\nTesting: {endpoint}")
            print(f"Params: {params}")
            
            try:
                async with session.get(endpoint, headers=headers, params=params) as response:
                    print(f"Status: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        print(f"✅ SUCCESS! Data keys: {list(data.keys())}")
                        if data.get('result'):
                            print(f"Result keys: {list(data['result'].keys())}")
                        break  # Stop if we find a working endpoint
                    else:
                        error_text = await response.text()
                        print(f"❌ Error: {error_text[:200]}")
                        
            except Exception as e:
                print(f"❌ Exception: {e}")

asyncio.run(test_all_endpoints())