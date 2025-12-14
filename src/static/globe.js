class GitHubStyleGlobe {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.attacks = new Map();
        this.labels = new Map();
        this.arcs = new Map();
        
        this.stats = {
            totalAttacks: 0,
            activeAttacks: 0,
            countriesHit: new Set()
        };
        
        this.dotIntensity = 0.3;
        this.autoRotate = true;
        this.showLabels = true;
        
        this.initGitHubStyleGlobe();
        this.connectWebSocket();
        this.setupUI();
    }

async initGitHubStyleGlobe() {
    try {
        // SCENE SETUP
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x000011);
        
        // CAMERA
        this.camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        this.camera.position.z = 300;
        
        // RENDERER
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true, 
            alpha: true,
            powerPreference: "high-performance"
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);
        
        // CONTROLS
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.rotateSpeed = 0.5;
        this.controls.autoRotate = this.autoRotate;
        this.controls.autoRotateSpeed = 0.3;
        this.controls.minDistance = 150;
        this.controls.maxDistance = 500;
        
        // LIGHTING
        this.setupLighting();
        
        // CREATE GLOBE WITH TEXTURE
        await this.createTexturedGlobe();
        
        // CREATE ATMOSPHERIC EFFECTS
        this.createAtmosphere();
        
        // CREATE BACKGROUND STARS
        this.createStarfield();
        
        // CREATE GRID LINES
        this.createGridLines();
        
        // CREATE CONTINENT OUTLINES
        this.createContinentOutlines();
        
        // CREATE COUNTRY LABELS
        this.createCountryLabels();
        
        // START ANIMATION
        this.animate();
        
        // HANDLE RESIZE
        window.addEventListener('resize', () => this.onWindowResize());
        
        console.log("✅ GitHub-style DDoS Globe initialized with Earth texture");
        
    } catch (error) {
        console.error("Globe initialization failed:", error);
        this.showError();
    }
}

    setupLighting() {
    // Ambient light - keep it low to maintain cyber feel
    const ambientLight = new THREE.AmbientLight(0x404040, 0.4);
    this.scene.add(ambientLight);
    
    // Main directional light (simulating sun)
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight.position.set(200, 100, 50);
    directionalLight.castShadow = true;
    this.scene.add(directionalLight);
    
    // Hemisphere light for atmospheric scattering effect
    const hemisphereLight = new THREE.HemisphereLight(0x4488ff, 0x44aa44, 0.6);
    this.scene.add(hemisphereLight);
    
    // Add point lights at strategic positions for better continent illumination
    const continentLights = [
        { position: [100, 50, -100], color: 0xffffaa, intensity: 0.3 }, // Europe/Asia
        { position: [-150, 30, 0], color: 0xaaffff, intensity: 0.3 },  // Americas
        { position: [0, -80, 100], color: 0xffaaff, intensity: 0.2 },  // Antarctica
    ];
    
    continentLights.forEach(lightConfig => {
        const light = new THREE.PointLight(
            lightConfig.color, 
            lightConfig.intensity, 
            200
        );
        light.position.set(...lightConfig.position);
        this.scene.add(light);
    });
}

createGridLines() {
    // Create longitude lines (meridians)
    const longitudeGeometry = new THREE.BufferGeometry();
    const longitudePoints = [];
    
    // Create 12 meridians (every 30 degrees)
    for (let i = 0; i < 12; i++) {
        const lon = (i * 30) * Math.PI / 180;
        
        // Create a circle for each meridian
        for (let j = 0; j <= 180; j++) {
            const lat = (j - 90) * Math.PI / 180;
            
            const x = Math.cos(lat) * Math.cos(lon) * 101;
            const y = Math.sin(lat) * 101;
            const z = Math.cos(lat) * Math.sin(lon) * 101;
            
            longitudePoints.push(x, y, z);
        }
    }
    
    longitudeGeometry.setAttribute(
        'position', 
        new THREE.Float32BufferAttribute(longitudePoints, 3)
    );
    
    const longitudeMaterial = new THREE.LineBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.15,
        linewidth: 1
    });
    
    const longitudes = new THREE.LineSegments(longitudeGeometry, longitudeMaterial);
    this.scene.add(longitudes);
    
    // Create latitude lines (parallels)
    const latitudeGeometry = new THREE.BufferGeometry();
    const latitudePoints = [];
    
    // Create 6 parallels (every 30 degrees)
    for (let i = 0; i < 6; i++) {
        const lat = (i * 30 - 60) * Math.PI / 180;
        const radius = Math.cos(lat) * 101;
        const height = Math.sin(lat) * 101;
        
        // Create a circle for each parallel
        for (let j = 0; j <= 360; j++) {
            const lon = j * Math.PI / 180;
            
            const x = Math.cos(lon) * radius;
            const y = height;
            const z = Math.sin(lon) * radius;
            
            latitudePoints.push(x, y, z);
        }
    }
    
    latitudeGeometry.setAttribute(
        'position', 
        new THREE.Float32BufferAttribute(latitudePoints, 3)
    );
    
    const latitudeMaterial = new THREE.LineBasicMaterial({
        color: 0x4488ff,
        transparent: true,
        opacity: 0.15,
        linewidth: 1
    });
    
    const latitudes = new THREE.LineSegments(latitudeGeometry, latitudeMaterial);
    this.scene.add(latitudes);
}

