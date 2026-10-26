import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";
import { Link, useParams } from "react-router";
import { Bottle } from "../components/Bottle";
import { ProductCard } from "../components/ProductCard";
import { ErrorState, Loading } from "../components/States";
import type { Product, Seller } from "../lib/api";
import { useApi } from "../lib/useApi";

export function HousesIndex() {
  const { data, error, loading } = useApi<Seller[]>("/sellers");
  if (loading) return <div className="pt-24"><Loading /></div>;
  if (error) return <div className="pt-24"><ErrorState message={error} /></div>;
  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-24 pt-28 md:px-10 md:pt-36">
      <p className="eyebrow text-gold">The houses</p>
      <h1 className="display mt-3 text-6xl md:text-8xl">Four voices</h1>
      <div className="mt-16 divide-y divide-champagne border-y border-champagne">
        {data?.map((s, i) => (
          <Link key={s.id} to={`/houses/${s.id}`} className="group grid items-center gap-6 py-10 md:grid-cols-12">
            <span className="display text-3xl text-sand md:col-span-1">0{i + 1}</span>
            <span className="display text-5xl transition-transform duration-500 group-hover:translate-x-3 md:col-span-5 md:text-7xl" style={{ color: s.accent }}>{s.name}</span>
            <span className="text-sm leading-relaxed text-smoke md:col-span-4">{s.tagline}<br /><span className="eyebrow">{s.origin} · est. {s.founded}</span></span>
            <span className="eyebrow flex items-center gap-2 md:col-span-2 md:justify-end">{s.product_count} scents <ArrowRight size={12} /></span>
          </Link>
        ))}
      </div>
    </div>
  );
}

export function SellerPage() {
  const { id } = useParams();
  const { data, error, loading } = useApi<Seller & { product_count: number; products: Product[] }>(`/sellers/${id}`);
  if (loading) return <div className="pt-24"><Loading /></div>;
  if (error || !data) return <div className="pt-24"><ErrorState message={error ?? "Not found"} /></div>;
  const [hero, ...rest] = data.products;

  return (
    <>
      <section className="relative overflow-hidden text-paper" style={{ background: `linear-gradient(160deg, ${data.accent} 0%, #0e0d0b 70%)` }}>
        <div className="mx-auto grid min-h-[85svh] max-w-[1400px] items-end gap-10 px-4 pb-16 pt-32 md:grid-cols-12 md:px-10">
          <div className="md:col-span-7">
            <p className="eyebrow text-champagne">{data.origin} · Established {data.founded} · Fictional house</p>
            <motion.h1 className="display mt-6 text-7xl md:text-9xl" initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 1 }}>
              {data.name}
            </motion.h1>
            <p className="display mt-6 max-w-xl text-3xl italic text-champagne">{data.tagline}</p>
            <p className="mt-6 max-w-lg text-sm leading-relaxed text-sand">{data.description}</p>
            <p className="eyebrow mt-10">{data.product_count} of 5 compositions listed</p>
          </div>
          {hero && (
            <motion.div className="md:col-span-5" initial={{ clipPath: "inset(0 0 100% 0)" }} animate={{ clipPath: "inset(0 0 0% 0)" }} transition={{ duration: 1.4, delay: 0.2 }}>
              <Bottle product={hero} seller={data} scene="noir" className="mx-auto max-h-[60vh] w-full" />
            </motion.div>
          )}
        </div>
      </section>
      <section className="mx-auto max-w-[1400px] px-4 py-20 md:px-10 md:py-28">
        <div className="flex items-end justify-between">
          <h2 className="display text-5xl">The collection</h2>
          <Link to={`/shop?seller=${data.id}`} className="eyebrow link-line">Filter in shop</Link>
        </div>
        <div className="mt-12 grid grid-cols-2 gap-x-4 gap-y-14 md:grid-cols-12 md:gap-x-8">
          {hero && <div className="col-span-2 md:col-span-6 md:row-span-2"><ProductCard product={hero} tall /></div>}
          {rest.map((p, i) => (
            <div key={p.id} className={`md:col-span-3 ${i < 2 ? "md:mt-24" : ""}`}><ProductCard product={p} index={i} /></div>
          ))}
        </div>
      </section>
    </>
  );
}
