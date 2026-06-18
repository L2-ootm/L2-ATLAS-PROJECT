# Fluid Glass

Source URLs:
- Page: https://reactbits.dev/components/fluid-glass
- Component: https://raw.githubusercontent.com/DavidHDev/react-bits/main/src/content/Components/FluidGlass/FluidGlass.jsx

## Category

Components. A real-time 3D glass element (lens / bar / cube) that floats over a scrollable WebGL scene of images and 3D text, refracting and chromatically distorting whatever is behind it as it follows the pointer — a "liquid glass" magnifier over the page content.

## Dependencies

Heavy WebGL stack:
- `three` (Three.js core).
- `@react-three/fiber` — React renderer for Three.js (`Canvas`, `useFrame`, `useThree`, `createPortal`).
- `@react-three/drei` — helpers: `useFBO` (render-to-texture), `useGLTF` (loads the glass mesh `.glb`), `ScrollControls`/`Scroll`/`useScroll`, `Image`, `Preload`, `MeshTransmissionMaterial` (the glass refraction material), `Text` (3D SDF text).
- `maath` — `easing.damp3` for smooth pointer follow.
- External assets required at runtime: GLB meshes `/assets/3d/lens.glb`, `/assets/3d/cube.glb`, `/assets/3d/bar.glb` (geometry keys `Cylinder` / `Cube` / `Cube`) and demo images under `/assets/demo/`.

The refraction is NOT a hand-written GLSL string here — it is provided by drei's `MeshTransmissionMaterial` (which internally compiles a transmission/refraction shader). The "shader" surface is configured via material props: `ior`, `thickness`, `anisotropy`, `chromaticAberration`, plus (bar mode) `transmission`, `roughness`, `attenuationColor`, `attenuationDistance`. The geometry comes from the loaded GLB, not from inline buffer geometry.

## Source

### FluidGlass.jsx

