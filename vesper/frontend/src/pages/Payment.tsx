import { motion } from "motion/react";
import { Check, CircleAlert, Clock } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { ErrorState, Loading } from "../components/States";
import { api, type Order } from "../lib/api";
import { formatMinor } from "../lib/money";
import { useShop } from "../lib/store";

/** Local stand-in for PayMongo's hosted page, only reachable when the backend runs PAYMENT_MODE=mock. */
export function MockPay() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Order>(`/orders/${id}`).then(setOrder).catch((e: Error) => setError(e.message));
  }, [id]);

  const pay = async (outcome: "paid" | "failed") => {
    setBusy(true);
    try {
      await api(`/payments/mock/${id}`, { method: "POST", json: { outcome } });
      navigate(`/order/${id}?result=${outcome === "paid" ? "success" : "failed"}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  if (error) return <div className="pt-24"><ErrorState message={error} /></div>;
  if (!order) return <div className="pt-24"><Loading /></div>;
  return (
    <div className="flex min-h-screen items-center justify-center bg-ivory px-4 pt-20">
      <div className="w-full max-w-md border border-dashed border-gold bg-paper p-10">
        <p className="eyebrow bg-gold px-3 py-1 text-center text-paper">Mock payment gateway · demo only</p>
        <h1 className="display mt-8 text-4xl">Simulated checkout</h1>
        <p className="mt-3 text-sm text-smoke">
          PayMongo credentials are not configured, so this local page stands in for the hosted checkout. Choose an
          outcome to test both paths. No money moves.
        </p>
        <dl className="mt-8 space-y-2 border-y border-champagne py-5 text-sm">
          <div className="flex justify-between"><dt>Order</dt><dd className="font-mono">{order.id}</dd></div>
          <div className="flex justify-between"><dt>Method</dt><dd className="uppercase">{order.payment_method}</dd></div>
          <div className="display flex justify-between pt-2 text-2xl"><dt>Amount</dt><dd>{formatMinor(order.total_centavos, "PHP")}</dd></div>
        </dl>
        {order.status === "pending" || order.status === "failed" ? (
          <div className="mt-8 grid gap-3">
            <button className="btn btn-dark" disabled={busy} onClick={() => pay("paid")}>Simulate successful payment</button>
            <button className="btn btn-ghost" disabled={busy} onClick={() => pay("failed")}>Simulate failed payment</button>
          </div>
        ) : (
          <Link to={`/order/${order.id}`} className="btn btn-dark mt-8 w-full">This order is already {order.status}</Link>
        )}
      </div>
    </div>
  );
}

export function OrderPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const { refreshCart } = useShop();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempts, setAttempts] = useState(0);

  const verify = useCallback(async () => {
    try {
      // Server asks PayMongo for the real status; the ?result= query is only a hint for messaging.
      const o = await api<Order>(`/orders/${id}/verify`, { method: "POST" });
      setOrder(o);
      if (o.status === "paid") refreshCart();
      return o;
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id, refreshCart]);

  useEffect(() => {
    verify();
  }, [verify]);
  // Webhooks can lag a few seconds behind the redirect: poll briefly while pending.
  useEffect(() => {
    if (order?.status !== "pending" || params.get("result") !== "success" || attempts >= 6) return;
    const t = setTimeout(() => verify().then(() => setAttempts((a) => a + 1)), 2500);
    return () => clearTimeout(t);
  }, [order, attempts, params, verify]);

  if (error && !order) return <div className="pt-24"><ErrorState message={error} /></div>;
  if (!order) return <div className="pt-24"><Loading label="Confirming your payment" /></div>;

  const cancelled = params.get("result") === "cancelled";
  const view = {
    paid: { icon: Check, eyebrow: "Payment confirmed", title: "Thank you.", text: `Your payment was verified and your order is confirmed. Keep your order number for reference (no emails are sent in this demo).` },
    failed: { icon: CircleAlert, eyebrow: "Payment failed", title: "Payment didn’t go through.", text: "No money was taken. Your bag is still saved — you can try again with another method." },
    cancelled: { icon: CircleAlert, eyebrow: "Order cancelled", title: "Order cancelled.", text: "No payment was taken." },
    pending: cancelled
      ? { icon: CircleAlert, eyebrow: "Payment cancelled", title: "You left the payment page.", text: "No money was taken. Your bag is still saved whenever you are ready." }
      : { icon: Clock, eyebrow: "Awaiting confirmation", title: "Confirming with PayMongo…", text: attempts >= 6 ? "We haven't received confirmation yet. Refresh this page in a minute — your order will update once PayMongo confirms." : "This usually takes a few seconds. Please keep this page open." },
  }[order.status];

  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 pt-32 md:pt-40">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8 }}>
        <view.icon size={36} strokeWidth={1} className={order.status === "paid" ? "text-gold" : "text-wine"} />
        <p className="eyebrow mt-6 text-gold">{view.eyebrow}</p>
        <h1 className="display mt-3 text-6xl" role="status">{view.title}</h1>
        <p className="mt-4 text-smoke">{view.text}</p>
      </motion.div>

      <div className="mt-12 border-t border-champagne pt-8">
        <div className="flex flex-wrap justify-between gap-4 text-sm">
          <p>Order <span className="font-mono">{order.id}</span></p>
          <p className="eyebrow">Status: {order.status} · Payment: {order.payment_status} ({order.payment_provider === "mock" ? "mock gateway" : "PayMongo test"})</p>
        </div>
        <ul className="mt-8 divide-y divide-champagne">
          {order.items.map((i) => (
            <li key={i.product_id} className="flex justify-between py-4 text-sm">
              <span><span className="display text-xl">{i.name}</span> <span className="text-smoke">— {i.seller_name} × {i.quantity}</span></span>
              <span className="tabular-nums">{formatMinor(i.unit_price_centavos * i.quantity, "PHP")}</span>
            </li>
          ))}
        </ul>
        <dl className="mt-4 space-y-2 border-t border-champagne pt-4 text-sm">
          <div className="flex justify-between"><dt>Subtotal</dt><dd>{formatMinor(order.subtotal_centavos, "PHP")}</dd></div>
          <div className="flex justify-between"><dt>Shipping (demo rate)</dt><dd>{formatMinor(order.shipping_centavos, "PHP")}</dd></div>
          <div className="display flex justify-between text-2xl"><dt>Total charged in PHP</dt><dd>{formatMinor(order.total_centavos, "PHP")}</dd></div>
        </dl>
      </div>
      <div className="mt-12 flex flex-wrap gap-4">
        {order.status === "paid" ? (
          <Link to="/shop" className="btn btn-dark">Continue shopping</Link>
        ) : (
          <Link to="/checkout" className="btn btn-dark">Return to checkout</Link>
        )}
        <Link to="/" className="btn btn-ghost">Back to home</Link>
      </div>
    </div>
  );
}
