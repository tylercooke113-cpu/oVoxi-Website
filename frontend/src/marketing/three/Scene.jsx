import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

const COUNT_DESKTOP = 20000;
const COUNT_MOBILE  = 6000;

const VERTEX_SHADER = /* glsl */`
  attribute vec3  aTargetA;
  attribute vec3  aTargetB;
  attribute vec3  aScaleA;
  attribute vec3  aScaleB;
  attribute float aSeed;
  attribute float aCleared;

  uniform float uProgress;
  uniform float uTime;

  varying float vCleared;
  varying float vFogDepth;

  void main() {
    vec3 pos   = mix(aTargetA, aTargetB, uProgress);
    vec3 scale = mix(aScaleA,  aScaleB,  uProgress);

    // Slow ambient Y drift, fades over first 25% of scroll progress
    float drift = sin(aSeed * 6.28318 + uTime * 0.4) * 1.2;
    pos.y += drift * (1.0 - clamp(uProgress * 4.0, 0.0, 1.0));

    vec4 mvPosition = modelViewMatrix * vec4(position * scale + pos, 1.0);
    vFogDepth = -mvPosition.z;
    vCleared  = aCleared;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = /* glsl */`
  precision mediump float;

  varying float vCleared;
  varying float vFogDepth;

  void main() {
    vec3 grey  = vec3(0.541, 0.541, 0.580); // #8A8A94
    vec3 grad1 = vec3(0.706, 0.310, 0.831); // #B44FD4
    vec3 grad3 = vec3(0.420, 0.498, 0.831); // #6B7FD4

    vec3 color = mix(grey, mix(grad1, grad3, 0.5), vCleared);

    // Exponential fog toward black, tuned for 400-unit deep field
    float fogFactor = clamp(exp(-0.006 * vFogDepth), 0.0, 1.0);
    color *= fogFactor;

    gl_FragColor = vec4(color, 1.0);
  }
`;

function generateNoiseLayout(count) {
  const pos    = new Float32Array(count * 3);
  const scales = new Float32Array(count * 3);
  const seeds  = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    pos[i * 3]     = (Math.random() - 0.5) * 200;
    pos[i * 3 + 1] = (Math.random() - 0.5) * 60;
    pos[i * 3 + 2] = (Math.random() - 0.5) * 400;

    const w = 0.3 + Math.random() * 0.3;
    scales[i * 3]     = w;
    scales[i * 3 + 1] = 0.5 + Math.random() * 7.5;
    scales[i * 3 + 2] = w;

    seeds[i] = Math.random();
  }

  return { pos, scales, seeds };
}

function BarField({ count }) {
  const { geo, mat } = useMemo(() => {
    const g = new THREE.BoxGeometry(1, 1, 1);
    const { pos, scales, seeds } = generateNoiseLayout(count);
    const cleared = new Float32Array(count); // all 0 — all grey in Phase 4

    g.setAttribute('aTargetA', new THREE.InstancedBufferAttribute(pos.slice(),    3));
    g.setAttribute('aTargetB', new THREE.InstancedBufferAttribute(pos.slice(),    3));
    g.setAttribute('aScaleA',  new THREE.InstancedBufferAttribute(scales.slice(), 3));
    g.setAttribute('aScaleB',  new THREE.InstancedBufferAttribute(scales.slice(), 3));
    g.setAttribute('aSeed',    new THREE.InstancedBufferAttribute(seeds,          1));
    g.setAttribute('aCleared', new THREE.InstancedBufferAttribute(cleared,        1));

    const m = new THREE.ShaderMaterial({
      vertexShader:   VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms: {
        uProgress: { value: 0 },
        uTime:     { value: 0 },
      },
    });

    return { geo: g, mat: m };
  }, [count]);

  useFrame(({ clock }) => {
    mat.uniforms.uTime.value = clock.getElapsedTime();
    // uProgress wired to scroll in Phase 5
  });

  return (
    <instancedMesh
      args={[geo, mat, count]}
      frustumCulled={false}
    />
  );
}

export default function Scene() {
  const count = window.innerWidth < 768 ? COUNT_MOBILE : COUNT_DESKTOP;

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none',
      }}
    >
      <Canvas
        camera={{ fov: 50, position: [0, 5, 120], near: 0.1, far: 2000 }}
        gl={{ antialias: false }}
        style={{ background: '#000000', width: '100%', height: '100%' }}
      >
        <BarField count={count} />
      </Canvas>
    </div>
  );
}
