import { motion } from "motion/react";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { Bottle } from "../components/Bottle";
import { AddButton, ProductCard } from "../components/ProductCard";
import { ErrorState, Loading } from "../components/States";
import { api, type Product, type Seller } from "../lib/api";
import { useShop } from "../lib/store";
import { useApi } from "../lib/useApi";

const ease = [0.22, 1, 0.36, 1] as const;

export const FAMILIES: Record<string, string> = {
  Floral: "Petals at full bloom — tuberose, sampaguita, rose. Romantic, radiant, sometimes narcotic.",
  Woody: "Cedar, vetiver, birch and incense. Dry, grounded scents that feel like quiet rooms.",
  Amber: "Resins, vanilla and oud. Warm, enveloping and made for skin at night.",
  Fresh: "Citrus, salt and cold air. Clean, bright, for heat and for mornings.",
  Gourmand: "Cacao, praline, coffee. Edible accords, handled with a light touch.",
  Chypre: "Bergamot over oakmoss and patchouli. The classic structure of perfumery, made modern.",
};

function Hero({ feature }: { feature?: Product }) {
  return (
    <section className="relative min-h-[100svh] overflow-hidden bg-ink text-paper">
      <div className="mx-auto grid min-h-[100svh] max-w-[1400px] grid-cols-12 items-end gap-6 px-4 pb-14 pt-28 md:px-10 md:pb-20">
        <div className="relative z-10 col-span-12 md:col-span-7">
          <motion.p className="eyebrow text-gold-light" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
            Collection Nº 1 — Autumn / Winter 2026
          </motion.p>
          <h1 className="display mt-6 text-[clamp(3.4rem,9vw,8.6rem)]">
            {["Wear the", "hour after", "dark."].map((line, i) => (
              <span key={line} className="block overflow-hidden">
                <motion.span
                  className={`block ${i === 1 ? "italic text-champagne md:pl-[12%]" : ""}`}
                  initial={{ y: "105%" }}
                  animate={{ y: 0 }}
                  transition={{ duration: 1.1, delay: 0.25 + i * 0.12, ease }}
                >
                  {line}
                </motion.span>
              </span>
            ))}
          </h1>
          <motion.div
            className="mt-10 flex max-w-md flex-col gap-8 md:ml-[12%]"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.8 }}
          >
            <p className="text-sm leading-relaxed text-sand">
              Four independent perfume houses. Five compositions each. Twenty bottles, nothing more — so every one of
              them has to earn its place on your skin.
            </p>
            <div className="flex flex-wrap gap-4">
              <Link to="/shop" className="btn btn-light">Discover the collection <ArrowRight size={14} /></Link>
              <Link to="/houses" className="btn btn-ghost text-paper hover:!border-paper hover:!bg-paper hover:!text-ink">Meet the houses</Link>
            </div>
          </motion.div>
        </div>

        <motion.div
          className="absolute inset-y-0 right-0 w-full opacity-40 md:static md:col-span-5 md:h-[78vh] md:w-auto md:opacity-100"
          initial={{ clipPath: "inset(100% 0 0 0)" }}
          animate={{ clipPath: "inset(0% 0 0 0)" }}
          transition={{ duration: 1.6, delay: 0.4, ease }}
        >
          {feature && (
            <Link to={`/product/${feature.id}`} className="group relative block h-full" aria-label={`Featured: ${feature.name}`}>
              <Bottle product={feature} seller={feature.seller} scene="noir" className="h-full w-full object-cover" />
              <span className="absolute bottom-6 left-6 hidden text-left md:block">
                <span className="eyebrow block text-gold-light">The signature</span>
                <span className="display mt-1 block text-3xl">{feature.name}</span>
                <span className="eyebrow mt-1 block text-sand">{feature.seller.name} — {feature.seller.origin}</span>
              </span>
              <ArrowUpRight className="absolute right-6 top-6 hidden transition-transform group-hover:-translate-y-1 group-hover:translate-x-1 md:block" strokeWidth={1} />
            </Link>
          )}
        </motion.div>
      </div>
      <p className="eyebrow absolute bottom-6 right-4 hidden rotate-0 text-[0.55rem] text-smoke md:block md:right-10">
        Fictional houses · demonstration store
      </p>
    </section>
  );
}

