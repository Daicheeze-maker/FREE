import type { Product, Seller } from "../lib/api";

/*
 * Art-directed bottle "photography": each house has its own glass silhouette, each scent its own juice colour.
 * Rendered as SVG so the demo needs no external image hosting.
 * shortcut: illustrations stand in for product photos; drop real photos into /public and swap this component.
 */

type Scene = "studio" | "noir" | "detail";

const SHAPES: Record<Seller["bottle"], { body: string; liquid: string; neck: [number, number, number, number]; cap: string }> = {
  // heavy square block
  block: {
    body: "M60 120 h80 a6 6 0 0 1 6 6 v124 a6 6 0 0 1 -6 6 h-80 a6 6 0 0 1 -6 -6 v-124 a6 6 0 0 1 6 -6z",
    liquid: "M62 150 h76 v98 a4 4 0 0 1 -4 4 h-68 a4 4 0 0 1 -4 -4z",
    neck: [88, 104, 24, 16],
    cap: "M78 62 h44 v42 h-44z",
  },
  // rounded dome
  dome: {
    body: "M100 112 c44 0 58 40 58 82 c0 40 -18 62 -58 62 c-40 0 -58 -22 -58 -62 c0 -42 14 -82 58 -82z",
    liquid: "M46 176 h108 c2 8 2 12 2 18 c0 36 -16 58 -56 58 c-40 0 -56 -22 -56 -58 c0 -6 0 -10 2 -18z",
    neck: [90, 96, 20, 18],
    cap: "M100 46 c16 0 24 12 24 26 c0 14 -8 24 -24 24 c-16 0 -24 -10 -24 -24 c0 -14 8 -26 24 -26z",
  },
  // tall slim column
  column: {
    body: "M74 96 h52 a4 4 0 0 1 4 4 v152 a4 4 0 0 1 -4 4 h-52 a4 4 0 0 1 -4 -4 v-152 a4 4 0 0 1 4 -4z",
    liquid: "M72 132 h56 v118 a3 3 0 0 1 -3 3 h-50 a3 3 0 0 1 -3 -3z",
    neck: [92, 84, 16, 12],
    cap: "M86 30 h28 v54 h-28z",
  },
  // faceted flacon
  facet: {
    body: "M78 112 h44 l34 34 v76 l-34 34 h-44 l-34 -34 v-76z",
    liquid: "M46 168 h108 v52 l-33 33 h-42 l-33 -33z",
    neck: [90, 98, 20, 14],
    cap: "M100 40 l26 26 l-26 32 l-26 -32z",
  },
};

export function Bottle({
  product,
  seller,
  scene = "studio",
  className = "",
  decorative = false,
}: {
  product: Pick<Product, "id" | "name" | "hue" | "concentration" | "size_ml">;
  seller: Pick<Seller, "name" | "bottle" | "accent">;
  scene?: Scene;
  className?: string;
  decorative?: boolean; // duplicate images (hover layers, thumbnails) stay out of the accessibility tree
}) {
  const s = SHAPES[seller.bottle] ?? SHAPES.block;
  const id = `${product.id}-${scene}`;
  const dark = scene === "noir";
  const [nx, ny, nw, nh] = s.neck;
  const viewBox = scene === "detail" ? "30 120 140 120" : "0 0 200 300";

  return (
    <svg viewBox={viewBox} preserveAspectRatio="xMidYMid slice" className={className} {...(decorative ? { "aria-hidden": true } : { role: "img", "aria-label": `${product.name} bottle by ${seller.name}` })}>
      <defs>
        <radialGradient id={`bg-${id}`} cx="50%" cy="38%" r="75%">
          <stop offset="0" stopColor={dark ? "#2b2620" : "#fbf8f1"} />
          <stop offset="1" stopColor={dark ? "#0e0d0b" : "#e9dfcd"} />
        </radialGradient>
        <linearGradient id={`glass-${id}`} x1="0" x2="1">
          <stop offset="0" stopColor="#fff" stopOpacity={dark ? 0.1 : 0.55} />
          <stop offset="0.45" stopColor="#fff" stopOpacity="0.06" />
          <stop offset="1" stopColor="#fff" stopOpacity={dark ? 0.18 : 0.35} />
        </linearGradient>
        <linearGradient id={`juice-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={product.hue} stopOpacity="0.75" />
          <stop offset="1" stopColor={product.hue} stopOpacity="1" />
        </linearGradient>
        <linearGradient id={`cap-${id}`} x1="0" x2="1">
          <stop offset="0" stopColor={seller.accent} />
          <stop offset="0.5" stopColor="#e9d9b4" />
          <stop offset="1" stopColor={seller.accent} />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width="200" height="300" fill={`url(#bg-${id})`} />
      {dark && <path d="M70 0 L130 0 L180 300 L20 300 Z" fill="#fff" opacity="0.04" />}
      <ellipse cx="100" cy="262" rx="62" ry="7" fill="#000" opacity={dark ? 0.6 : 0.16} />

      <path d={s.cap} fill={`url(#cap-${id})`} />
      <rect x={nx} y={ny} width={nw} height={nh} fill={seller.accent} opacity="0.85" />
      <path d={s.body} fill={dark ? "#ffffff10" : "#ffffff55"} stroke={dark ? "#ffffff30" : "#00000022"} strokeWidth="1" />
      <path d={s.liquid} fill={`url(#juice-${id})`} />
      <path d={s.body} fill={`url(#glass-${id})`} />

      <rect x="72" y="182" width="56" height="44" fill="#fbf8f1" opacity="0.94" />
      <text x="100" y="196" textAnchor="middle" fontFamily="Jost, sans-serif" fontSize="4" letterSpacing="1.4" fill="#6f675c">
        {seller.name.toUpperCase()}
      </text>
      <text x="100" y="210" textAnchor="middle" fontFamily="Cormorant Garamond, serif" fontSize={product.name.length > 14 ? 7 : 9} fill="#0e0d0b">
        {product.name}
      </text>
      <text x="100" y="220" textAnchor="middle" fontFamily="Jost, sans-serif" fontSize="3.6" letterSpacing="1" fill="#6f675c">
        {product.concentration.toUpperCase()} · {product.size_ml} ML
      </text>
    </svg>
  );
}