createContinentOutlines() {
    // Continent coordinates (simplified)
    const continents = [
        {
            name: 'North America',
            points: [
                { lat: 70, lng: -170 }, { lat: 70, lng: -60 },
                { lat: 15, lng: -60 }, { lat: 15, lng: -170 }
            ]
        },
        {
            name: 'South America',
            points: [
                { lat: 15, lng: -80 }, { lat: -55, lng: -80 },
                { lat: -55, lng: -35 }, { lat: 15, lng: -35 }
            ]
        },
        {
            name: 'Europe',
            points: [
                { lat: 70, lng: -10 }, { lat: 70, lng: 40 },
                { lat: 35, lng: 40 }, { lat: 35, lng: -10 }
            ]
        },
        // Add other continents...
    ];
    
    continents.forEach(continent => {
        const points = [];
        
        // Convert lat/lng to 3D points
        continent.points.forEach(coord => {
            const pos = this.latLngToVector3(coord.lat, coord.lng, 101);
            points.push(pos);
        });
        
        // Close the polygon
        points.push(points[0].clone());
        
        // Create line geometry
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({
            color: 0x44ff44,
            transparent: true,
            opacity: 0.3,
            linewidth: 2
        });
        
        const outline = new THREE.Line(geometry, material);
        this.scene.add(outline);
    });
}

    async createTexturedGlobe() {
    // Create geometry first
    const geometry = new THREE.SphereGeometry(100, 64, 64);
    
    // Create material with Earth-like colors as fallback
    const material = new THREE.MeshPhongMaterial({
        color: 0x4488ff,  // Blue water color as fallback
        specular: new THREE.Color(0x333333),
        shininess: 5,
        transparent: false,
        wireframe: false
    });
    
    this.earth = new THREE.Mesh(geometry, material);
    this.scene.add(this.earth);
    
    // Try loading texture
    const textureLoader = new THREE.TextureLoader();
    
    // Use a reliable Earth texture from NASA or other source
    const earthTextureURLs = [
        'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_atmos_2048.jpg',
        'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg',
        '/static/textures/globe_2.jpg'
    ];
    
    // Try loading from multiple sources
    for (const url of earthTextureURLs) {
        try {
            const texture = await new Promise((resolve, reject) => {
                textureLoader.load(
                    url,
                    resolve,  // Success
                    undefined,  // Progress
                    reject     // Error
                );
            });
            
            // Apply the loaded texture
            this.earth.material.map = texture;
            this.earth.material.needsUpdate = true;
            
            console.log(`✅ Earth texture loaded from: ${url}`);
            
            // Add bump/normal map for terrain detail
            try {
                const bumpTexture = await new Promise((resolve) => {
                    textureLoader.load(
                        'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/earth_normal_2048.jpg',
                        resolve,
                        undefined,
                        () => resolve(null)  // Silently fail if not available
                    );
                });
                
                if (bumpTexture) {
                    this.earth.material.bumpMap = bumpTexture;
                    this.earth.material.bumpScale = 0.05;
                    console.log('✅ Bump map loaded');
                }
            } catch (bumpError) {
                console.log('ℹ️ No bump map available, using flat texture');
            }
            
            return;  // Exit if successful
            
        } catch (error) {
            console.log(`❌ Failed to load texture from ${url}, trying next...`);
        }
    }
    
    // If all URLs fail, create a procedurally generated texture
    console.log('⚠️ Using procedurally generated Earth texture');
    this.createProceduralEarthTexture();
}
createCountryLabels() {
    // Major countries to label
    const countries = [
        { name: 'USA', lat: 40, lng: -100 },
        { name: 'China', lat: 35, lng: 105 },
        { name: 'Russia', lat: 60, lng: 100 },
        { name: 'Germany', lat: 51, lng: 10 },
        { name: 'Japan', lat: 36, lng: 138 },
        { name: 'Brazil', lat: -15, lng: -55 },
        { name: 'India', lat: 20, lng: 78 },
        { name: 'Australia', lat: -25, lng: 135 },
        { name: 'UK', lat: 54, lng: -2 },
        { name: 'France', lat: 47, lng: 2 }
    ];
    
    countries.forEach(country => {
        const label = document.createElement('div');
        label.textContent = country.name;
        label.style.cssText = `
            position: absolute;
            color: rgba(255, 255, 255, 0.7);
            font-family: Arial, sans-serif;
            font-size: 10px;
            font-weight: bold;
            text-shadow: 0 1px 2px rgba(0,0,0,0.8);
            pointer-events: none;
            z-index: 10;
        `;
        
        this.container.appendChild(label);
        
        // Store reference for updating position
        if (!this.countryLabels) this.countryLabels = [];
        this.countryLabels.push({
            element: label,
            lat: country.lat,
            lng: country.lng
        });
    });
}

