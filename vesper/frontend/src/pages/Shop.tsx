import { SlidersHorizontal, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { ProductCard } from "../components/ProductCard";
import { CurrencyNote } from "../components/CartDrawer";
import { ErrorState, Loading } from "../components/States";
import type { Product, Seller } from "../lib/api";
import { useApi } from "../lib/useApi";
import { FAMILIES } from "./Home";

const PRICE_MAX = 20000;
const SORTS = [
  ["", "Featured"],
  ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"],
  ["name_asc", "Name: A–Z"],
  ["name_desc", "Name: Z–A"],
] as const;

export default function Shop() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const sellers = useApi<Seller[]>("/sellers");

  // Keep the search box in sync when the header search navigates here.
  const urlQ = params.get("q") ?? "";
  useEffect(() => {
    setQ(urlQ);
  }, [urlQ]);
  // Debounce typing into the URL.
  useEffect(() => {
    const t = setTimeout(() => update((p) => (q ? p.set("q", q) : p.delete("q"))), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  // Read the live URL, not the render-time params: the debounced search must not undo newer filter changes.
  const update = (fn: (p: URLSearchParams) => void) => {
    const next = new URLSearchParams(window.location.search);
    fn(next);
    setParams(next, { replace: true });
  };
  const toggle = (key: string, value: string) =>
    update((p) => {
      const values = p.getAll(key);
      p.delete(key);
      (values.includes(value) ? values.filter((v) => v !== value) : [...values, value]).forEach((v) => p.append(key, v));
    });

  const minPrice = Number(params.get("min_price") ?? 0);
  const maxPrice = Number(params.get("max_price") ?? PRICE_MAX);
  const products = useApi<Product[]>(`/products?${params.toString()}`);
  const activeCount = params.getAll("seller").length + params.getAll("family").length +
    (params.has("min_price") || params.has("max_price") ? 1 : 0) + (params.get("q") ? 1 : 0);

  const filters = (
    <div className="space-y-10">
      <fieldset>
        <legend className="eyebrow mb-4 text-smoke">House</legend>
        {(sellers.data ?? []).map((s) => (
          <label key={s.id} className="flex cursor-pointer items-center gap-3 py-1.5 text-sm">
            <input type="checkbox" className="accent-ink" checked={params.getAll("seller").includes(s.id)} onChange={() => toggle("seller", s.id)} />
            {s.name}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend className="eyebrow mb-4 text-smoke">Fragrance family</legend>
        {Object.keys(FAMILIES).map((f) => (
          <label key={f} className="flex cursor-pointer items-center gap-3 py-1.5 text-sm">
            <input type="checkbox" className="accent-ink" checked={params.getAll("family").includes(f)} onChange={() => toggle("family", f)} />
            {f}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend className="eyebrow mb-4 text-smoke">Price (PHP)</legend>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="flex justify-between"><span>Min</span><span className="tabular-nums">₱{minPrice.toLocaleString()}</span></span>
            <input type="range" min={0} max={PRICE_MAX} step={500} value={minPrice} className="w-full"
              onChange={(e) => update((p) => p.set("min_price", String(Math.min(Number(e.target.value), maxPrice))))} />
          </label>
          <label className="block">
            <span className="flex justify-between"><span>Max</span><span className="tabular-nums">₱{maxPrice.toLocaleString()}</span></span>
            <input type="range" min={0} max={PRICE_MAX} step={500} value={maxPrice} className="w-full"
              onChange={(e) => update((p) => p.set("max_price", String(Math.max(Number(e.target.value), minPrice))))} />
          </label>
        </div>
      </fieldset>
      {activeCount > 0 && (
        <button className="eyebrow link-line" onClick={() => { setQ(""); setParams(new URLSearchParams(params.get("sort") ? { sort: params.get("sort")! } : {})); }}>
          Clear all filters
        </button>
      )}
    </div>
  );

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-24 pt-28 md:px-10 md:pt-36">
      <header className="grid gap-6 border-b border-champagne pb-10 md:grid-cols-12 md:items-end">
        <div className="md:col-span-7">
          <p className="eyebrow text-gold">The collection</p>
          <h1 className="display mt-3 text-6xl md:text-8xl">All fragrances</h1>
        </div>
        <div className="md:col-span-5">
          <label htmlFor="shop-search" className="eyebrow text-smoke">Search by perfume or house</label>
          <div className="mt-2 flex items-center border-b border-ink">
            <input id="shop-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. Fjord, Velours Noir" className="w-full bg-transparent py-2 text-lg outline-none placeholder:text-sand" />
            {q && <button onClick={() => setQ("")} aria-label="Clear search"><X size={16} /></button>}
          </div>
        </div>
      </header>

      <div className="flex items-center justify-between py-6">
        <button className="eyebrow flex items-center gap-2 lg:hidden" onClick={() => setFiltersOpen((o) => !o)} aria-expanded={filtersOpen}>
          <SlidersHorizontal size={14} /> Filters {activeCount > 0 && `(${activeCount})`}
        </button>
        <p className="eyebrow hidden text-smoke lg:block" aria-live="polite">
          {products.data ? `${products.data.length} of 20 fragrances` : " "}
        </p>
        <label className="eyebrow flex items-center gap-3">
          <span className="text-smoke">Sort</span>
          <select value={params.get("sort") ?? ""} onChange={(e) => update((p) => (e.target.value ? p.set("sort", e.target.value) : p.delete("sort")))} className="bg-transparent py-1 outline-none">
            {SORTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>

      <div className="grid gap-10 lg:grid-cols-[14rem_1fr]">
        <aside className={`${filtersOpen ? "block" : "hidden"} border-b border-champagne pb-8 lg:block lg:border-0`}>{filters}</aside>
        <section aria-label="Products">
          <div className="mb-6"><CurrencyNote /></div>
          {products.loading && !products.data ? (
            <Loading label="Gathering bottles" />
          ) : products.error ? (
            <ErrorState message={products.error} />
          ) : products.data?.length === 0 ? (
            <div className="py-24 text-center">
              <p className="display text-4xl">Nothing matches — yet.</p>
              <p className="mt-3 text-sm text-smoke">Try a different house, family or price range.</p>
            </div>
          ) : (
            <div className={`grid grid-cols-2 gap-x-4 gap-y-14 md:grid-cols-3 md:gap-x-8 ${products.loading ? "opacity-60" : ""}`}>
              {products.data?.map((p, i) => (
                <div key={p.id} className={i % 3 === 1 ? "md:mt-16" : ""}>
                  <ProductCard product={p} index={i} />
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
