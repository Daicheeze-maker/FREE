export type Seller = {
  id: string;
  name: string;
  tagline: string;
  description: string;
  origin: string;
  founded: number;
  accent: string;
  bottle: "block" | "dome" | "column" | "facet";
  product_count?: number;
};

export type Product = {
  id: string;
  seller_id: string;
  name: string;
  price_centavos: number;
  description: string;
  top_notes: string[];
  heart_notes: string[];
  base_notes: string[];
  size_ml: number;
  family: string;
  concentration: string;
  stock: number;
  hue: string;
  bestseller: boolean;
  seller: Seller;
};

export type CartLine = { product: Product; quantity: number; line_total_centavos: number };

export type Cart = {
  id: string;
  items: CartLine[];
  item_count: number;
  subtotal_centavos: number;
  shipping_centavos: number;
  total_centavos: number;
};

export type Order = {
  id: string;
  status: "pending" | "paid" | "failed" | "cancelled";
  payment_method: string;
  payment_provider: "mock" | "paymongo";
  payment_status: string;
  subtotal_centavos: number;
  shipping_centavos: number;
  total_centavos: number;
  created_at: string;
  paid_at: string | null;
  customer: { name: string; email: string };
  items: { product_id: string; name: string; seller_name: string; unit_price_centavos: number; quantity: number }[];
};

export type Rate = { base: string; quote: string; rate: string; date: string | null; source: string; stale: boolean };

export class ApiError extends Error {
  constructor(message: string, public status: number, public fields: Record<string, string> = {}) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`/api${path}`, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  }).catch(() => {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  });
  if (res.ok) return res.json();
  const body = await res.json().catch(() => ({}));
  // FastAPI validation errors come as a list; flatten them to {field: message}.
  if (Array.isArray(body.detail)) {
    const fields: Record<string, string> = {};
    for (const e of body.detail) fields[String(e.loc?.[e.loc.length - 1])] = String(e.msg).replace(/^Value error, /, "");
    throw new ApiError("Please check the highlighted fields.", res.status, fields);
  }
  throw new ApiError(body.detail ?? `Request failed (${res.status})`, res.status);
}
