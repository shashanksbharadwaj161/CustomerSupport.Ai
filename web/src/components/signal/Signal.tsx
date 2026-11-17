"use client";
/**
 * "The Signal" (DESIGN.md section 6): voice-reactive particle field.
 * States: idle, listening, thinking, speaking, switch, handoff, error.
 * Inputs: mic level, playback level + 4 bands (levelsRef, read every frame without React renders),
 * current language (hue + motif), state, pointer.
 * Tiers: full = always-on frame loop, high DPR, many particles; lite = 30 fps cap, DPR 1,
 * fewer particles; off / reduced motion = static CSS orb. Paused when the tab is hidden.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useEffectsTier } from "@/lib/effects";
import { gsap, setupMotion } from "@/lib/motion";
import { token, type Lang } from "@/lib/tokens";
import { motifPositions, type Motif } from "./motifs";
import { asciiFragment, asciiVertex, particleFragment, particleVertex } from "./shaders";
import { StaticSignal } from "./StaticSignal";

export type SignalState = "idle" | "listening" | "thinking" | "speaking" | "switch" | "handoff" | "error";
export type Levels = { mic: number; out: number; bands: [number, number, number, number] };
export const emptyLevels = (): Levels => ({ mic: 0, out: 0, bands: [0, 0, 0, 0] });
/** Visitor control (drag / keys on SignalStage): rotation in radians, zoom factor. Read every frame, no re-render. */
export type Control = { yaw: number; pitch: number; zoom: number };
export const emptyControl = (): Control => ({ yaw: 0, pitch: 0, zoom: 1 });

type Props = {
  state: SignalState;
  lang: Lang;
  levelsRef?: React.RefObject<Levels>;
  motif?: Motif;           // overrides the language motif (e.g. "word" for the landing wordmark)
  ascii?: boolean;         // GPU ASCII post-process (landing hero)
  className?: string;
  label?: string;
  controlRef?: React.RefObject<Control>;
};

export function Signal(props: Props) {
  const { tier, hidden, software, generating } = useEffectsTier();
  // measured: with CPU-rendered WebGL the Lite orb added ~1.4 s to first audio on a 4-core PC (5.3 s vs 3.7-4.0 s with
  // effects off). While the models generate on such a machine the orb drops to 8 fps (unless Full was chosen).
  const liteFps = software && generating ? token.num("signal-fps-cpu-busy", 8) : token.num("signal-fps-lite", 30);
  if (tier === "off") return <StaticSignal state={props.state} lang={props.lang} className={props.className} />;
  const dpr = tier === "full" ? token.num("signal-dpr-full", 2) : token.num("signal-dpr-lite", 1);
  return (
    <div className={props.className} aria-hidden="true" data-testid="signal" data-state={props.state} data-tier={tier}>
      <Canvas
        dpr={[1, dpr]}
        frameloop={hidden ? "never" : tier === "full" ? "always" : "demand"}
        camera={{ position: [0, 0, 3.2], fov: 45 }}
        gl={{ antialias: false, alpha: true, powerPreference: "high-performance" }}
      >
        {tier === "lite" && !hidden && <FrameCap fps={liteFps} />}
        <Particles {...props} count={tier === "full" ? token.num("signal-particles-full", 14000) : token.num("signal-particles-lite", 3500)} />
        {props.ascii && <AsciiPass lang={props.lang} cell={tier === "full" ? 9 : 12} />}
      </Canvas>
    </div>
  );
}

function FrameCap({ fps }: { fps: number }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const id = window.setInterval(() => invalidate(), 1000 / fps);
    return () => window.clearInterval(id);
  }, [fps, invalidate]);
  return null;
}

const STATE_WEIGHTS: Record<SignalState, { listen: number; think: number; speak: number; calm: number; err: number }> = {
  idle: { listen: 0, think: 0, speak: 0, calm: 0, err: 0 },
  listening: { listen: 1, think: 0, speak: 0, calm: 0, err: 0 },
  thinking: { listen: 0, think: 1, speak: 0, calm: 0, err: 0 },
  speaking: { listen: 0, think: 0, speak: 1, calm: 0, err: 0 },
  switch: { listen: 0, think: 0.3, speak: 0, calm: 0, err: 0 },
  handoff: { listen: 0, think: 0, speak: 0, calm: 1, err: 0 },
  error: { listen: 0, think: 0, speak: 0, calm: 0.3, err: 1 },
};

