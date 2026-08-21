import { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { useScrollProgress } from '../hooks/useScrollProgress';

const COUNT_DESKTOP = 20000;
const COUNT_MOBILE  = 6000;

const p2in  = (t) => t < 0.5 ? 2*t*t : 1 - Math.pow(-2*t+2, 2)/2;
const p3out = (t) => 1 - Math.pow(1-t, 3);

// Gate state helper -- shared by BarField and GatePlane
function computeGateState(p) {
  if (p < 0.35 || p >= 0.72) return { gateZ: -200, gateAmt: 0 };
  if (p < 0.52) return { gateZ: -150, gateAmt: (p - 0.35) / 0.17 };
  if (p < 0.62) return { gateZ: -150 + ((p - 0.52) / 0.10) * 300, gateAmt: 1 };
  return { gateZ: 150, gateAmt: Math.max(0, 1 - (p - 0.62) / 0.10) };
}

// ---- Bar shaders ----

const VERTEX_SHADER = /* glsl */`
  attribute vec3  aTargetA;
  attribute vec3  aTargetB;
  attribute vec3  aScaleA;
  attribute vec3  aScaleB;
  attribute float aSeed;
  attribute float aCleared;
  attribute float aClearedB;

  uniform float uProgress;
  uniform float uGlobalP;
  uniform float uTime;

  varying float vCleared;
  varying float vFogDepth;
  varying float vPosZ;

  void main() {
    vec3 pos   = mix(aTargetA, aTargetB, uProgress);
    vec3 scale = mix(aScaleA,  aScaleB,  uProgress);
    vCleared   = mix(aCleared, aClearedB, uProgress);
    vPosZ      = pos.z;

    float drift = sin(aSeed * 6.28318 + uTime * 0.4) * 1.2;
    pos.y += drift * (1.0 - clamp(uGlobalP * 10.0, 0.0, 1.0));

    vec4 mvPosition = modelViewMatrix * vec4(position * scale + pos, 1.0);
    vFogDepth = -mvPosition.z;
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const FRAGMENT_SHADER = /* glsl */`
  precision mediump float;

  uniform float uGateZ;
  uniform float uGateAmt;

  varying float vCleared;
  varying float vFogDepth;
  varying float vPosZ;

  void main() {
    vec3 grey  = vec3(0.541, 0.541, 0.580);
    vec3 grad1 = vec3(0.706, 0.310, 0.831);
    vec3 grad3 = vec3(0.420, 0.498, 0.831);
    vec3 cyan  = vec3(0.310, 0.765, 0.969);

    vec3 color = mix(grey, mix(grad1, grad3, 0.5), vCleared);

    if (uGateAmt > 0.001 && vCleared > 0.1) {
      // dist > 0: bar is ahead of scan (not yet reached), dist < 0: bar passed scan
      float d = vPosZ - uGateZ;
      vec3 gateColor = color;

      if (d > 8.0) {
        // Well ahead of scan: force grey
        gateColor = grey;
      } else if (d >= 0.0) {
        // Approaching -- grey flashing to cyan as gate closes in
        float t = 1.0 - d / 8.0;
        gateColor = mix(grey, cyan, t * t);
      } else if (d >= -12.0) {
        // Departing -- cyan to gradient with additive bloom
        float t = -d / 12.0;
        vec3 gradColor = mix(grad1, grad3, 0.5);
        gateColor = mix(cyan, gradColor, t) + (1.0 - t) * 0.45 * cyan;
      }
      // d < -12: already full gradient (base color above)

      color = mix(color, gateColor, uGateAmt);
    }

    float fog = clamp(exp(-0.006 * vFogDepth), 0.0, 1.0);
    color *= fog;
    gl_FragColor = vec4(color, 1.0);
  }
`;

// ---- Gate plane shaders ----

const GATE_PLANE_VERT = /* glsl */`
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const GATE_PLANE_FRAG = /* glsl */`
  precision mediump float;
  uniform float uTime;
  uniform float uOpacity;
  varying vec2 vUv;

  void main() {
    float dx   = abs(vUv.x - 0.5) * 2.0;
    float dy   = abs(vUv.y - 0.5) * 2.0;
    float core = pow(clamp(1.0 - max(dx, dy), 0.0, 1.0), 3.0);
    float scan = sin(vUv.y * 60.0 - uTime * 0.5) * 0.03 + 0.97;
    gl_FragColor = vec4(0.310, 0.765, 0.969, core * scan * uOpacity * 0.55);
  }
`;

// ---- Layout generators ----

function genNoise(count) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    pos[i*3]=(Math.random()-.5)*200; pos[i*3+1]=(Math.random()-.5)*60; pos[i*3+2]=(Math.random()-.5)*400;
    const w=.3+Math.random()*.3; scales[i*3]=w; scales[i*3+2]=w; scales[i*3+1]=.5+Math.random()*7.5;
  }
  return { pos, scales, cleared };
}

