import requests
import os

# Download a high-quality Earth texture
def download_earth_texture():
    texture_url = "https://raw.githubusercontent.com/janarosmonaliev/github-globe/main/public/textures/earth_texture.jpg"
    local_path = "src/static/textures/globe_2.jpg"
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    response = requests.get(texture_url)
    if response.status_code == 200:
        with open(local_path, 'wb') as f:
            f.write(response.content)
        print("✅ Earth texture downloaded!")
    else:
        print("❌ Could not download texture, using fallback")

download_earth_texture()