function Featured({ products }: { products: Product[] }) {
  const { price } = useShop();
  const [lead, ...rest] = products;
  if (!lead) return null;
  return (
    <section className="mx-auto max-w-[1400px] px-4 py-24 md:px-10 md:py-36">
      <div className="grid grid-cols-12 gap-6 md:gap-10">
        <div className="col-span-12 md:col-span-4">
          <p className="eyebrow text-gold">The featured edit</p>
          <h2 className="display mt-4 text-5xl md:text-6xl">Precious, <em>rare</em>, made in small batches.</h2>
          <p className="mt-6 max-w-sm text-sm leading-relaxed text-smoke">
            Three compositions our perfumers consider their most uncompromising work — the bottles that sell out first.
          </p>
          <div className="mt-12 hidden md:block">
            <p className="display text-3xl">{lead.name}</p>
            <p className="eyebrow mt-2 text-smoke">{lead.seller.name} · {lead.concentration} · {lead.size_ml} mL</p>
            <p className="mt-4 text-sm leading-relaxed">{lead.description}</p>
            <div className="mt-6 flex items-center gap-6">
              <span className="text-sm tabular-nums">{price(lead.price_centavos)}</span>
              <AddButton product={lead} className="btn btn-dark" />
            </div>
          </div>
        </div>
        <Link to={`/product/${lead.id}`} className="group relative col-span-12 block overflow-hidden md:col-span-5 md:row-span-2" aria-label={lead.name}>
          <Bottle product={lead} seller={lead.seller} className="h-full w-full transition-transform duration-[1.4s] group-hover:scale-[1.03]" />
        </Link>
        <div className="col-span-12 grid grid-cols-2 gap-6 md:col-span-3 md:mt-40 md:grid-cols-1">
          {rest.map((p, i) => <ProductCard key={p.id} product={p} index={i} />)}
        </div>
      </div>
    </section>
  );
}

