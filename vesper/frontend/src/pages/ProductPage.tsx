import { motion } from "motion/react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { Bottle } from "../components/Bottle";
import { CurrencyNote, QuantitySelector } from "../components/CartDrawer";
import { AddButton, Availability, ProductCard } from "../components/ProductCard";
import { ErrorState, Loading } from "../components/States";
import type { Product } from "../lib/api";
import { useShop } from "../lib/store";
import { useApi } from "../lib/useApi";

const SCENES = [
  { scene: "studio", label: "Studio" },
  { scene: "noir", label: "Evening" },
  { scene: "detail", label: "Label detail" },
] as const;

function NotesPyramid({ p }: { p: Product }) {
  const tiers = [
    { name: "Top", time: "First 15 minutes", notes: p.top_notes, width: "w-[55%]" },
    { name: "Heart", time: "The next 3 hours", notes: p.heart_notes, width: "w-[78%]" },
    { name: "Base", time: "Lingers all day", notes: p.base_notes, width: "w-full" },
  ];
  return (
    <div className="space-y-2">
      {tiers.map((t, i) => (
        <motion.div
          key={t.name}
          initial={{ opacity: 0, x: -20 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ delay: i * 0.15, duration: 0.7 }}
          className={`${t.width} border-l-2 py-4 pl-5`}
          style={{ borderColor: p.hue, background: `linear-gradient(90deg, ${p.hue}22, transparent)` }}
        >
          <div className="flex items-baseline justify-between gap-4">
            <span className="eyebrow">{t.name} notes</span>
            <span className="text-[0.65rem] italic text-smoke">{t.time}</span>
          </div>
          <p className="display mt-1 text-2xl">{t.notes.join(" · ")}</p>
        </motion.div>
      ))}
    </div>
  );
}

export default function ProductPage() {
  const { id } = useParams();
  const { data, error, loading } = useApi<{ product: Product; related: Product[] }>(`/products/${id}`);
  const { price, cart } = useShop();
  const [scene, setScene] = useState<(typeof SCENES)[number]["scene"]>("studio");
  const [qty, setQty] = useState(1);

  if (loading) return <div className="pt-24"><Loading /></div>;
  if (error || !data) return <div className="pt-24"><ErrorState message={error ?? "Not found"} /></div>;
  const p = data.product;
  const inCart = cart?.items.find((i) => i.product.id === p.id)?.quantity ?? 0;
  const available = Math.max(0, p.stock - inCart);

  return (
    <>
      <div className="mx-auto max-w-[1400px] px-4 pb-20 pt-24 md:px-10 md:pt-32">
        <nav className="eyebrow mb-8 text-smoke" aria-label="Breadcrumb">
          <Link to="/shop" className="link-line">Shop</Link> / <Link to={`/houses/${p.seller.id}`} className="link-line">{p.seller.name}</Link> / <span className="text-ink">{p.name}</span>
        </nav>
        <div className="grid gap-10 md:grid-cols-12 md:gap-16">
          <div className="md:col-span-7">
            <div className="grid gap-4 md:grid-cols-[5rem_1fr]">
              <div className="order-2 flex gap-3 md:order-1 md:flex-col" role="tablist" aria-label="Gallery">
                {SCENES.map((s) => (
                  <button
                    key={s.scene}
                    role="tab"
                    aria-selected={scene === s.scene}
                    aria-label={s.label}
                    onClick={() => setScene(s.scene)}
                    className={`w-20 overflow-hidden border transition-colors ${scene === s.scene ? "border-ink" : "border-transparent opacity-60 hover:opacity-100"}`}
                  >
                    <Bottle product={p} seller={p.seller} scene={s.scene} decorative className="aspect-[2/3] w-full" />
                  </button>
                ))}
              </div>
              <motion.div key={scene} initial={{ opacity: 0, scale: 1.02 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }} className="order-1 bg-champagne md:order-2">
                <Bottle product={p} seller={p.seller} scene={scene} className="aspect-[2/3] w-full" />
              </motion.div>
            </div>
          </div>

          <div className="md:col-span-5 md:pt-6">
            <Link to={`/houses/${p.seller.id}`} className="eyebrow link-line" style={{ color: p.seller.accent }}>{p.seller.name}</Link>
            <h1 className="display mt-3 text-6xl md:text-7xl">{p.name}</h1>
            <p className="eyebrow mt-4 text-smoke">{p.family} · {p.concentration === "EDT" ? "Eau de Toilette" : p.concentration === "EDP" ? "Eau de Parfum" : "Parfum"} · {p.size_ml} mL</p>
            <div className="mt-8 flex items-end justify-between border-y border-champagne py-5">
              <p className="display text-4xl tabular-nums">{price(p.price_centavos)}</p>
              <div className="text-right">
                <Availability stock={p.stock} />
                <p className="mt-1 text-xs text-smoke">{p.stock} in stock{inCart ? ` · ${inCart} in your bag` : ""}</p>
              </div>
            </div>
            <div className="mt-2"><CurrencyNote /></div>
            <p className="mt-8 leading-relaxed">{p.description}</p>
            <div className="mt-10 flex items-center gap-4">
              <QuantitySelector value={Math.min(qty, Math.max(available, 1))} max={Math.max(available, 1)} onChange={setQty} disabled={available === 0} label={p.name} />
              <AddButton product={p} quantity={Math.min(qty, Math.max(available, 1))} className="btn btn-dark flex-1" />
            </div>
            <p className="mt-4 text-xs text-smoke">Flat ₱180 demo shipping · Paid securely via PayMongo test mode</p>
            <div className="mt-14">
              <p className="eyebrow mb-5 text-gold">The composition</p>
              <NotesPyramid p={p} />
            </div>
          </div>
        </div>
      </div>

      <section className="text-paper" style={{ background: "#0e0d0b" }}>
        <div className="mx-auto grid max-w-[1400px] gap-8 px-4 py-16 md:grid-cols-12 md:px-10 md:py-20">
          <div className="md:col-span-4">
            <p className="eyebrow text-gold-light">The house</p>
            <h2 className="display mt-3 text-5xl">{p.seller.name}</h2>
            <p className="eyebrow mt-2 text-sand">{p.seller.origin} · est. {p.seller.founded}</p>
          </div>
          <div className="md:col-span-5">
            <p className="leading-relaxed text-sand">{p.seller.description}</p>
          </div>
          <div className="flex items-end md:col-span-3 md:justify-end">
            <Link to={`/houses/${p.seller.id}`} className="btn btn-light">Visit the house</Link>
          </div>
        </div>
      </section>

      {data.related.length > 0 && (
        <section className="mx-auto max-w-[1400px] px-4 py-20 md:px-10">
          <h2 className="display text-4xl md:text-5xl">Also from {p.seller.name}</h2>
          <div className="mt-10 grid grid-cols-2 gap-x-4 gap-y-12 md:grid-cols-4 md:gap-x-8">
            {data.related.map((r, i) => <ProductCard key={r.id} product={r} index={i} />)}
          </div>
        </section>
      )}
    </>
  );
}
