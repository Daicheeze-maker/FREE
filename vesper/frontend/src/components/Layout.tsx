import { AnimatePresence, motion } from "motion/react";
import { Menu, Search, ShoppingBag, X } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useShop } from "../lib/store";
import type { Currency } from "../lib/money";
import { CartDrawer } from "./CartDrawer";

const NAV = [
  { to: "/shop", label: "Shop all" },
  { to: "/houses", label: "The houses" },
  { to: "/shop?sort=price_desc", label: "Rare & precious" },
  { to: "/#discover", label: "Discover" },
];

function CurrencySwitch({ dark }: { dark: boolean }) {
  const { currency, setCurrency, rateLoading, rateError } = useShop();
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="currency" className="sr-only">Currency</label>
      <select
        id="currency"
        value={currency}
        onChange={(e) => setCurrency(e.target.value as Currency)}
        className={`eyebrow cursor-pointer bg-transparent py-1 outline-none ${dark ? "text-paper" : ""}`}
        title={rateError ?? undefined}
      >
        <option value="PHP" className="text-ink">PHP ₱</option>
        <option value="USD" className="text-ink">USD $</option>
      </select>
      {rateLoading && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-gold" aria-label="Loading rate" />}
    </div>
  );
}

function Header() {
  const { cart, setDrawerOpen } = useShop();
  const [menu, setMenu] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const [scrolled, setScrolled] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const overHero = pathname === "/" && !scrolled && !menu;

  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 40);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  useEffect(() => {
    setMenu(false);
  }, [pathname]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/shop?q=${encodeURIComponent(q.trim())}`);
    setSearchOpen(false);
  };

  const count = cart?.item_count ?? 0;
  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-colors duration-500 ${
        overHero ? "text-paper" : "bg-paper/95 text-ink backdrop-blur-sm shadow-[0_1px_0_#e7dac2]"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between px-4 md:h-20 md:px-10">
        <button className="lg:hidden" onClick={() => setMenu((m) => !m)} aria-label="Menu" aria-expanded={menu}>
          {menu ? <X size={20} strokeWidth={1.25} /> : <Menu size={20} strokeWidth={1.25} />}
        </button>

        <nav className="hidden gap-8 lg:flex" aria-label="Main">
          {NAV.map((n) => (
            n.to.includes("#") || n.to.includes("?") ? (
              <Link key={n.label} to={n.to} className="eyebrow link-line pb-1">{n.label}</Link>
            ) : (
              <NavLink key={n.label} to={n.to} className="eyebrow link-line pb-1" end>{n.label}</NavLink>
            )
          ))}
        </nav>

        <Link to="/" className="absolute left-1/2 -translate-x-1/2 text-center" aria-label="Vesper home">
          <span className="display block text-3xl tracking-[0.32em] md:text-4xl">VESPER</span>
          <span className="eyebrow hidden text-[0.52rem] opacity-70 md:block">Maison of independent perfumers</span>
        </Link>

        <div className="flex items-center gap-4 md:gap-6">
          <div className="hidden md:block">
            <CurrencySwitch dark={overHero} />
          </div>
          <button onClick={() => setSearchOpen((s) => !s)} aria-label="Search" aria-expanded={searchOpen}>
            <Search size={19} strokeWidth={1.25} />
          </button>
          <button onClick={() => setDrawerOpen(true)} className="relative" aria-label={`Shopping bag, ${count} items`}>
            <ShoppingBag size={19} strokeWidth={1.25} />
            {count > 0 && (
              <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-gold px-1 text-[0.6rem] font-medium text-paper">
                {count}
              </span>
            )}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {searchOpen && (
          <motion.form
            onSubmit={submit}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-champagne bg-paper text-ink"
            role="search"
          >
            <div className="mx-auto flex max-w-[1400px] items-center gap-4 px-4 py-5 md:px-10">
              <Search size={18} strokeWidth={1.25} />
              <label htmlFor="site-search" className="sr-only">Search perfumes or houses</label>
              <input
                id="site-search"
                autoFocus
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search a perfume or a house — try “oud” or “Casa Ylang”"
                className="display w-full bg-transparent text-2xl outline-none placeholder:text-sand md:text-3xl"
              />
              <button className="eyebrow link-line">Search</button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {menu && (
          <motion.nav
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="border-t border-champagne bg-paper px-4 pb-8 pt-4 text-ink lg:hidden"
            aria-label="Mobile"
          >
            {NAV.map((n) => (
              <Link key={n.label} to={n.to} className="display block border-b border-champagne py-4 text-3xl">
                {n.label}
              </Link>
            ))}
            <div className="mt-6">
              <CurrencySwitch dark={false} />
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}

function Footer() {
  return (
    <footer className="bg-ink text-champagne">
      <div className="mx-auto grid max-w-[1400px] gap-12 px-4 py-20 md:grid-cols-12 md:px-10">
        <div className="md:col-span-5">
          <p className="display text-5xl text-paper">VESPER</p>
          <p className="mt-6 max-w-sm text-sm leading-relaxed text-sand">
            A marketplace for four independent perfume houses, each limited to five compositions. Fewer bottles,
            chosen with more care.
          </p>
        </div>
        <div className="md:col-span-2">
          <p className="eyebrow mb-5 text-gold-light">Shop</p>
          <ul className="space-y-3 text-sm">
            <li><Link className="link-line" to="/shop">All fragrances</Link></li>
            <li><Link className="link-line" to="/shop?family=Floral">Florals</Link></li>
            <li><Link className="link-line" to="/shop?family=Woody">Woods</Link></li>
            <li><Link className="link-line" to="/shop?family=Gourmand">Gourmands</Link></li>
          </ul>
        </div>
        <div className="md:col-span-2">
          <p className="eyebrow mb-5 text-gold-light">Houses</p>
          <ul className="space-y-3 text-sm">
            <li><Link className="link-line" to="/houses/ombre-atlas">Ombre Atlas</Link></li>
            <li><Link className="link-line" to="/houses/casa-ylang">Casa Ylang</Link></li>
            <li><Link className="link-line" to="/houses/nordlys">Nordlys Parfum</Link></li>
            <li><Link className="link-line" to="/houses/velours-noir">Velours Noir</Link></li>
          </ul>
        </div>
        <div className="md:col-span-3">
          <p className="eyebrow mb-5 text-gold-light">Service</p>
          <ul className="space-y-3 text-sm">
            <li><Link className="link-line" to="/cart">Your bag</Link></li>
            <li>Shipping: flat ₱180 demo rate</li>
            <li>Payments: PayMongo (test mode)</li>
            <li>Rates: Frankfurter API</li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10">
        <p className="mx-auto max-w-[1400px] px-4 py-6 text-xs text-smoke md:px-10">
          University IT project demo. All houses, perfumes and prices are fictional. No real payments are processed.
        </p>
      </div>
    </footer>
  );
}

function Toasts() {
  const { toasts } = useShop();
  return (
    <div className="fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 flex-col gap-2" aria-live="polite" role="status">
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className={`px-6 py-3 text-sm shadow-lg ${t.tone === "error" ? "bg-wine text-paper" : "bg-ink text-paper"}`}
          >
            {t.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export function Layout() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) {
      window.scrollTo(0, 0);
      return;
    }
    // Sections like #discover render after data loads, so retry briefly.
    let tries = 0;
    const t = setInterval(() => {
      const el = document.getElementById(hash.slice(1));
      if (el || ++tries > 20) clearInterval(t);
      el?.scrollIntoView();
    }, 150);
    return () => clearInterval(t);
  }, [pathname, hash]);
  return (
    <>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:bg-paper focus:p-3">
        Skip to content
      </a>
      <Header />
      <motion.main
        id="main"
        key={pathname}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.45 }}
      >
        <Outlet />
      </motion.main>
      <Footer />
      <CartDrawer />
      <Toasts />
    </>
  );
}
