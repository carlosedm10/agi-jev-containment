import type { Level } from "./types";

type IconProps = {
  color?: string;
};

export function LevelIcon({
  n,
  color = "currentColor",
}: {
  n: Exclude<Level, 0>;
  color?: string;
}) {
  if (n === 1) return <WatchIcon color={color} />;
  if (n === 2) return <SupervisorIcon color={color} />;
  if (n === 3) return <FreezeIcon color={color} />;
  if (n === 4) return <CutIcon color={color} />;
  return <PlugIcon color={color} />;
}

function WatchIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M3.5 16s5.4-8 12.5-8 12.5 8 12.5 8-5.4 8-12.5 8S3.5 16 3.5 16z"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="16" r="3.4" fill={color} />
    </svg>
  );
}

function SupervisorIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M6 13h6.2v8.5H6zM19.8 13H26v8.5h-6.2z"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M12.2 15.2h7.6M12.2 19.8h7.6"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="9.1" cy="17.2" r="1.7" fill={color} />
      <circle cx="22.9" cy="17.2" r="1.7" fill={color} />
    </svg>
  );
}

function FreezeIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <rect x="9" y="7" width="5" height="18" rx="1.2" fill={color} />
      <rect x="18" y="7" width="5" height="18" rx="1.2" fill={color} />
    </svg>
  );
}

function CutIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <circle
        cx="16"
        cy="16"
        r="10"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
      />
      <path
        d="M16 6.2v3.4M16 22.4v3.4M6.2 16h3.4M22.4 16h3.4"
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <ellipse
        cx="16"
        cy="16"
        rx="4.2"
        ry="10"
        fill="none"
        stroke={color}
        strokeWidth="1.6"
      />
      <path
        d="M7 25 L25 7"
        fill="none"
        stroke={color}
        strokeWidth="2.1"
        strokeLinecap="round"
      />
    </svg>
  );
}

function PlugIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M8 11.5h7.5v9H8z"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M11 11.5V8M15.5 11.5V8M15.5 16H26"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function RingingPhone() {
  return (
    <svg className="phone-glyph" viewBox="0 0 48 48" aria-hidden="true">
      <circle className="phone-wave" cx="24" cy="24" r="16" />
      <circle className="phone-wave phone-wave-late" cx="24" cy="24" r="16" />
      <path
        className="phone-handset"
        d="M18.2 14.4c2.4-2.5 6.4-2.6 8.8-.2l1.8 1.8-3.4 3.3c-1.1.2-2.6.8-3.6 1.8s-1.6 2.5-1.8 3.6l-3.3 3.4-1.8-1.8c-2.4-2.4-2.3-6.4.2-8.8z"
      />
    </svg>
  );
}