```jsx
/* eslint-disable react/no-unknown-property */
import * as THREE from 'three';
import { useRef, useState, useEffect, memo } from 'react';
import { Canvas, createPortal, useFrame, useThree } from '@react-three/fiber';
import {
  useFBO,
  useGLTF,
  useScroll,
  Image,
  Scroll,
  Preload,
  ScrollControls,
  MeshTransmissionMaterial,
  Text
} from '@react-three/drei';
import { easing } from 'maath';

export default function FluidGlass({ mode = 'lens', lensProps = {}, barProps = {}, cubeProps = {} }) {
  const Wrapper = mode === 'bar' ? Bar : mode === 'cube' ? Cube : Lens;
  const rawOverrides = mode === 'bar' ? barProps : mode === 'cube' ? cubeProps : lensProps;

  const {
    navItems = [
      { label: 'Home', link: '' },
      { label: 'About', link: '' },
      { label: 'Contact', link: '' }
    ],
    ...modeProps
  } = rawOverrides;

  return (
    <Canvas camera={{ position: [0, 0, 20], fov: 15 }} gl={{ alpha: true }}>
      <ScrollControls damping={0.2} pages={3} distance={0.4}>
        {mode === 'bar' && <NavItems items={navItems} />}
        <Wrapper modeProps={modeProps}>
          <Scroll>
            <Typography />
            <Images />
          </Scroll>
          <Scroll html />
          <Preload />
        </Wrapper>
      </ScrollControls>
    </Canvas>
  );
}

const ModeWrapper = memo(function ModeWrapper({
  children,
  glb,
  geometryKey,
  lockToBottom = false,
  followPointer = true,
  modeProps = {},
  ...props
}) {
  const ref = useRef();
  const { nodes } = useGLTF(glb);
  const buffer = useFBO();
  const { viewport: vp } = useThree();
  const [scene] = useState(() => new THREE.Scene());
  const geoWidthRef = useRef(1);

  useEffect(() => {
    const geo = nodes[geometryKey]?.geometry;
    geo.computeBoundingBox();
    geoWidthRef.current = geo.boundingBox.max.x - geo.boundingBox.min.x || 1;
  }, [nodes, geometryKey]);

  useFrame((state, delta) => {
    const { gl, viewport, pointer, camera } = state;
    const v = viewport.getCurrentViewport(camera, [0, 0, 15]);

    const destX = followPointer ? (pointer.x * v.width) / 2 : 0;
    const destY = lockToBottom ? -v.height / 2 + 0.2 : followPointer ? (pointer.y * v.height) / 2 : 0;
    easing.damp3(ref.current.position, [destX, destY, 15], 0.15, delta);

    if (modeProps.scale == null) {
      const maxWorld = v.width * 0.9;
      const desired = maxWorld / geoWidthRef.current;
      ref.current.scale.setScalar(Math.min(0.15, desired));
    }

    gl.setRenderTarget(buffer);
    gl.render(scene, camera);
    gl.setRenderTarget(null);

    // Background Color
    gl.setClearColor(0x5227ff, 1);
  });

  const { scale, ior, thickness, anisotropy, chromaticAberration, ...extraMat } = modeProps;

  return (
    <>
      {createPortal(children, scene)}
      <mesh scale={[vp.width, vp.height, 1]}>
        <planeGeometry />
        <meshBasicMaterial map={buffer.texture} transparent />
      </mesh>
      <mesh ref={ref} scale={scale ?? 0.15} rotation-x={Math.PI / 2} geometry={nodes[geometryKey]?.geometry} {...props}>
        <MeshTransmissionMaterial
          buffer={buffer.texture}
          ior={ior ?? 1.15}
          thickness={thickness ?? 5}
          anisotropy={anisotropy ?? 0.01}
          chromaticAberration={chromaticAberration ?? 0.1}
          {...extraMat}
        />
      </mesh>
    </>
  );
});

function Lens({ modeProps, ...p }) {
  return <ModeWrapper glb="/assets/3d/lens.glb" geometryKey="Cylinder" followPointer modeProps={modeProps} {...p} />;
}

function Cube({ modeProps, ...p }) {
  return <ModeWrapper glb="/assets/3d/cube.glb" geometryKey="Cube" followPointer modeProps={modeProps} {...p} />;
}

function Bar({ modeProps = {}, ...p }) {
  const defaultMat = {
    transmission: 1,
    roughness: 0,
    thickness: 10,
    ior: 1.15,
    color: '#ffffff',
    attenuationColor: '#ffffff',
    attenuationDistance: 0.25
  };

  return (
    <ModeWrapper
      glb="/assets/3d/bar.glb"
      geometryKey="Cube"
      lockToBottom
      followPointer={false}
      modeProps={{ ...defaultMat, ...modeProps }}
      {...p}
    />
  );
}

function NavItems({ items }) {
  const group = useRef();
  const { viewport, camera } = useThree();

  const DEVICE = {
    mobile: { max: 639, spacing: 0.2, fontSize: 0.035 },
    tablet: { max: 1023, spacing: 0.24, fontSize: 0.035 },
    desktop: { max: Infinity, spacing: 0.3, fontSize: 0.035 }
  };
  const getDevice = () => {
    const w = window.innerWidth;
    return w <= DEVICE.mobile.max ? 'mobile' : w <= DEVICE.tablet.max ? 'tablet' : 'desktop';
  };

  const [device, setDevice] = useState(getDevice());

  useEffect(() => {
    const onResize = () => setDevice(getDevice());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { spacing, fontSize } = DEVICE[device];

  useFrame(() => {
    if (!group.current) return;
    const v = viewport.getCurrentViewport(camera, [0, 0, 15]);
    group.current.position.set(0, -v.height / 2 + 0.2, 15.1);

    group.current.children.forEach((child, i) => {
      child.position.x = (i - (items.length - 1) / 2) * spacing;
    });
  });

  const handleNavigate = link => {
    if (!link) return;
    link.startsWith('#') ? (window.location.hash = link) : (window.location.href = link);
  };

  return (
    <group ref={group} renderOrder={10}>
      {items.map(({ label, link }) => (
        <Text
          key={label}
          fontSize={fontSize}
          color="white"
          anchorX="center"
          anchorY="middle"
          depthWrite={false}
          outlineWidth={0}
          outlineBlur="20%"
          outlineColor="#000"
          outlineOpacity={0.5}
          depthTest={false}
          renderOrder={10}
          onClick={e => {
            e.stopPropagation();
            handleNavigate(link);
          }}
          onPointerOver={() => (document.body.style.cursor = 'pointer')}
          onPointerOut={() => (document.body.style.cursor = 'auto')}
        >
          {label}
        </Text>
      ))}
    </group>
  );
}

function Images() {
  const group = useRef();
  const data = useScroll();
  const { height } = useThree(s => s.viewport);

  useFrame(() => {
    group.current.children[0].material.zoom = 1 + data.range(0, 1 / 3) / 3;
    group.current.children[1].material.zoom = 1 + data.range(0, 1 / 3) / 3;
    group.current.children[2].material.zoom = 1 + data.range(1.15 / 3, 1 / 3) / 2;
    group.current.children[3].material.zoom = 1 + data.range(1.15 / 3, 1 / 3) / 2;
    group.current.children[4].material.zoom = 1 + data.range(1.15 / 3, 1 / 3) / 2;
  });

  return (
    <group ref={group}>
      <Image position={[-2, 0, 0]} scale={[3, height / 1.1, 1]} url="/assets/demo/cs1.webp" />
      <Image position={[2, 0, 3]} scale={3} url="/assets/demo/cs2.webp" />
      <Image position={[-2.05, -height, 6]} scale={[1, 3, 1]} url="/assets/demo/cs3.webp" />
      <Image position={[-0.6, -height, 9]} scale={[1, 2, 1]} url="/assets/demo/cs1.webp" />
      <Image position={[0.75, -height, 10.5]} scale={1.5} url="/assets/demo/cs2.webp" />
    </group>
  );
}

function Typography() {
  const DEVICE = {
    mobile: { fontSize: 0.2 },
    tablet: { fontSize: 0.4 },
    desktop: { fontSize: 0.6 }
  };
  const getDevice = () => {
    const w = window.innerWidth;
    return w <= 639 ? 'mobile' : w <= 1023 ? 'tablet' : 'desktop';
  };

  const [device, setDevice] = useState(getDevice());

  useEffect(() => {
    const onResize = () => setDevice(getDevice());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const { fontSize } = DEVICE[device];

  return (
    <Text
      position={[0, 0, 12]}
      fontSize={fontSize}
      letterSpacing={-0.05}
      outlineWidth={0}
      outlineBlur="20%"
      outlineColor="#000"
      outlineOpacity={0.5}
      color="white"
      anchorX="center"
      anchorY="middle"
    >
      React Bits
    </Text>
  );
}
```

