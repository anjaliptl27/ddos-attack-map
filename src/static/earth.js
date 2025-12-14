let globeInstance = null;
let attacks = [];
let rotateEnabled = true;
let rotationSpeed = 0.001;
let arcIntensity = 0.5;

function initializeGlobe() {
    const container = document.getElementById('globeContainer');

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0d1117);

    // Camera
    const camera = new THREE.PerspectiveCamera(
        45,
        container.clientWidth / container.clientHeight,
        0.1,
        1000
    );
    camera.position.z = 300;

    // Orbit Controls
    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Lights
    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 1);
    dir.position.set(1, 1, 1);
    scene.add(dir);

    // 🌍 Correct Globe()
    const globe = Globe()
        .globeImageUrl("//unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
        .bumpImageUrl("//unpkg.com/three-globe/example/img/earth-topology.png")
        .showAtmosphere(true)
        .atmosphereColor("#3a228a")
        .atmosphereAltitude(0.25)
        .arcsData(attacks)
        .arcColor("color")
        .arcAltitude(0.3)
        .arcStroke(0.5)
        .arcDashLength(0.5)
        .arcDashGap(1)
        .arcDashAnimateTime(2000);

    scene.add(globe);
    globeInstance = globe;

    // Resize
    window.addEventListener("resize", () => {
        camera.aspect = container.clientWidth / container.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(container.clientWidth, container.clientHeight);
    });

    // Animation Loop
    function animate() {
        requestAnimationFrame(animate);

        if (rotateEnabled) {
            globe.rotation.y += rotationSpeed;
        }

        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    connectWebSocket();
}

// ---------------- WebSocket -------------------

function connectWebSocket() {
    const ws = new WebSocket(`ws://${window.location.host}/ws`);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "new_attacks") {
            addAttacks(data.attacks);
        }
    };

    ws.onclose = () => setTimeout(connectWebSocket, 3000);
}

// ---------------- Add Attacks -----------------

function addAttacks(newAttacks) {
    newAttacks.forEach(a => {
        attacks.push({
            startLat: a.source_coordinates.lat,
            startLng: a.source_coordinates.lng,
            endLat: a.target_coordinates.lat,
            endLng: a.target_coordinates.lng,
            color: getColorFromConfidence(a.confidence || 0.5)
        });
    });

    if (globeInstance) {
        globeInstance.arcsData(attacks.slice(-120));
    }
}

function getColorFromConfidence(c) {
    if (c > 0.9) return "#ff0066";
    if (c > 0.7) return "#ff3300";
    if (c > 0.5) return "#ffaa00";
    return "#00ff88";
}

window.clearAttacks = function () {
    attacks = [];
    if (globeInstance) globeInstance.arcsData([]);
};

// Init
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeGlobe);
} else {
    initializeGlobe();
}