updateCountryLabels() {
    if (!this.countryLabels) return;
    
    this.countryLabels.forEach(label => {
        const pos = this.latLngToVector3(label.lat, label.lng, 102);
        pos.project(this.camera);
        
        const x = (pos.x * 0.5 + 0.5) * window.innerWidth;
        const y = (-(pos.y * 0.5) + 0.5) * window.innerHeight;
        
        // Only show if visible on screen
        if (x > 0 && x < window.innerWidth && y > 0 && y < window.innerHeight) {
            label.element.style.left = `${x}px`;
            label.element.style.top = `${y}px`;
            label.element.style.display = 'block';
        } else {
            label.element.style.display = 'none';
        }
    });
}
createProceduralEarthTexture() {
    // Create a simple canvas texture with continents
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = 1024;
    const ctx = canvas.getContext('2d');
    
    // Draw oceans (blue background)
    ctx.fillStyle = '#1a3a8f';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    // Draw continents (green shapes)
    ctx.fillStyle = '#2d5a27';
    
    // Africa
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.25, canvas.height * 0.6, 250, 300, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Americas
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.15, canvas.height * 0.4, 200, 400, -0.2, 0, Math.PI * 2);
    ctx.fill();
    
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.3, canvas.height * 0.3, 180, 300, 0.3, 0, Math.PI * 2);
    ctx.fill();
    
    // Asia
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.65, canvas.height * 0.4, 350, 350, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Australia
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.8, canvas.height * 0.7, 120, 120, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Antarctica (white)
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.ellipse(canvas.width * 0.5, canvas.height * 0.95, canvas.width * 0.4, 40, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Create texture from canvas
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.ClampToEdgeWrapping;
    
    this.earth.material.map = texture;
    this.earth.material.needsUpdate = true;
}


    createAtmosphere() {
        const atmosphereGeometry = new THREE.SphereGeometry(102, 64, 64);
        const atmosphereMaterial = new THREE.ShaderMaterial({
            uniforms: {
                glowColor: { value: new THREE.Color(0x0088ff) },
                viewVector: { value: this.camera.position }
            },
            vertexShader: `
                uniform vec3 viewVector;
                varying float intensity;
                void main() {
                    vec3 vNormal = normalize(normalMatrix * normal);
                    vec3 vNormel = normalize(normalMatrix * viewVector);
                    intensity = pow(0.8 - dot(vNormal, vNormel), 2.0);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 glowColor;
                varying float intensity;
                void main() {
                    vec3 glow = glowColor * intensity;
                    gl_FragColor = vec4(glow, intensity * 0.2);
                }
            `,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending,
            transparent: true
        });
        
        this.atmosphere = new THREE.Mesh(atmosphereGeometry, atmosphereMaterial);
        this.scene.add(this.atmosphere);
    }

    createStarfield() {
        const starGeometry = new THREE.BufferGeometry();
        const starMaterial = new THREE.PointsMaterial({
            color: 0xffffff,
            size: 0.1,
            transparent: true
        });
        
        const starVertices = [];
        for (let i = 0; i < 10000; i++) {
            const x = (Math.random() - 0.5) * 2000;
            const y = (Math.random() - 0.5) * 2000;
            const z = (Math.random() - 0.5) * 2000;
            starVertices.push(x, y, z);
        }
        
        starGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starVertices, 3));
        const stars = new THREE.Points(starGeometry, starMaterial);
        this.scene.add(stars);
    }

    // Convert lat/lng to 3D position on sphere
    latLngToVector3(lat, lng, radius = 100) {
        const phi = (90 - lat) * Math.PI / 180;
        const theta = (lng + 180) * Math.PI / 180;
        
        return new THREE.Vector3(
            -radius * Math.sin(phi) * Math.cos(theta),
            radius * Math.cos(phi),
            radius * Math.sin(phi) * Math.sin(theta)
        );
    }

    // Create attack visualization
    createAttackVisualization(sourcePos, targetPos, attack) {
        const attackColor = this.getAttackColor(attack.confidence);
        
        // 1. Create source dot (attacker)
        const sourceDot = this.createDot(sourcePos, attackColor, 2.0);
        
        // 2. Create target dot (victim)
        const targetDot = this.createDot(targetPos, 0xff4444, 1.5); // Red for target
        
        // 3. Create animated arc from source to target
        const arc = this.createAnimatedArc(sourcePos, targetPos, attackColor);
        
        // 4. Create labels
        const sourceLabel = this.createLabel(sourcePos, this.getLocationText(attack, 'source'), 'attacker');
        const targetLabel = this.createLabel(targetPos, this.getLocationText(attack, 'target'), 'target');
        
        return {
            sourceDot: sourceDot,
            targetDot: targetDot,
            arc: arc,
            sourceLabel: sourceLabel,
            targetLabel: targetLabel,
            startTime: Date.now(),
            pulsePhase: 0
        };
    }

    createDot(position, color, size = 1.5) {
        const dotGeometry = new THREE.SphereGeometry(size, 8, 8);
        const dotMaterial = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.9 * this.dotIntensity
        });
        
        const dot = new THREE.Mesh(dotGeometry, dotMaterial);
        dot.position.copy(position);
        
        // Add glow effect
        const glowGeometry = new THREE.SphereGeometry(size * 2, 8, 8);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.4 * this.dotIntensity,
            blending: THREE.AdditiveBlending
        });
        
        const glow = new THREE.Mesh(glowGeometry, glowMaterial);
        glow.position.copy(position);
        
        // Add pulsing light
        const pointLight = new THREE.PointLight(color, this.dotIntensity, 15);
        pointLight.position.copy(position);
        
        const dotGroup = new THREE.Group();
        dotGroup.add(dot);
        dotGroup.add(glow);
        dotGroup.add(pointLight);
        
        this.scene.add(dotGroup);
        
        return {
            group: dotGroup,
            dot: dot,
            glow: glow,
            light: pointLight
        };
    }

    createAnimatedArc(startPos, endPos, color) {
        // Create curved arc
        const midPoint = new THREE.Vector3()
            .addVectors(startPos, endPos)
            .multiplyScalar(0.5)
            .normalize()
            .multiplyScalar(150);
        
        const curve = new THREE.QuadraticBezierCurve3(startPos, midPoint, endPos);
        const points = curve.getPoints(50);
        
        // Create the arc line
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const material = new THREE.LineBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.7,
            linewidth: 2
        });
        
        const arc = new THREE.Line(geometry, material);
        this.scene.add(arc);
        
        // Create moving particle along the arc
        const particleGeometry = new THREE.SphereGeometry(0.5, 4, 4);
        const particleMaterial = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 1.0
        });
        
        const particle = new THREE.Mesh(particleGeometry, particleMaterial);
        this.scene.add(particle);
        
        return {
            line: arc,
            particle: particle,
            curve: curve,
            progress: 0,
            speed: 0.02
        };
    }

    createLabel(position, text, type) {
        // Create HTML label
        const label = document.createElement('div');
        label.style.cssText = `
            position: absolute;
            color: ${type === 'attacker' ? '#ff6b6b' : '#4ecdc4'};
            background: rgba(13, 17, 23, 0.9);
            padding: 4px 8px;
            border-radius: 4px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-size: 11px;
            font-weight: 600;
            border: 1px solid ${type === 'attacker' ? '#ff6b6b' : '#4ecdc4'};
            pointer-events: none;
            white-space: nowrap;
            backdrop-filter: blur(5px);
            z-index: 100;
            opacity: ${this.showLabels ? '1' : '0'};
            transition: opacity 0.3s;
        `;
        label.textContent = text;
        
        this.container.appendChild(label);
        
        return {
            element: label,
            position: position.clone(),
            type: type
        };
    }

    getLocationText(attack, type) {
        if (type === 'source') {
            const city = attack.source_city || 'Unknown City';
            const country = attack.source_country_name || 'Unknown Country';
            return `🦠 ${city}, ${country}`;
        } else {
            const city = attack.target_city || 'Unknown City';
            const country = attack.target_country_name || 'Unknown Country';
            return `🎯 ${city}, ${country}`;
        }
    }

    // Add DDoS attack visualization
    addAttack(attack) {
        // Only process DDoS attacks
        if (!attack.attack_type.toLowerCase().includes('ddos')) {
            console.log('Skipping non-DDoS attack:', attack.attack_type);
            return;
        }

        const sourceCoords = attack.source_coordinates;
        const targetCoords = attack.target_coordinates;
        
        if (!sourceCoords || !targetCoords) {
            console.log('Missing coordinates for attack:', attack);
            return;
        }

        // Convert coordinates to 3D positions
        const sourcePos = this.latLngToVector3(sourceCoords.lat, sourceCoords.lng);
        const targetPos = this.latLngToVector3(targetCoords.lat, targetCoords.lng);
        
        // Create visualization
        const visualization = this.createAttackVisualization(sourcePos, targetPos, attack);
        
        // Store attack data
        const attackId = Date.now() + Math.random();
        this.attacks.set(attackId, {
            ...visualization,
            attackData: attack,
            startTime: Date.now()
        });
        
        // Update statistics
        this.stats.totalAttacks++;
        this.stats.activeAttacks++;
        if (attack.source_country) {
            this.stats.countriesHit.add(attack.source_country);
        }
        
        this.updateUI();
        
        console.log(`✅ Added DDoS attack: ${attack.source_city} → ${attack.target_city}`);
      // Schedule removal after 60 seconds
        setTimeout(() => {
    this.fadeOutAndRemove(attackId);
}, 60000);
    
}
fadeOutAndRemove(attackId) {
    const attackData = this.attacks.get(attackId);
    if (!attackData) return;

    // Prevent double fading
    if (attackData.fading) return;
    attackData.fading = true;

    let opacity = 1;

    const fade = () => {
        // If attack was removed early — STOP
        if (!this.attacks.has(attackId)) return;

        opacity -= 0.05;

        if (opacity <= 0) {
            this.removeAttack(attackId);
            return;
        }

        // ---- ARC FADE ----
        if (attackData.arc?.line?.material) {
            attackData.arc.line.material.transparent = true;
            attackData.arc.line.material.opacity = opacity;
        }
        if (attackData.arc?.particle?.material) {
            attackData.arc.particle.material.transparent = true;
            attackData.arc.particle.material.opacity = opacity;
        }

        // ---- DOTS FADE ----
        if (attackData.sourceDot?.dot?.material) {
            attackData.sourceDot.dot.material.opacity = opacity;
        }
        if (attackData.sourceDot?.glow?.material) {
            attackData.sourceDot.glow.material.opacity = opacity * 0.4;
        }
        if (attackData.targetDot?.dot?.material) {
            attackData.targetDot.dot.material.opacity = opacity;
        }
        if (attackData.targetDot?.glow?.material) {
            attackData.targetDot.glow.material.opacity = opacity * 0.4;
        }

        // ---- LABELS FADE ----
        if (attackData.sourceLabel?.element) {
            attackData.sourceLabel.element.style.opacity = opacity;
        }
        if (attackData.targetLabel?.element) {
            attackData.targetLabel.element.style.opacity = opacity;
        }

        requestAnimationFrame(fade);
    };

    fade();
}


    removeAttack(attackId) {
        if (this.attacks.has(attackId)) {
            const attackData = this.attacks.get(attackId);
            
            // Remove all 3D elements
            this.scene.remove(attackData.sourceDot.group);
            this.scene.remove(attackData.targetDot.group);
            if (attackData.arc) {
                this.scene.remove(attackData.arc.line);
                this.scene.remove(attackData.arc.particle);
            }
            
            // Remove HTML labels
            if (attackData.sourceLabel && attackData.sourceLabel.element.parentNode) {
                attackData.sourceLabel.element.remove();
            }
            if (attackData.targetLabel && attackData.targetLabel.element.parentNode) {
                attackData.targetLabel.element.remove();
            }
            
            this.attacks.delete(attackId);
            this.stats.activeAttacks--;
            this.updateUI();
        }
    }

    getAttackColor(confidence) {
        // Color coding based on DDoS attack confidence
        if (confidence > 0.9) return 0xff0066; // Critical - Bright Pink
        if (confidence > 0.7) return 0xff3300; // High - Orange-Red
        if (confidence > 0.5) return 0xffaa00; // Medium - Amber
        return 0x00ff88; // Low - Cyan-Green
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        
        // Update controls
        if (this.controls) {
            this.controls.update();
        }
        
        // Animate attacks
        this.animateAttacks();
        
        // Update labels position
        this.updateLabels();
        
        // Render scene
        this.renderer.render(this.scene, this.camera);
    }

    animateAttacks() {
        const now = Date.now();
        
        this.attacks.forEach((attackData, attackId) => {
            const age = now - attackData.startTime;
            attackData.pulsePhase += 0.1;
            
            // Pulsing effect for dots
            this.animateDot(attackData.sourceDot, attackData.pulsePhase);
            this.animateDot(attackData.targetDot, attackData.pulsePhase);
            
            // Animate arc particle
            if (attackData.arc) {
                this.animateArc(attackData.arc);
            }
        });
    }

    animateDot(dotData, pulsePhase) {
        if (dotData.dot) {
            const pulse = 0.8 + Math.sin(pulsePhase) * 0.4;
            dotData.dot.scale.set(pulse, pulse, pulse);
        }
        
        if (dotData.glow) {
            const glowPulse = 1 + Math.sin(pulsePhase * 0.5) * 0.2;
            dotData.glow.scale.set(glowPulse, glowPulse, glowPulse);
        }
        
        if (dotData.light) {
            dotData.light.intensity = this.dotIntensity * (0.5 + Math.sin(pulsePhase) * 0.3);
        }
    }

    animateArc(arcData) {
        // Move particle along the curve
        arcData.progress += arcData.speed;
        if (arcData.progress > 1) {
            arcData.progress = 0;
        }
        
        const point = arcData.curve.getPoint(arcData.progress);
        arcData.particle.position.copy(point);
        
        // Make particle pulse
        const scale = 0.8 + Math.sin(Date.now() * 0.01) * 0.4;
        arcData.particle.scale.set(scale, scale, scale);
    }

    updateLabels() {
        this.attacks.forEach((attackData) => {
            this.updateLabelPosition(attackData.sourceLabel);
            this.updateLabelPosition(attackData.targetLabel);
        });
    }

    updateLabelPosition(labelData) {
        if (!labelData || !labelData.element) return;
        
        // Convert 3D position to 2D screen coordinates
        const vector = labelData.position.clone();
        vector.project(this.camera);
        
        const x = (vector.x * 0.5 + 0.5) * window.innerWidth;
        const y = (-(vector.y * 0.5) + 0.5) * window.innerHeight;
        
        // Position label near the dot
        labelData.element.style.left = x + 'px';
        labelData.element.style.top = y + 'px';
        
        // Show/hide based on setting
        labelData.element.style.opacity = this.showLabels ? '1' : '0';
    }

    onWindowResize() {
        this.camera.aspect = window.innerWidth / window.innerHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(window.innerWidth, window.innerHeight);
    }

    setupUI() {
        this.createGitHubStyleDashboard();
    }

    createGitHubStyleDashboard() {
        const dashboard = document.createElement('div');
        dashboard.style.cssText = `
            position: absolute;
            bottom: 30px;
            left: 30px;
            background: rgba(13, 17, 23, 0.9);
            color: #f0f6fc;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #30363d;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            backdrop-filter: blur(10px);
            min-width: 280px;
            z-index: 1000;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
        `;
        
        dashboard.innerHTML = `
            <div style="margin-bottom: 15px;">
                <h3 style="margin: 0 0 8px 0; color: #f0f6fc; font-size: 16px; font-weight: 600;">
                    🌐 DDoS Attack Monitor
                </h3>
                <div style="height: 1px; background: #30363d; margin: 8px 0;"></div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 14px;">
                <div>
                    <div style="color: #8b949e; font-size: 12px; margin-bottom: 4px;">ACTIVE DDoS</div>
                    <div style="color: #ff7b72; font-size: 20px; font-weight: 600;" id="activeCount">0</div>
                </div>
                <div>
                    <div style="color: #8b949e; font-size: 12px; margin-bottom: 4px;">TOTAL DDoS</div>
                    <div style="color: #d29922; font-size: 20px; font-weight: 600;" id="totalCount">0</div>
                </div>
                <div>
                    <div style="color: #8b949e; font-size: 12px; margin-bottom: 4px;">COUNTRIES</div>
                    <div style="color: #3fb950; font-size: 16px; font-weight: 600;" id="countriesCount">0</div>
                </div>
                <div>
                    <div style="color: #8b949e; font-size: 12px; margin-bottom: 4px;">INTENSITY</div>
                    <div style="color: #a5d6ff; font-size: 16px; font-weight: 600;" id="dotIntensity">30%</div>
                </div>
            </div>
            
            <div style="margin-top: 15px; padding-top: 12px; border-top: 1px solid #30363d;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                    <div style="width: 8px; height: 8px; background: #ff6b6b; border-radius: 50%;"></div>
                    <div style="font-size: 11px; color: #8b949e;">🦠 = Attacker</div>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="width: 8px; height: 8px; background: #4ecdc4; border-radius: 50%;"></div>
                    <div style="font-size: 11px; color: #8b949e;">🎯 = Target</div>
                </div>
            </div>
            
            <div style="margin-top: 15px; padding-top: 12px; border-top: 1px solid #30363d;">
                <div style="font-size: 11px; color: #8b949e;">
                    Drag to rotate • Scroll to zoom • Arcs show attack paths
                </div>
            </div>
        `;
        
        this.container.appendChild(dashboard);
    }

    updateUI() {
        document.getElementById('activeCount').textContent = this.stats.activeAttacks;
        document.getElementById('totalCount').textContent = this.stats.totalAttacks;
        document.getElementById('countriesCount').textContent = this.stats.countriesHit.size;
        document.getElementById('dotIntensity').textContent = Math.round(this.dotIntensity * 100) + '%';
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('🔗 Connected to DDoS attack feed');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'new_attacks') {
                    // Filter and process only DDoS attacks
                    const ddosAttacks = data.attacks.filter(attack => 
                        attack.attack_type.toLowerCase().includes('ddos')
                    );
                    
                    if (ddosAttacks.length > 0) {
                        console.log(`🎯 Processing ${ddosAttacks.length} DDoS attacks`);
                        ddosAttacks.forEach(attack => this.addAttack(attack));
                    }
                }
            } catch (error) {
                console.error('Error parsing attack data:', error);
            }
        };
        
        this.ws.onclose = () => {
            console.log('Connection lost, reconnecting...');
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    showError() {
        this.container.innerHTML = `
            <div style="
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                text-align: center;
                color: #ff7b72;
                background: rgba(13, 17, 23, 0.9);
                padding: 30px;
                border-radius: 12px;
                border: 1px solid #30363d;
            ">
                <h2>⚠️ Globe Initialization Failed</h2>
                <p>Please check the console for details</p>
                <button onclick="location.reload()" style="
                    background: #238636;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    margin-top: 15px;
                    cursor: pointer;
                ">Retry</button>
            </div>
        `;
    }
}

// Control functions
function toggleRotation() {
    if (window.githubGlobe) {
        window.githubGlobe.controls.autoRotate = !window.githubGlobe.controls.autoRotate;
    }
}

function adjustIntensity(change) {
    if (window.githubGlobe) {
        window.githubGlobe.dotIntensity = Math.max(0.1, Math.min(1, window.githubGlobe.dotIntensity + change));
        window.githubGlobe.updateUI();
    }
}

function toggleLabels() {
    if (window.githubGlobe) {
        window.githubGlobe.showLabels = !window.githubGlobe.showLabels;
        window.githubGlobe.updateLabels();
    }
}

function clearAttacks() {
    if (window.githubGlobe) {
        window.githubGlobe.attacks.forEach((data, id) => {
            window.githubGlobe.removeAttack(id);
        });
    }
}

// Initialize GitHub-style globe
document.addEventListener('DOMContentLoaded', () => {
    console.log('🌍 Initializing GitHub-style DDoS Attack Globe...');
    window.githubGlobe = new GitHubStyleGlobe('globeContainer');
});