> Shader note: The glass refraction/chromatic-aberration shader is NOT inlined in this file. It is supplied by `@react-three/drei`'s `<MeshTransmissionMaterial>`, which compiles its own GLSL transmission shader internally (a thickness/IOR-based refraction with a per-channel `chromaticAberration` offset and an FBO `buffer` texture as the "behind" sample). To capture the raw GLSL you would read drei's `MeshTransmissionMaterial` source (`@react-three/drei/materials/MeshTransmissionMaterial`). The geometry is loaded from external `.glb` files (`lens.glb`/`cube.glb`/`bar.glb`), not authored inline.

## Technique

A full-viewport `<Canvas>` hosts a `ScrollControls` scene (3 pages). The scrollable content (3D `Text` headline plus five `Image` planes that zoom on scroll) is rendered into an off-screen `THREE.Scene` and captured each frame to an FBO render target via `useFBO`. `ModeWrapper` then draws two meshes: a fullscreen plane that simply displays the FBO texture (so the page content is visible), and the glass mesh (geometry from the loaded GLB), whose `MeshTransmissionMaterial` is fed the same FBO texture as its `buffer` — letting the transmission shader refract and chromatically split the rendered content behind it. Each frame, `easing.damp3` smoothly eases the glass mesh toward the pointer position (`followPointer`) or pins it to the bottom (`lockToBottom`, used by the `bar` mode nav), and auto-scales the mesh relative to viewport width using the GLB's measured bounding-box width. `mode` selects lens (cylinder, follows pointer), cube, or bar (fixed bottom bar with floating `Text` nav links). Material look is tuned via `ior` (~1.15), `thickness`, `anisotropy`, and `chromaticAberration` (~0.1).

## Svelte 5 port note

This is the only effect of the five that needs real 3D. Two reimplementation paths for Svelte 5 + Tailwind v4 + dark theme:

Option A — true WebGL with Three.js (closest fidelity). There is no Svelte equivalent of react-three-fiber's component tree that ships `MeshTransmissionMaterial` out of the box, so the pragmatic route is to use `three` directly in `onMount` (or an `$effect`): create a `WebGLRenderer`, a `Scene`, an orthographic/perspective camera, render the page-content scene to a `WebGLRenderTarget` (the manual equivalent of `useFBO`), load the glass GLB with `GLTFLoader`, and assign a transmission material. drei's `MeshTransmissionMaterial` is itself a port of `THREE.MeshPhysicalMaterial` with `transmission`/`thickness`/`ior` plus an injected chromatic-aberration `onBeforeCompile` patch — you can either (a) port that material file's GLSL injection into a `MeshPhysicalMaterial.onBeforeCompile` in plain three, or (b) use `MeshPhysicalMaterial` with `transmission: 1`, `ior: 1.15`, `thickness`, `roughness: 0` and accept no chromatic aberration. Drive the pointer-follow with a manual `damp`/lerp in a `requestAnimationFrame` loop, and replace `ScrollControls` with a scroll listener mapping `scrollTop` to camera/group Y. (`threlte` is the Svelte-native r3f analog if you want a declarative tree, but it does not provide a drop-in transmission material either.) Heaviest option; only worth it if the literal liquid-glass look is required.

Option B — CSS/SVG approximation (no WebGL, recommended default for a cockpit). Render a glass panel with `backdrop-filter: blur(...) saturate(...)` plus a subtle border/inner highlight, and add liquid refraction via an SVG `<filter>` using `feTurbulence` + `feDisplacementMap` applied to the backdrop (the well-known "liquid glass / Apple glass" CSS trick). For chromatic fringing, layer two faint offset copies tinted with `mix-blend-mode`. Animate the displacement (`feTurbulence` `baseFrequency` or a moving `feOffset`) and translate the panel toward the pointer in an `$effect`/RAF for the follow behavior. This gives ~80% of the visual at a fraction of the cost, integrates with the dark ATLAS theme trivially, and needs zero 3D assets. Use Option B for the cockpit unless a hero moment specifically calls for true refraction.

Either way: gate the animation on `prefers-reduced-motion`, and note the React version depends on external `.glb` and `.webp` assets that would need to be re-supplied (Option A) or dropped (Option B).