function genExpanse(count, seeds) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    pos[i*3]=(Math.random()-.5)*320; pos[i*3+1]=(Math.random()-.5)*90; pos[i*3+2]=(Math.random()-.5)*600;
    if (seeds[i] < .15) { scales[i*3]=scales[i*3+1]=scales[i*3+2]=0; }
    else { const w=.3+Math.random()*.3; scales[i*3]=w; scales[i*3+2]=w; scales[i*3+1]=.5+Math.random()*7.5; }
  }
  return { pos, scales, cleared };
}

function genGate(count, seeds) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    pos[i*3]=(Math.random()-.5)*80; pos[i*3+1]=(Math.random()-.5)*40; pos[i*3+2]=(Math.random()-.5)*300;
    if (seeds[i] > .25) {
      const w=.3+Math.random()*.2; scales[i*3]=w; scales[i*3+2]=w; scales[i*3+1]=1+Math.random()*5; cleared[i]=1;
    } else { scales[i*3]=scales[i*3+1]=scales[i*3+2]=0; }
  }
  return { pos, scales, cleared };
}

function genLattice(count) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count).fill(1);
  const nX=count<10000?60:100, nY=20, nZ=Math.ceil(count/(nX*nY));
  const sx=2, sy=2.2, sz=3, ox=(nX-1)*sx/2, oy=(nY-1)*sy/2, oz=(nZ-1)*sz/2;
  for (let i = 0; i < count; i++) {
    pos[i*3]=(i%nX)*sx-ox; pos[i*3+1]=(Math.floor(i/nX)%nY)*sy-oy; pos[i*3+2]=Math.floor(i/(nX*nY))*sz-oz;
    scales[i*3]=scales[i*3+2]=.4; scales[i*3+1]=1.5+Math.random()*2;
  }
  return { pos, scales, cleared };
}

function genStems(count, seeds) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count).fill(1);
  const zg = [-15,-5,5,15];
  for (let i = 0; i < count; i++) {
    const g=Math.floor(seeds[i]*4)%4;
    pos[i*3]=(Math.random()-.5)*8; pos[i*3+1]=(Math.random()-.5)*40; pos[i*3+2]=zg[g]+(Math.random()-.5)*3;
    scales[i*3]=scales[i*3+2]=.35; scales[i*3+1]=2+Math.random()*6;
  }
  return { pos, scales, cleared };
}

function genArc(count) {
  const pos = new Float32Array(count*3), scales = new Float32Array(count*3), cleared = new Float32Array(count).fill(1);
  for (let i = 0; i < count; i++) {
    const a=Math.PI*(i/count);
    pos[i*3]=Math.cos(a)*90+(Math.random()-.5)*6; pos[i*3+1]=Math.sin(a)*35-15+(Math.random()-.5)*6; pos[i*3+2]=(Math.random()-.5)*30;
    scales[i*3]=scales[i*3+2]=.3+Math.random()*.2; scales[i*3+1]=1+Math.random()*4;
  }
  return { pos, scales, cleared };
}

