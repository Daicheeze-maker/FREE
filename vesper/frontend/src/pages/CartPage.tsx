import { Link } from "react-router";
import { CartLines, Totals } from "../components/CartDrawer";
import { Loading } from "../components/States";
import { useShop } from "../lib/store";

export default function CartPage() {
  const { cart } = useShop();
  const overStock = cart?.items.some((i) => i.quantity > i.product.stock);
  return (
    <div className="mx-auto max-w-[1400px] px-4 pb-24 pt-28 md:px-10 md:pt-36">
      <h1 className="display text-6xl md:text-8xl">Your bag</h1>
      {!cart ? (
        <Loading />
      ) : cart.items.length === 0 ? (
        <div className="py-24 text-center">
          <p className="display text-4xl">Your bag is empty.</p>
          <p className="mt-3 text-sm text-smoke">Your bag is saved on this device, so you can come back to it anytime.</p>
          <Link to="/shop" className="btn btn-dark mt-8">Explore fragrances</Link>
        </div>
      ) : (
        <div className="mt-12 grid gap-12 md:grid-cols-12">
          <div className="md:col-span-8"><CartLines items={cart.items} /></div>
          <aside className="h-fit space-y-6 bg-ivory p-8 md:sticky md:top-28 md:col-span-4">
            <p className="eyebrow">Summary · {cart.item_count} items</p>
            <Totals />
            {overStock ? (
              <button className="btn btn-dark w-full" disabled>Adjust quantities to continue</button>
            ) : (
              <Link to="/checkout" className="btn btn-dark w-full">Proceed to checkout</Link>
            )}
            <Link to="/shop" className="eyebrow link-line mx-auto block w-fit">Continue shopping</Link>
          </aside>
        </div>
      )}
    </div>
  );
}
