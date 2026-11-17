/** GLSL for the Signal particles and the ASCII post-process. Colors/levels come in as uniforms. */
export const particleVertex = /* glsl */ `
attribute vec3 aFrom;
attribute vec3 aTo;
attribute float aSeed;
uniform float uTime, uMorph, uMic, uOut, uSize, uPixelRatio;
uniform float uListen, uThink, uSpeak, uCalm, uErr;
uniform vec4 uBands;
uniform vec2 uPointer;
varying float vMix;
varying float vAlpha;

float hash(float n) { return fract(sin(n) * 43758.5453); }
float noise3(vec3 p) {
  return sin(p.x * 3.1 + uTime * 0.9) * sin(p.y * 3.7 + uTime * 1.1) * sin(p.z * 2.9 + uTime * 0.7);
}
mat2 rot(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }

void main() {
  float m = smoothstep(0.0, 1.0, uMorph);
  vec3 p = mix(aFrom, aTo, m);
  // during a morph particles bulge outward a little (Halovane-style transition)
  p *= 1.0 + sin(m * 3.14159) * 0.35 * (0.5 + aSeed);
  float n = noise3(p * 1.3 + aSeed);
  float speed = mix(1.0, 0.35, uCalm);

  // idle drift
  vec3 disp = p * n * 0.05;
  // listening: radial swell with mic level
  // (bounded so the swell never leaves the canvas: clipped particles showed as a hard square edge)
  disp += p * uListen * min(uMic, 1.0) * (0.35 + 0.65 * (0.5 + 0.5 * n)) * 0.22;
  // thinking: contract and twist into filaments
  vec3 q = p * (1.0 - 0.28 * uThink);
  q.xz = rot(uThink * (uTime * 1.6 * speed + q.y * 2.5)) * q.xz;
  // speaking: each particle follows one frequency band
  int bi = int(floor(aSeed * 3.999));
  float band = bi == 0 ? uBands.x : bi == 1 ? uBands.y : bi == 2 ? uBands.z : uBands.w;
  disp += p * uSpeak * (min(band, 1.0) * 0.18 + min(uOut, 1.0) * 0.07);
  // error: brief, small jitter (never alarming)
  disp += uErr * vec3(hash(aSeed + uTime) - 0.5, hash(aSeed * 2.0 + uTime) - 0.5, 0.0) * 0.06;

  vec3 pos = q + disp;
  // pointer field (visitor control)
  vec2 d = uPointer - pos.xy;
  pos.xy += d * 0.12 * exp(-dot(d, d) * 3.0);
  pos.xz = rot(uTime * 0.05 * speed) * pos.xz;

  vec4 mv = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mv;
  float energy = uListen * uMic + uSpeak * (band + uOut) * 0.5;
  gl_PointSize = uSize * uPixelRatio * (1.0 + min(energy, 1.0) * 0.6) * (1.0 / -mv.z) * (0.6 + aSeed * 0.8);
  vMix = clamp(0.5 + 0.5 * n + energy * 0.3, 0.0, 1.0);
  vAlpha = (0.35 + 0.65 * aSeed) * mix(1.0, 0.55, uCalm);
}
`;

export const particleFragment = /* glsl */ `
uniform vec3 uColorA, uColorB;
uniform float uCalm;
varying float vMix;
varying float vAlpha;
void main() {
  float d = length(gl_PointCoord - 0.5);
  float a = smoothstep(0.5, 0.0, d) * vAlpha;
  vec3 c = mix(uColorA, uColorB, vMix);
  float g = dot(c, vec3(0.299, 0.587, 0.114));
  c = mix(c, vec3(g), uCalm * 0.75);
  gl_FragColor = vec4(c * a, a);
}
`;

export const asciiVertex = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

/** Brightness-mapped glyph atlas lookup. Glyphs are Latin/symbols only. */
export const asciiFragment = /* glsl */ `
uniform sampler2D uScene, uAtlas;
uniform vec2 uResolution;
uniform float uCell, uGlyphs;
uniform vec3 uTint;
varying vec2 vUv;
void main() {
  vec2 cells = uResolution / uCell;
  vec2 cell = floor(vUv * cells);
  vec2 center = (cell + 0.5) / cells;
  vec3 col = texture2D(uScene, center).rgb;
  float lum = clamp(dot(col, vec3(0.299, 0.587, 0.114)) * 2.6, 0.0, 1.0);
  float idx = floor(lum * (uGlyphs - 1.0) + 0.5);
  vec2 inCell = fract(vUv * cells);
  vec2 auv = vec2((idx + inCell.x) / uGlyphs, inCell.y);
  float glyph = texture2D(uAtlas, auv).r;
  vec3 c = mix(uTint, col * 1.4 + uTint * 0.2, 0.55);
  gl_FragColor = vec4(c * glyph, glyph);  // transparent between glyphs: the console grid shows through
}
`;
