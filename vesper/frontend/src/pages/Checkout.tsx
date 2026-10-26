import { CreditCard, Lock, Smartphone, Wallet } from "lucide-react";
import { useEffect, useState, type FormEvent, type InputHTMLAttributes } from "react";
import { Link } from "react-router";
import { Bottle } from "../components/Bottle";
import { Totals } from "../components/CartDrawer";
import { Loading } from "../components/States";
import { api, ApiError, type Order } from "../lib/api";
import { formatMinor } from "../lib/money";
import { useShop } from "../lib/store";

type Form = { name: string; email: string; phone: string; address: string };
const METHODS = [
  { id: "card", label: "Credit / debit card", icon: CreditCard },
  { id: "gcash", label: "GCash", icon: Smartphone },
  { id: "paymaya", label: "Maya", icon: Wallet },
] as const;

export function validate(f: Form): Partial<Form> {
  const e: Partial<Form> = {};
  if (f.name.trim().length < 2) e.name = "Please enter your full name.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(f.email.trim())) e.email = "Please enter a valid email address.";
  if (!/^(\+63|0)\d{9,10}$/.test(f.phone.replace(/[\s-]/g, ""))) e.phone = "Enter a Philippine number, e.g. 0917 123 4567.";
  if (f.address.trim().length < 10) e.address = "Please enter your complete shipping address.";
  return e;
}

export default function Checkout() {
  const { cart, price } = useShop();
  const [form, setForm] = useState<Form>({ name: "", email: "", phone: "", address: "" });
  const [method, setMethod] = useState<(typeof METHODS)[number]["id"]>("card");
  const [errors, setErrors] = useState<Partial<Form>>({});
  const [touched, setTouched] = useState(false);
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [mode, setMode] = useState<string | null>(null);

  useEffect(() => {
    api<{ payment_mode: string }>("/health").then((h) => setMode(h.payment_mode)).catch(() => setMode(null));
  }, []);
  useEffect(() => {
    if (touched) setErrors(validate(form));
  }, [form, touched]);

  if (!cart) return <div className="pt-24"><Loading /></div>;
  if (cart.items.length === 0)
    return (
      <div className="mx-auto max-w-xl px-4 pb-24 pt-40 text-center">
        <h1 className="display text-5xl">Nothing to check out</h1>
        <p className="mt-3 text-sm text-smoke">Your bag is empty.</p>
        <Link to="/shop" className="btn btn-dark mt-8">Explore fragrances</Link>
      </div>
    );

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setTouched(true);
    const errs = validate(form);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setBusy(true);
    setServerError(null);
    try {
      const res = await api<{ order: Order; checkout_url: string }>("/checkout", {
        method: "POST",
        json: { cart_id: cart.id, customer: form, payment_method: method },
      });
      // Leaves the SPA: PayMongo hosted checkout (or the local mock gateway).
      window.location.assign(res.checkout_url);
    } catch (err) {
      const apiErr = err as ApiError;
      setServerError(apiErr.message);
      if (apiErr.fields) setErrors((x) => ({ ...x, ...apiErr.fields }));
      setBusy(false);
    }
  };

  const field = (key: keyof Form, label: string, props: InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div>
      <label htmlFor={key} className="eyebrow text-smoke">{label}</label>
      <input
        id={key}
        className="field"
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        aria-invalid={!!errors[key]}
        aria-describedby={errors[key] ? `${key}-err` : undefined}
        {...props}
      />
      {errors[key] && <p id={`${key}-err`} className="mt-1 text-xs text-wine">{errors[key]}</p>}
    </div>
  );

  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-24 pt-28 md:px-10 md:pt-36">
      <h1 className="display text-6xl md:text-7xl">Checkout</h1>
      <form onSubmit={submit} noValidate className="mt-12 grid gap-14 md:grid-cols-12">
        <div className="space-y-12 md:col-span-7">
          <fieldset className="space-y-6">
            <legend className="eyebrow mb-6 text-gold">01 — Contact</legend>
            {field("name", "Full name", { autoComplete: "name" })}
            <div className="grid gap-6 md:grid-cols-2">
              {field("email", "Email address", { type: "email", autoComplete: "email" })}
              {field("phone", "Contact number", { type: "tel", autoComplete: "tel", placeholder: "0917 123 4567" })}
            </div>
          </fieldset>
          <fieldset className="space-y-6">
            <legend className="eyebrow mb-6 text-gold">02 — Shipping address</legend>
            {field("address", "Street, barangay, city, province, postal code", { autoComplete: "street-address" })}
          </fieldset>
          <fieldset>
            <legend className="eyebrow mb-6 text-gold">03 — Payment method</legend>
            <div className="grid gap-3 md:grid-cols-3">
              {METHODS.map((m) => (
                <label key={m.id} className={`flex cursor-pointer items-center gap-3 border p-4 text-sm transition-colors ${method === m.id ? "border-ink bg-ivory" : "border-champagne hover:border-sand"}`}>
                  <input type="radio" name="method" value={m.id} checked={method === m.id} onChange={() => setMethod(m.id)} className="accent-ink" />
                  <m.icon size={16} strokeWidth={1.25} /> {m.label}
                </label>
              ))}
            </div>
            <p className="mt-4 flex items-start gap-2 text-xs text-smoke">
              <Lock size={12} className="mt-0.5 shrink-0" />
              {mode === "mock"
                ? "Local mock-payment mode: you will see a clearly labelled demo payment page. No PayMongo call, no real money."
                : "You will be redirected to PayMongo's secure hosted checkout (test mode — use PayMongo test cards). No real money is charged."}
            </p>
          </fieldset>
        </div>

        <aside className="h-fit bg-ivory p-8 md:sticky md:top-28 md:col-span-5">
          <p className="eyebrow mb-6">Order summary</p>
          <ul className="mb-6 space-y-4">
            {cart.items.map((i) => (
              <li key={i.product.id} className="flex items-center gap-4">
                <Bottle product={i.product} seller={i.product.seller} className="w-12 shrink-0" />
                <div className="flex-1 text-sm">
                  <p className="display text-lg">{i.product.name}</p>
                  <p className="text-xs text-smoke">{i.product.seller.name} · × {i.quantity}</p>
                </div>
                <span className="text-sm tabular-nums">{price(i.line_total_centavos)}</span>
              </li>
            ))}
          </ul>
          <Totals />
          {serverError && <p className="mt-6 border-l-2 border-wine pl-3 text-sm text-wine" role="alert">{serverError}</p>}
          <button className="btn btn-dark mt-8 w-full" disabled={busy}>
            {busy ? "Securing your order…" : `Pay ${formatMinor(cart.total_centavos, "PHP")}`}
          </button>
          <p className="mt-3 text-center text-[0.7rem] text-smoke">Totals are recalculated on our server before payment.</p>
        </aside>
      </form>
    </div>
  );
}
