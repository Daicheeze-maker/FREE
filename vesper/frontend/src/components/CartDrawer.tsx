import { AnimatePresence, motion } from "motion/react";
import { Minus, Plus, X } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate } from "react-router";
import type { CartLine } from "../lib/api";
import { useShop } from "../lib/store";
import { Bottle } from "./Bottle";

export function QuantitySelector({
  value,
  max,
  onChange,
  disabled,
  label,
}: {
  value: number;
  max: number;
  onChange: (n: number) => void;
  disabled?: boolean;
  label: string;
}) {
  const cap = Math.min(max, 10);
  return (
    <div className="inline-flex items-center border border-sand" role="group" aria-label={`Quantity for ${label}`}>
      <button
        type="button"
        className="p-2.5 disabled:opacity-30"
        onClick={() => onChange(value - 1)}
        disabled={disabled || value <= 1}
        aria-label="Decrease quantity"
      >
        <Minus size={12} />
      </button>
      <span className="w-8 text-center text-sm tabular-nums" aria-live="polite">{value}</span>
      <button
        type="button"
        className="p-2.5 disabled:opacity-30"
        onClick={() => onChange(value + 1)}
        disabled={disabled || value >= cap}
        aria-label="Increase quantity"
        title={value >= cap ? `Only ${max} in stock` : undefined}
      >
        <Plus size={12} />
      </button>
    </div>
  );
}

export function CartLines({ items, compact = false }: { items: CartLine[]; compact?: boolean }) {
  const { price, setQuantity, removeItem, cartBusy, setDrawerOpen } = useShop();
  return (
    <ul className="divide-y divide-champagne">
      {items.map(({ product, quantity, line_total_centavos }) => (
        <li key={product.id} className={`flex gap-5 py-6 ${cartBusy === product.id ? "opacity-50" : ""}`}>
          <Link to={`/product/${product.id}`} onClick={() => setDrawerOpen(false)} className={compact ? "w-20 shrink-0" : "w-28 shrink-0"}>
            <Bottle product={product} seller={product.seller} className="w-full" />
          </Link>
          <div className="flex flex-1 flex-col">
            <div className="flex justify-between gap-4">
              <div>
                <p className="eyebrow text-smoke">{product.seller.name}</p>
                <Link to={`/product/${product.id}`} onClick={() => setDrawerOpen(false)} className="display mt-1 block text-2xl">
                  {product.name}
                </Link>
                <p className="mt-1 text-xs text-smoke">{product.concentration} · {product.size_ml} mL · {price(product.price_centavos)} each</p>
              </div>
              <p className="text-sm tabular-nums">{price(line_total_centavos)}</p>
            </div>
            <div className="mt-auto flex items-center justify-between pt-4">
              <QuantitySelector
                value={quantity}
                max={product.stock}
                label={product.name}
                disabled={cartBusy === product.id}
                onChange={(n) => setQuantity(product.id, n)}
              />
              <button className="eyebrow link-line text-smoke" onClick={() => removeItem(product.id)} disabled={cartBusy === product.id}>
                Remove
              </button>
            </div>
            {quantity > product.stock && (
              <p className="mt-2 text-xs text-wine">Only {product.stock} left — please lower the quantity.</p>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Totals() {
  const { cart, price, currency, rate, rateError } = useShop();
  if (!cart) return null;
  return (
    <dl className="space-y-3 text-sm">
      <div className="flex justify-between"><dt>Subtotal</dt><dd className="tabular-nums">{price(cart.subtotal_centavos)}</dd></div>
      <div className="flex justify-between"><dt>Shipping <span className="text-smoke">(flat demo rate)</span></dt><dd className="tabular-nums">{price(cart.shipping_centavos)}</dd></div>
      <div className="display flex justify-between border-t border-champagne pt-4 text-2xl"><dt>Total</dt><dd className="tabular-nums">{price(cart.total_centavos)}</dd></div>
      <CurrencyNote />
      {currency !== "PHP" && rate && !rateError && <p className="text-xs text-smoke">You will be charged in PHP.</p>}
    </dl>
  );
}

export function CurrencyNote() {
  const { currency, rate, rateError } = useShop();
  if (currency === "PHP") return null;
  if (rateError) return <p className="text-xs text-wine">Exchange rate unavailable — showing prices in PHP.</p>;
  if (!rate) return null;
  return (
    <p className="text-xs text-smoke">
      1 PHP = {rate.rate} {rate.quote} · rate dated {rate.date}
      {rate.stale ? " (cached, latest fetch failed)" : ""} · Frankfurter
    </p>
  );
}

export function CartDrawer() {
  const { cart, drawerOpen, setDrawerOpen } = useShop();
  const navigate = useNavigate();
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawerOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen, setDrawerOpen]);

  const go = (to: string) => {
    setDrawerOpen(false);
    navigate(to);
  };
  const items = cart?.items ?? [];

  return (
    <AnimatePresence>
      {drawerOpen && (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-ink/40"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setDrawerOpen(false)}
          />
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label="Shopping bag"
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-paper"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "tween", duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-champagne px-6 py-5">
              <p className="eyebrow">Your bag ({cart?.item_count ?? 0})</p>
              <button onClick={() => setDrawerOpen(false)} aria-label="Close bag" autoFocus>
                <X size={20} strokeWidth={1.25} />
              </button>
            </div>
            {items.length === 0 ? (
              <div className="flex flex-1 flex-col items-center justify-center px-10 text-center">
                <p className="display text-4xl">Your bag is empty</p>
                <p className="mt-3 text-sm text-smoke">Every collection begins with a single bottle.</p>
                <button className="btn btn-dark mt-8" onClick={() => go("/shop")}>Explore fragrances</button>
              </div>
            ) : (
              <>
                <div className="flex-1 overflow-y-auto px-6">
                  <CartLines items={items} compact />
                </div>
                <div className="space-y-4 border-t border-champagne px-6 py-6">
                  <Totals />
                  <button className="btn btn-dark w-full" onClick={() => go("/checkout")}>Checkout</button>
                  <button className="eyebrow link-line mx-auto block" onClick={() => go("/cart")}>View full bag</button>
                </div>
              </>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
