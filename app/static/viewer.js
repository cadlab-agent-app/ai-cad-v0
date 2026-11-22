import * as THREE from 'three';
import { STLLoader } from '/static/vendor/STLLoader.js';
import { OrbitControls } from '/static/vendor/OrbitControls.js';

export function createViewer(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0xeff3ef, 1);
  container.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 10000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x658176, 2.5));
  const light = new THREE.DirectionalLight(0xffffff, 3);
  light.position.set(100, 180, 120); scene.add(light);
  let mesh = null, extent = 100;
  const grid = new THREE.GridHelper(400, 40, 0xb4c8ba, 0xd4dfd5);
  grid.position.y = -0.2; scene.add(grid);
  function reset() {
    camera.position.set(extent * 1.35, extent * 1.05, extent * 1.5);
    controls.target.set(0, extent * 0.15, 0); controls.update();
  }
  function clear() {
    if (mesh) { scene.remove(mesh); mesh.geometry.dispose(); mesh.material.dispose(); mesh = null; }
    document.querySelector('#empty-state').hidden = false;
  }
  function setGeometry(geometry) {
    clear();
    // CAD Z-up to viewer Y-up, in millimetres.
    geometry.rotateX(-Math.PI / 2); geometry.computeBoundingBox();
    const box = geometry.boundingBox, center = box.getCenter(new THREE.Vector3());
    geometry.translate(-center.x, -box.min.y, -center.z);
    geometry.computeVertexNormals();
    const size = box.getSize(new THREE.Vector3()); extent = Math.max(size.x, size.y, size.z, 10);
    mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0x4f9480, roughness: 0.42, metalness: 0.2 }));
    scene.add(mesh); grid.scale.setScalar(extent / 100);
    document.querySelector('#empty-state').hidden = true; reset();
  }
  const resize = new ResizeObserver(() => {
    renderer.setSize(container.clientWidth, container.clientHeight, false);
    camera.aspect = container.clientWidth / container.clientHeight; camera.updateProjectionMatrix();
  }); resize.observe(container);
  reset();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
  return {
    clear, reset,
    async load(url) {
      const response = await fetch(url);
      if (!response.ok) throw new Error('STL download failed');
      const geometry = new STLLoader().parse(await response.arrayBuffer());
      setGeometry(geometry);
    }
  };
}