// Scroll segments: [fromActIdx, toActIdx, segStart, segEnd, useGateEasing]
const SEGS = [
  [0,0,0.00,0.10,false],
  [0,1,0.10,0.25,false],
  [1,1,0.25,0.35,false],
  [1,2,0.35,0.52,true ],
  [2,2,0.52,0.62,false],
  [2,3,0.62,0.72,false],
  [3,3,0.72,0.78,false],
  [3,4,0.78,0.87,false],
  [4,4,0.87,0.91,false],
  [4,5,0.91,1.00,false],
];

const _cp = new THREE.Vector3();
const _ct = new THREE.Vector3();

const camCurve = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0,  5, 120),
  new THREE.Vector3(0, 25, 200),
  new THREE.Vector3(0,  5,  80),
  new THREE.Vector3(50,20,  40),
  new THREE.Vector3(0,  5,  30),
  new THREE.Vector3(0, 40, 180),
]);
const tgtCurve = new THREE.CatmullRomCurve3([
  new THREE.Vector3(0, 0,   0),
  new THREE.Vector3(0, 0, -60),
  new THREE.Vector3(0, 0,   0),
  new THREE.Vector3(0, 5,   0),
  new THREE.Vector3(0, 0,   0),
  new THREE.Vector3(0, 0,   0),
]);

// ---- CameraRig ----

function CameraRig({ progressRef }) {
  useFrame(({ camera }) => {
    const p = Math.max(0, Math.min(1, progressRef.current));
    camCurve.getPointAt(p, _cp);
    tgtCurve.getPointAt(p, _ct);
    camera.position.copy(_cp);
    camera.lookAt(_ct);
  });
  return null;
}

// ---- Gate plane ----

function GatePlane({ progressRef }) {
  const meshRef = useRef();
  const mat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader:   GATE_PLANE_VERT,
    fragmentShader: GATE_PLANE_FRAG,
    uniforms: { uTime: { value: 0 }, uOpacity: { value: 0 } },
    transparent: true,
    depthWrite:  false,
    blending:    THREE.AdditiveBlending,
  }), []);

  useFrame(({ clock }) => {
    const p = Math.max(0, Math.min(1, progressRef.current));
    const { gateZ, gateAmt } = computeGateState(p);
    if (meshRef.current) meshRef.current.position.z = gateZ;
    mat.uniforms.uOpacity.value = gateAmt;
    mat.uniforms.uTime.value    = clock.getElapsedTime();
  });

  return (
    <mesh ref={meshRef} position={[0, 0, -200]}>
      <planeGeometry args={[300, 160]} />
      <primitive object={mat} attach="material" />
    </mesh>
  );
}

// ---- Bar field ----

