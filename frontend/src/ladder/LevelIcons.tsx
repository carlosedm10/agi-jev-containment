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
  if (n === 2) return <WatchIcon color={color} />;
  if (n === 3) return <TagIcon color={color} />;
  if (n === 4) return <FreezeIcon color={color} />;
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

function TagIcon({ color }: IconProps) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M6.5 14.2 14.2 6.5h9.3v9.3L15.8 25.5 6.5 16.2z"
        fill="none"
        stroke={color}
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="20.2" cy="11.8" r="1.6" fill={color} />
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
