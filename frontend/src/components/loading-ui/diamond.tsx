/**
 * Diamond loader from loading-ui.com, vendored via its shadcn registry entry
 * (https://loading-ui.com/r/diamond.json).
 *
 * Eight pixels around a diamond path, each fading in sequence. Colour is inherited
 * through `currentColor`, so set it with a text utility on the parent.
 *
 * Changed from the published source: the animation is disabled under
 * prefers-reduced-motion, where an endless pulse is exactly what a person with
 * vestibular sensitivity asked the OS to stop.
 */
function Diamond(props: React.ComponentProps<"svg">) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="currentColor"
      role="status"
      aria-label="Loading"
      {...props}
    >
      <style>
        {`
          @keyframes loading-ui-diamond {
            0% { opacity: 0; }
            1% { opacity: 1; }
            100% { opacity: 0; }
          }
          .loading-ui-diamond rect {
            animation: loading-ui-diamond 0.8s ease-in-out infinite;
          }
          .loading-ui-diamond rect:nth-of-type(1) { animation-delay: 0s; }
          .loading-ui-diamond rect:nth-of-type(2) { animation-delay: 0.1s; }
          .loading-ui-diamond rect:nth-of-type(3) { animation-delay: 0.2s; }
          .loading-ui-diamond rect:nth-of-type(4) { animation-delay: 0.3s; }
          .loading-ui-diamond rect:nth-of-type(5) { animation-delay: 0.4s; }
          .loading-ui-diamond rect:nth-of-type(6) { animation-delay: 0.5s; }
          .loading-ui-diamond rect:nth-of-type(7) { animation-delay: 0.6s; }
          .loading-ui-diamond rect:nth-of-type(8) { animation-delay: 0.7s; }
          @media (prefers-reduced-motion: reduce) {
            .loading-ui-diamond rect { animation: none; opacity: 0.45; }
          }
        `}
      </style>
      <g className="loading-ui-diamond">
        {/* Top */}
        <rect x="8" y="0" width="4" height="4" />
        {/* Top Right */}
        <rect x="12" y="4" width="4" height="4" />
        {/* Right */}
        <rect x="16" y="8" width="4" height="4" />
        {/* Bottom Right */}
        <rect x="12" y="12" width="4" height="4" />
        {/* Bottom */}
        <rect x="8" y="16" width="4" height="4" />
        {/* Bottom Left */}
        <rect x="4" y="12" width="4" height="4" />
        {/* Left */}
        <rect x="0" y="8" width="4" height="4" />
        {/* Top Left */}
        <rect x="4" y="4" width="4" height="4" />
      </g>
    </svg>
  );
}

export { Diamond };
