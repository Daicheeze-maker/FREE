import { AnimatePresence, motion } from "motion/react";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";
import type { Product } from "../lib/api";
import { useShop } from "../lib/store";
import { Bottle } from "./Bottle";

export function Availability({ stock }: { stock: number }) {
  if (stock <= 0) return <span className="eyebrow text-wine">Sold out</span>;
  if (stock <= 5) return <span className="eyebrow text-gold">Only {stock} left</span>;
  return <span className="eyebrow text-smoke">In stock</span>;
}

export function AddButton({ product, quantity = 1, className = "btn btn-dark" }: { product: Product; quantity?: number; className?: string }) {
  const { addToCart, cartBusy, cart } = useShop();
  const inCart = cart?.items.find((i) => i.product.id === product.id)?.quantity ?? 0;
  const soldOut = product.stock <= 0;
  const maxed = !soldOut && inCart + quantity > product.stock;
  const busy = cartBusy === product.id;
  return (
    <button
      className={className}
      disabled={soldOut || maxed || busy}
      onClick={() => addToCart(product.id, quantity, product.name)}
    >
      {soldOut ? "Sold out" : maxed ? "All stock in bag" : busy ? "Adding…" : "Add to bag"}
    </button>
  );
}

export function ProductCard({ product, index = 0, tall = false }: { product: Product; index?: number; tall?: boolean }) {
  const { price } = useShop();
  const [quick, setQuick] = useState(false);
  return (
    <motion.article
      className="group"
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.7, delay: (index % 4) * 0.06, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className={`relative overflow-hidden bg-champagne ${tall ? "aspect-[3/4.4]" : "aspect-[3/4]"}`}>
        <Link to={`/product/${product.id}`} aria-label={product.name} className="block h-full">
          <Bottle product={product} seller={product.seller} className="absolute inset-0 h-full w-full object-cover transition-transform duration-[1.2s] ease-out group-hover:scale-[1.04]" />
          <Bottle product={product} seller={product.seller} scene="noir" decorative className="absolute inset-0 h-full w-full opacity-0 transition-opacity duration-700 group-hover:opacity-100" />
        </Link>
        {product.bestseller && <span className="eyebrow absolute left-4 top-4 bg-paper/90 px-2 py-1 text-[0.58rem]">Bestseller</span>}
        <div className="absolute inset-x-0 bottom-0 flex translate-y-0 gap-px opacity-100 transition-all duration-500 md:translate-y-full md:opacity-0 md:group-hover:translate-y-0 md:group-hover:opacity-100 md:group-focus-within:translate-y-0 md:group-focus-within:opacity-100">
          <button className="btn btn-light min-w-0 flex-1 px-1 py-3 tracking-[0.1em] md:tracking-[0.24em]" onClick={() => setQuick(true)}>Quick view</button>
          <AddButton product={product} className="btn btn-dark min-w-0 flex-1 px-1 py-3 tracking-[0.1em] md:tracking-[0.24em]" />
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-2 md:flex-row md:items-start md:justify-between md:gap-4">
        <div>
          <p className="eyebrow text-smoke">{product.seller.name}</p>
          <h3 className="display mt-1 text-2xl">
            <Link to={`/product/${product.id}`} className="link-line">{product.name}</Link>
          </h3>
          <p className="mt-1 text-xs text-smoke">{product.family} · {product.concentration} · {product.size_ml} mL</p>
        </div>
        <div className="flex items-baseline justify-between gap-2 md:block md:text-right">
          <p className="text-sm tabular-nums">{price(product.price_centavos)}</p>
          <div className="md:mt-1"><Availability stock={product.stock} /></div>
        </div>
      </div>
      <QuickView product={product} open={quick} onClose={() => setQuick(false)} />
    </motion.article>
  );
}

function QuickView({ product, open, onClose }: { product: Product; open: boolean; onClose: () => void }) {
  const { price } = useShop();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Portal: the card animates with transforms, which would trap a fixed-position overlay.
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/50 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={`Quick view: ${product.name}`}
            className="relative grid max-h-[90vh] w-full max-w-4xl overflow-y-auto bg-paper md:grid-cols-2"
            initial={{ y: 30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 30, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <button className="absolute right-4 top-4 z-10" onClick={onClose} aria-label="Close quick view" autoFocus>
              <X size={20} strokeWidth={1.25} />
            </button>
            <Bottle product={product} seller={product.seller} className="h-full max-h-[60vh] w-full md:max-h-none" />
            <div className="flex flex-col p-8 md:p-10">
              <p className="eyebrow text-smoke">{product.seller.name}</p>
              <h2 className="display mt-2 text-5xl">{product.name}</h2>
              <p className="mt-2 text-xs text-smoke">{product.family} · {product.concentration} · {product.size_ml} mL</p>
              <p className="mt-6 text-sm leading-relaxed">{product.description}</p>
              <dl className="mt-6 space-y-2 text-sm">
                <div className="flex gap-3"><dt className="eyebrow w-16 pt-0.5 text-gold">Top</dt><dd>{product.top_notes.join(", ")}</dd></div>
                <div className="flex gap-3"><dt className="eyebrow w-16 pt-0.5 text-gold">Heart</dt><dd>{product.heart_notes.join(", ")}</dd></div>
                <div className="flex gap-3"><dt className="eyebrow w-16 pt-0.5 text-gold">Base</dt><dd>{product.base_notes.join(", ")}</dd></div>
              </dl>
              <div className="mt-8 flex items-center justify-between">
                <p className="display text-3xl tabular-nums">{price(product.price_centavos)}</p>
                <Availability stock={product.stock} />
              </div>
              <div className="mt-6 flex flex-col gap-3">
                <AddButton product={product} />
                <Link to={`/product/${product.id}`} className="eyebrow link-line self-center" onClick={onClose}>Full details</Link>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