function Particles({ state, lang, levelsRef, motif, count, controlRef }: Props & { count: number }) {
  const points = useRef<THREE.Points>(null);
  const camera = useThree((s) => s.camera);
  setupMotion();
  const target = motif ?? lang;
  const { geometry, uniforms } = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const start = motifPositions(target, count);
    const seeds = new Float32Array(count);
    for (let i = 0; i < count; i++) { const x = Math.sin(i * 12.9898) * 43758.5453; seeds[i] = x - Math.floor(x); }
    g.setAttribute("position", new THREE.BufferAttribute(start.slice(), 3));
    g.setAttribute("aFrom", new THREE.BufferAttribute(start.slice(), 3));
    g.setAttribute("aTo", new THREE.BufferAttribute(start, 3));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));
    const u = {
      uTime: { value: 0 }, uMorph: { value: 1 }, uMic: { value: 0 }, uOut: { value: 0 },
      uSize: { value: 26 }, uPixelRatio: { value: 1 }, uBands: { value: new THREE.Vector4() },
      uPointer: { value: new THREE.Vector2(9, 9) },
      uListen: { value: 0 }, uThink: { value: 0 }, uSpeak: { value: 0 }, uCalm: { value: 0 }, uErr: { value: 0 },
      uColorA: { value: new THREE.Color(token.langColor(lang) || "#7cc7ff") },
      uColorB: { value: new THREE.Color(token.color("signal-alt") || "#8a7dff") },
    };
    return { geometry: g, uniforms: u };
    // geometry is rebuilt only when the particle budget changes (tier switch)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);
  const material = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: particleVertex, fragmentShader: particleFragment, uniforms,
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  }), [uniforms]);
  const gl = useThree((s) => s.gl);
  const invalidate = useThree((s) => s.invalidate);

  useEffect(() => () => { geometry.dispose(); material.dispose(); }, [geometry, material]);

  // morph to the new motif (language switch / wordmark)
  const current = useRef<Motif>(target);
  useEffect(() => {
    if (current.current === target) return;
    const from = geometry.getAttribute("aFrom") as THREE.BufferAttribute;
    const to = geometry.getAttribute("aTo") as THREE.BufferAttribute;
    const m = uniforms.uMorph.value;
    for (let i = 0; i < from.array.length; i++) (from.array as Float32Array)[i] = (from.array as Float32Array)[i] * (1 - m) + (to.array as Float32Array)[i] * m;
    (to.array as Float32Array).set(motifPositions(target, count));
    from.needsUpdate = to.needsUpdate = true;
    current.current = target;
    uniforms.uMorph.value = 0;
    gsap.to(uniforms.uMorph, { value: 1, duration: token.dur("slow") * 1.4, ease: "emphasis", onUpdate: invalidate });
  }, [target, count, geometry, uniforms, invalidate]);

  // language hue
  useEffect(() => {
    const c = new THREE.Color(token.langColor(lang) || "#7cc7ff");
    gsap.to(uniforms.uColorA.value, { r: c.r, g: c.g, b: c.b, duration: token.dur("slow"), onUpdate: invalidate });
  }, [lang, uniforms, invalidate]);

  // state weights
  useEffect(() => {
    const w = STATE_WEIGHTS[state];
    const d = token.dur("base");
    gsap.to(uniforms.uListen, { value: w.listen, duration: d });
    gsap.to(uniforms.uThink, { value: w.think, duration: d });
    gsap.to(uniforms.uSpeak, { value: w.speak, duration: d });
    gsap.to(uniforms.uCalm, { value: w.calm, duration: token.dur("slow") });
    gsap.to(uniforms.uErr, { value: w.err, duration: token.dur("fast") });
    if (state === "error") gsap.to(uniforms.uErr, { value: 0, delay: token.dur("slow"), duration: token.dur("base") });
  }, [state, uniforms]);

  useFrame((s, delta) => {
    uniforms.uTime.value += Math.min(delta, 0.05);
    uniforms.uPixelRatio.value = gl.getPixelRatio();
    const L = levelsRef?.current;
    const k = 0.25; // smoothing
    uniforms.uMic.value += ((L?.mic ?? 0) - uniforms.uMic.value) * k;
    uniforms.uOut.value += ((L?.out ?? 0) - uniforms.uOut.value) * k;
    const b = uniforms.uBands.value, nb = L?.bands ?? [0, 0, 0, 0];
    b.set(b.x + (nb[0] - b.x) * k, b.y + (nb[1] - b.y) * k, b.z + (nb[2] - b.z) * k, b.w + (nb[3] - b.w) * k);
    const pv = uniforms.uPointer.value;
    pv.set(s.pointer.x * 1.6, s.pointer.y * 1.0);
    const c = controlRef?.current;
    if (c && points.current) {  // eased toward the visitor's drag / keyboard target
      points.current.rotation.y += (c.yaw - points.current.rotation.y) * 0.18;
      points.current.rotation.x += (c.pitch - points.current.rotation.x) * 0.18;
      const z = 3.2 / Math.max(0.6, Math.min(1.6, c.zoom));
      camera.position.z += (z - camera.position.z) * 0.18;
    }
  });

  return <points ref={points} geometry={geometry} material={material} frustumCulled={false} />;
}

