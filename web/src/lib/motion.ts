"use client";
import gsap from "gsap";
import { CustomEase } from "gsap/CustomEase";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { easePath, token } from "./tokens";

let ready = false;
/** Register GSAP plugins and the 3 token easings once ("enter", "exit", "emphasis"). */
export function setupMotion() {
  if (ready || typeof window === "undefined") return gsap;
  gsap.registerPlugin(CustomEase, ScrollTrigger);
  CustomEase.create("enter", easePath("enter"));
  CustomEase.create("exit", easePath("exit"));
  CustomEase.create("emphasis", easePath("emphasis"));
  gsap.defaults({ ease: "enter", duration: token.dur("base") });
  ready = true;
  return gsap;
}
export { gsap, ScrollTrigger };