function Houses({ sellers }: { sellers: Seller[] }) {
  return (
    <section className="bg-ivory py-24 md:py-32">
      <div className="mx-auto max-w-[1400px] px-4 md:px-10">
        <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <h2 className="display text-5xl md:text-7xl">Four houses,<br /><em className="text-gold">one address.</em></h2>
          <p className="max-w-sm text-sm leading-relaxed text-smoke">
            Each house keeps its own voice, its own glass, its own way of working. We only ask that they choose their
            five best.
          </p>
        </div>
        <div className="mt-16 grid border-champagne md:grid-cols-4 md:border-r">
          {sellers.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08, duration: 0.8, ease }}
              className={`border-t border-champagne md:border-l md:border-t-0 ${i % 2 ? "md:mt-16" : ""}`}
            >
              <Link to={`/houses/${s.id}`} className="group flex h-full flex-col bg-ivory p-6 transition-colors duration-500 hover:bg-ink hover:text-paper md:p-8">
                <span className="eyebrow text-smoke group-hover:text-sand">0{i + 1} — {s.origin}, est. {s.founded}</span>
                <div className="my-8 h-40 overflow-hidden">
                  <Bottle
                    product={{ id: `house-${s.id}`, name: s.name.split(" ")[0], hue: s.accent, concentration: "Maison", size_ml: 0 }}
                    seller={s}
                    className="mx-auto h-full transition-transform duration-700 group-hover:scale-110"
                  />
                </div>
                <span className="display text-3xl">{s.name}</span>
                <span className="mt-3 text-sm leading-relaxed text-smoke group-hover:text-sand">{s.tagline}</span>
                <span className="eyebrow mt-8 flex items-center gap-2">
                  {s.product_count} fragrances <ArrowRight size={12} className="transition-transform group-hover:translate-x-1" />
                </span>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Bestsellers({ products }: { products: Product[] }) {
  const { price } = useShop();
  return (
    <section className="mx-auto max-w-[1400px] px-4 py-24 md:px-10 md:py-32">
      <div className="grid gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <p className="eyebrow text-gold">Most worn this season</p>
          <h2 className="display mt-4 text-5xl md:text-6xl">The bestsellers</h2>
          <Link to="/shop" className="eyebrow link-line mt-8 inline-block">See every fragrance</Link>
        </div>
        <ol className="md:col-span-8">
          {products.map((p, i) => (
            <li key={p.id} className="group border-t border-champagne last:border-b">
              <div className="grid grid-cols-[2.5rem_4rem_1fr_auto] items-center gap-4 py-5 md:grid-cols-[3rem_5rem_1fr_10rem_auto] md:gap-6">
                <span className="display text-2xl text-sand">{String(i + 1).padStart(2, "0")}</span>
                <Link to={`/product/${p.id}`} className="overflow-hidden" aria-label={p.name}>
                  <Bottle product={p} seller={p.seller} className="w-full transition-transform duration-700 group-hover:scale-110" />
                </Link>
                <div>
                  <Link to={`/product/${p.id}`} className="display link-line text-2xl md:text-3xl">{p.name}</Link>
                  <p className="eyebrow mt-1 text-smoke">{p.seller.name}</p>
                </div>
                <p className="hidden text-xs italic text-smoke md:block">{p.top_notes.join(" · ")}</p>
                <div className="flex flex-col items-end gap-2">
                  <span className="text-sm tabular-nums">{price(p.price_centavos)}</span>
                  <AddButton product={p} className="eyebrow link-line disabled:opacity-40" />
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Discover({ products }: { products: Product[] }) {
  const [family, setFamily] = useState("Woody");
  const matches = products.filter((p) => p.family === family);
  return (
    <section id="discover" className="scroll-mt-20 bg-ink py-24 text-paper md:py-32">
      <div className="mx-auto max-w-[1400px] px-4 md:px-10">
        <p className="eyebrow text-gold-light">Fragrance discovery</p>
        <h2 className="display mt-4 max-w-3xl text-5xl md:text-7xl">Where would you like to <em className="text-champagne">begin?</em></h2>
        <div className="mt-12 flex flex-wrap gap-x-8 gap-y-4" role="tablist" aria-label="Fragrance families">
          {Object.keys(FAMILIES).map((f) => (
            <button
              key={f}
              role="tab"
              aria-selected={family === f}
              onClick={() => setFamily(f)}
              className={`display text-3xl transition-colors md:text-4xl ${family === f ? "text-paper italic" : "text-smoke hover:text-sand"}`}
            >
              {f}
            </button>
          ))}
        </div>
        <motion.div key={family} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }} className="mt-12 grid gap-10 md:grid-cols-12">
          <div className="md:col-span-4">
            <p className="text-lg leading-relaxed text-sand">{FAMILIES[family]}</p>
            <Link to={`/shop?family=${family}`} className="btn btn-light mt-8">Shop {family.toLowerCase()} · {matches.length}</Link>
          </div>
          <div className="grid grid-cols-2 gap-4 md:col-span-8 md:grid-cols-4">
            {matches.map((p) => (
              <Link key={p.id} to={`/product/${p.id}`} className="group">
                <div className="overflow-hidden">
                  <Bottle product={p} seller={p.seller} scene="noir" className="w-full transition-transform duration-700 group-hover:scale-105" />
                </div>
                <p className="display mt-3 text-xl">{p.name}</p>
                <p className="eyebrow text-smoke">{p.seller.name}</p>
              </Link>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function Story() {
  return (
    <section className="mx-auto grid max-w-[1400px] gap-12 px-4 py-24 md:grid-cols-12 md:px-10 md:py-40">
      <div className="md:col-span-2">
        <p className="eyebrow text-gold">Our story</p>
      </div>
      <blockquote className="display text-4xl leading-tight md:col-span-7 md:text-6xl">
        “A perfume house that makes fifty scents is a factory. One that makes five is still listening to its
        <em className="text-gold"> nose</em>.”
      </blockquote>
      <div className="flex flex-col justify-end gap-8 text-sm leading-relaxed text-smoke md:col-span-3">
        <p>
          Vesper began as a dinner-table argument about why fragrance shops feel like airports. We built the opposite:
          a quiet room with few bottles, and the people who made them.
        </p>
        <dl className="grid grid-cols-3 gap-4 border-t border-champagne pt-6 text-ink">
          <div><dt className="eyebrow text-smoke">Houses</dt><dd className="display text-4xl">4</dd></div>
          <div><dt className="eyebrow text-smoke">Each</dt><dd className="display text-4xl">5</dd></div>
          <div><dt className="eyebrow text-smoke">Bottles</dt><dd className="display text-4xl">20</dd></div>
        </dl>
      </div>
    </section>
  );
}

function Newsletter() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<{ status: "idle" | "busy" | "done" | "error"; msg?: string }>({ status: "idle" });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setState({ status: "busy" });
    try {
      const r = await api<{ already: boolean }>("/newsletter", { method: "POST", json: { email } });
      setState({ status: "done", msg: r.already ? "You are already on the list." : "Welcome. The next letter is yours." });
    } catch (err) {
      const e2 = err as { fields?: Record<string, string>; message: string };
      setState({ status: "error", msg: e2.fields?.email ? "Please enter a valid email address." : e2.message });
    }
  };
  return (
    <section className="bg-champagne">
      <div className="mx-auto grid max-w-[1400px] items-end gap-10 px-4 py-20 md:grid-cols-2 md:px-10 md:py-28">
        <div>
          <p className="eyebrow text-smoke">The Vesper letter</p>
          <h2 className="display mt-4 text-5xl md:text-6xl">Notes from the atelier, once a month.</h2>
        </div>
        <form onSubmit={submit} noValidate>
          <label htmlFor="newsletter" className="eyebrow">Email address</label>
          <div className="mt-2 flex gap-4 border-b border-ink">
            <input
              id="newsletter"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-transparent py-3 outline-none placeholder:text-smoke"
              placeholder="you@example.com"
              aria-invalid={state.status === "error"}
              aria-describedby="newsletter-msg"
            />
            <button className="eyebrow shrink-0 disabled:opacity-40" disabled={state.status === "busy" || !email}>
              {state.status === "busy" ? "Sending…" : "Subscribe"}
            </button>
          </div>
          <p id="newsletter-msg" className={`mt-3 min-h-5 text-sm ${state.status === "error" ? "text-wine" : ""}`} aria-live="polite">
            {state.msg}
          </p>
        </form>
      </div>
    </section>
  );
}

export default function Home() {
  const products = useApi<Product[]>("/products");
  const sellers = useApi<Seller[]>("/sellers");
  const all = products.data ?? [];
  const byId = (id: string) => all.find((p) => p.id === id);

  return (
    <>
      <Hero feature={byId("atlas-oud-nocturne")} />
      {products.loading || sellers.loading ? (
        <Loading label="Opening the atelier" />
      ) : products.error || sellers.error ? (
        <ErrorState message={products.error ?? sellers.error ?? ""} retry={() => location.reload()} />
      ) : (
        <>
          <Featured products={["velours-encre", "nordlys-midnatt", "atlas-cuir-de-nuit"].map(byId).filter((p): p is Product => !!p)} />
          <Houses sellers={sellers.data ?? []} />
          <Bestsellers products={all.filter((p) => p.bestseller)} />
          <Discover products={all} />
          <Story />
        </>
      )}
      <Newsletter />
    </>
  );
}