/** GPU ASCII post-process: scene -> render target -> brightness-mapped glyph atlas. */
function AsciiPass({ lang, cell }: { lang: Lang; cell: number }) {
  const { gl, scene, camera, size } = useThree();
  const glyphs = " .:-=+*#%@";
  const res = useMemo(() => {
    const rt = new THREE.WebGLRenderTarget(1, 1);
    const c = document.createElement("canvas");
    const G = 64;
    c.width = G * glyphs.length; c.height = G;
    const g = c.getContext("2d")!;
    g.fillStyle = "#000"; g.fillRect(0, 0, c.width, c.height);
    g.fillStyle = "#fff"; g.font = `${G * 0.9}px 'JetBrains Mono', monospace`; g.textAlign = "center"; g.textBaseline = "middle";
    [...glyphs].forEach((ch, i) => g.fillText(ch, i * G + G / 2, G / 2));
    const atlas = new THREE.CanvasTexture(c);
    atlas.minFilter = THREE.LinearFilter;
    const mat = new THREE.ShaderMaterial({
      vertexShader: asciiVertex, fragmentShader: asciiFragment, depthTest: false,
      uniforms: {
        uScene: { value: rt.texture }, uAtlas: { value: atlas }, uResolution: { value: new THREE.Vector2(1, 1) },
        uCell: { value: cell }, uGlyphs: { value: glyphs.length },
        uTint: { value: new THREE.Color(token.langColor(lang) || "#7cc7ff") },
      },
    });
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
    const qScene = new THREE.Scene(); qScene.add(quad);
    const qCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    return { rt, atlas, mat, qScene, qCam };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    const pr = gl.getPixelRatio();
    res.rt.setSize(Math.max(1, size.width * pr), Math.max(1, size.height * pr));
    res.mat.uniforms.uResolution.value.set(size.width * pr, size.height * pr);
    res.mat.uniforms.uCell.value = cell * pr;
  }, [size, gl, res, cell]);
  useEffect(() => {
    const c = new THREE.Color(token.langColor(lang) || "#7cc7ff");
    gsap.to(res.mat.uniforms.uTint.value, { r: c.r, g: c.g, b: c.b, duration: token.dur("slow") });
  }, [lang, res]);
  useEffect(() => () => { res.rt.dispose(); res.atlas.dispose(); res.mat.dispose(); }, [res]);
  useFrame(() => {
    gl.setRenderTarget(res.rt);
    gl.render(scene, camera);
    gl.setRenderTarget(null);
    gl.render(res.qScene, res.qCam);
  }, 1);
  return null;
}