function BarField({ count, progressRef }) {
  const prevSegRef = useRef(-1);

  const { layouts, geo, mat } = useMemo(() => {
    const seeds = new Float32Array(count);
    for (let i = 0; i < count; i++) seeds[i] = Math.random();

    const L = [
      genNoise(count),
      genExpanse(count, seeds),
      genGate(count, seeds),
      genLattice(count),
      genStems(count, seeds),
      genArc(count),
    ];

    const g = new THREE.BoxGeometry(1, 1, 1);
    g.setAttribute('aTargetA',  new THREE.InstancedBufferAttribute(L[0].pos.slice(),     3));
    g.setAttribute('aTargetB',  new THREE.InstancedBufferAttribute(L[0].pos.slice(),     3));
    g.setAttribute('aScaleA',   new THREE.InstancedBufferAttribute(L[0].scales.slice(),  3));
    g.setAttribute('aScaleB',   new THREE.InstancedBufferAttribute(L[0].scales.slice(),  3));
    g.setAttribute('aSeed',     new THREE.InstancedBufferAttribute(seeds,                1));
    g.setAttribute('aCleared',  new THREE.InstancedBufferAttribute(L[0].cleared.slice(), 1));
    g.setAttribute('aClearedB', new THREE.InstancedBufferAttribute(L[0].cleared.slice(), 1));

    const m = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms: {
        uProgress: { value: 0 },
        uGlobalP:  { value: 0 },
        uTime:     { value: 0 },
        uGateZ:    { value: -200 },
        uGateAmt:  { value: 0 },
      },
    });

    return { layouts: L, geo: g, mat: m };
  }, [count]);

  useFrame(({ clock }) => {
    const p = Math.max(0, Math.min(1, progressRef.current));

    let si = SEGS.length - 1;
    for (let i = 0; i < SEGS.length; i++) { if (p <= SEGS[i][3]) { si = i; break; } }

    if (si !== prevSegRef.current) {
      const [fa, ta] = SEGS[si];
      const setArr = (name, src) => { const a = geo.getAttribute(name); a.array.set(src); a.needsUpdate = true; };
      setArr('aTargetA',  layouts[fa].pos);
      setArr('aScaleA',   layouts[fa].scales);
      setArr('aCleared',  layouts[fa].cleared);
      setArr('aTargetB',  layouts[ta].pos);
      setArr('aScaleB',   layouts[ta].scales);
      setArr('aClearedB', layouts[ta].cleared);
      prevSegRef.current = si;
    }

    const [,,ss,se,ge] = SEGS[si];
    const span = se - ss;
    const raw  = span > 0 ? Math.max(0, Math.min(1, (p-ss)/span)) : 1;
    mat.uniforms.uProgress.value = ge ? p3out(raw) : p2in(raw);
    mat.uniforms.uGlobalP.value  = p;
    mat.uniforms.uTime.value     = clock.getElapsedTime();

    const { gateZ, gateAmt } = computeGateState(p);
    mat.uniforms.uGateZ.value   = gateZ;
    mat.uniforms.uGateAmt.value = gateAmt;
  });

  return <instancedMesh args={[geo, mat, count]} frustumCulled={false} />;
}

// ---- FPS guard ----

function FPSGuard({ onHalf, onHide }) {
  const t0    = useRef(null);
  const fc    = useRef(0);
  const phase = useRef(0); // 0 = initial, 1 = post-halve, 2 = done

  useFrame(({ clock }) => {
    if (phase.current === 2) return;
    const t = clock.getElapsedTime();
    if (t0.current === null) { t0.current = t; return; }
    fc.current++;
    if (t - t0.current < 2) return;

    const fps = fc.current / (t - t0.current);

    if (fps < 30) {
      if (phase.current === 0) {
        phase.current = 1;
        t0.current = t;
        fc.current = 0;
        onHalf();
      } else {
        phase.current = 2;
        onHide();
      }
    } else {
      phase.current = 2;
    }
  });
  return null;
}

// ---- Scene ----

export default function Scene() {
  const [halved,  setHalved]  = useState(false);
  const [visible, setVisible] = useState(true);
  const progressRef = useScrollProgress();
  const baseCount   = useMemo(() => window.innerWidth < 768 ? COUNT_MOBILE : COUNT_DESKTOP, []);
  const count = halved ? Math.floor(baseCount / 2) : baseCount;

  if (!visible) return null;

  return (
    <div aria-hidden="true" style={{ position: 'fixed', inset: 0, zIndex: 0, pointerEvents: 'none' }}>
      <Canvas
        camera={{ fov: 50, position: [0, 5, 120], near: 0.1, far: 2000 }}
        gl={{ antialias: false }}
        style={{ background: '#000000', width: '100%', height: '100%' }}
      >
        <CameraRig progressRef={progressRef} />
        <GatePlane progressRef={progressRef} />
        <BarField count={count} progressRef={progressRef} />
        <FPSGuard
          onHalf={() => setHalved(true)}
          onHide={() => setVisible(false)}
        />
      </Canvas>
    </div>
  );
}
