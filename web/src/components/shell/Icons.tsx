/** Line icons drawn for ShaOn (no icon library): 20px grid, 1.5px stroke, currentColor. Decorative: aria-hidden. */
type P = { size?: number; className?: string };
const S = ({ size = 20, className, children }: P & { children: React.ReactNode }) => (
  <svg width={size} height={size} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
    strokeLinejoin="round" aria-hidden="true" className={className}>{children}</svg>
);
export const IconHome = (p: P) => <S {...p}><circle cx="10" cy="10" r="3" /><circle cx="10" cy="10" r="7" strokeDasharray="2 2.4" /></S>;
export const IconCall = (p: P) => <S {...p}><path d="M3 10h1.5M6 6v8M9 3.5v13M12 6.5v7M15 8.5v3M17 10h0" /></S>;
export const IconStudio = (p: P) => <S {...p}><path d="M4 5h12M4 10h12M4 15h12" /><circle cx="7" cy="5" r="1.6" fill="var(--bg)" /><circle cx="13" cy="10" r="1.6" fill="var(--bg)" /><circle cx="9" cy="15" r="1.6" fill="var(--bg)" /></S>;
export const IconKnowledge = (p: P) => <S {...p}><circle cx="5" cy="5" r="1.8" /><circle cx="15" cy="6" r="1.8" /><circle cx="10" cy="15" r="1.8" /><path d="M6.6 5.3l6.6.6M6 6.5l3.2 6.8M14.2 7.6l-3.4 5.8" /></S>;
export const IconLogs = (p: P) => <S {...p}><rect x="3.5" y="3" width="13" height="14" rx="1.5" /><path d="M6.5 7h7M6.5 10h7M6.5 13h4" /></S>;
export const IconSettings = (p: P) => <S {...p}><path d="M10 2.8v2.4M10 14.8v2.4M2.8 10h2.4M14.8 10h2.4M4.9 4.9l1.7 1.7M13.4 13.4l1.7 1.7M4.9 15.1l1.7-1.7M13.4 6.6l1.7-1.7" /><circle cx="10" cy="10" r="3.2" /></S>;
export const IconKey = (p: P) => <S {...p}><circle cx="7" cy="10" r="3.2" /><path d="M10.2 10H17M14.5 10v2.6M16.5 10v1.8" /></S>;
export const IconChip = (p: P) => <S {...p}><rect x="5" y="5" width="10" height="10" rx="1.5" /><path d="M8 2.5v2.5M12 2.5v2.5M8 15v2.5M12 15v2.5M2.5 8H5M2.5 12H5M15 8h2.5M15 12h2.5" /></S>;
export const IconMic = (p: P) => <S {...p}><rect x="7.5" y="2.8" width="5" height="9" rx="2.5" /><path d="M4.8 9.5a5.2 5.2 0 0010.4 0M10 14.7V17" /></S>;
export const IconStop = (p: P) => <S {...p}><rect x="5.5" y="5.5" width="9" height="9" rx="1" /></S>;
export const IconArrow = (p: P) => <S {...p}><path d="M4 10h12M11.5 5.5L16 10l-4.5 4.5" /></S>;
export const IconEye = (p: P) => <S {...p}><path d="M2.5 10s2.7-5 7.5-5 7.5 5 7.5 5-2.7 5-7.5 5-7.5-5-7.5-5z" /><circle cx="10" cy="10" r="2.3" /></S>;
export const IconRefresh = (p: P) => <S {...p}><path d="M16 6.5A6.5 6.5 0 104.3 13M16 3v3.5h-3.5" /></S>;
