import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type Cart, type Rate } from "./api";
import { formatPrice, type Currency } from "./money";

const CART_KEY = "vesper.cart";
const CURRENCY_KEY = "vesper.currency";

function load(key: string) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function save(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: cart still works for this tab */
  }
}

type Toast = { id: number; text: string; tone: "ok" | "error" };

type Shop = {
  cart: Cart | null;
  cartBusy: string | null; // product id currently being changed
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  addToCart: (productId: string, quantity?: number, name?: string) => Promise<boolean>;
  setQuantity: (productId: string, quantity: number) => Promise<void>;
  removeItem: (productId: string) => Promise<void>;
  refreshCart: () => Promise<void>;
  currency: Currency;
  setCurrency: (c: Currency) => void;
  rate: Rate | null;
  rateError: string | null;
  rateLoading: boolean;
  price: (centavos: number) => string;
  toasts: Toast[];
  notify: (text: string, tone?: Toast["tone"]) => void;
};

const ShopContext = createContext<Shop | null>(null);

export function ShopProvider({ children }: { children: ReactNode }) {
  const [cart, setCart] = useState<Cart | null>(null);
  const [cartBusy, setCartBusy] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [currency, setCurrencyState] = useState<Currency>(load(CURRENCY_KEY) === "USD" ? "USD" : "PHP");
  const [rate, setRate] = useState<Rate | null>(null);
  const [rateError, setRateError] = useState<string | null>(null);
  const [rateLoading, setRateLoading] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((text: string, tone: Toast["tone"] = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800);
  }, []);

  const newCart = useCallback(async () => {
    const c = await api<Cart>("/carts", { method: "POST" });
    save(CART_KEY, c.id);
    setCart(c);
    return c;
  }, []);

  const refreshCart = useCallback(async () => {
    const id = load(CART_KEY);
    if (!id) return void (await newCart());
    try {
      setCart(await api<Cart>(`/carts/${id}`));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) await newCart();
      else notify((e as Error).message, "error");
    }
  }, [newCart, notify]);

  useEffect(() => {
    refreshCart();
  }, [refreshCart]);

  const mutate = useCallback(
    async (productId: string, run: (cartId: string) => Promise<Cart>) => {
      setCartBusy(productId);
      try {
        const id = cart?.id ?? (await newCart()).id;
        setCart(await run(id));
        return true;
      } catch (e) {
        notify((e as Error).message, "error");
        return false;
      } finally {
        setCartBusy(null);
      }
    },
    [cart, newCart, notify],
  );

  const addToCart = useCallback(
    async (productId: string, quantity = 1, name?: string) => {
      const ok = await mutate(productId, (id) =>
        api(`/carts/${id}/items`, { method: "POST", json: { product_id: productId, quantity } }),
      );
      if (ok) notify(`${name ?? "Item"} added to your bag`);
      return ok;
    },
    [mutate, notify],
  );

  const setQuantity = useCallback(
    async (productId: string, quantity: number) => {
      await mutate(productId, (id) => api(`/carts/${id}/items/${productId}`, { method: "PATCH", json: { quantity } }));
    },
    [mutate],
  );

  const removeItem = useCallback(
    async (productId: string) => {
      await mutate(productId, (id) => api(`/carts/${id}/items/${productId}`, { method: "DELETE" }));
    },
    [mutate],
  );

  useEffect(() => {
    save(CURRENCY_KEY, currency);
    if (currency === "PHP") {
      setRateError(null);
      return;
    }
    let cancelled = false;
    setRateLoading(true);
    api<Rate>(`/currency/rate?to=${currency}`)
      .then((r) => !cancelled && (setRate(r), setRateError(null)))
      .catch((e: Error) => !cancelled && (setRate(null), setRateError(e.message)))
      .finally(() => !cancelled && setRateLoading(false));
    return () => {
      cancelled = true;
    };
  }, [currency]);

  const activeRate = currency !== "PHP" && rate?.quote === currency ? rate.rate : null;
  const price = useCallback((c: number) => formatPrice(c, currency, activeRate), [currency, activeRate]);

  return (
    <ShopContext.Provider
      value={{
        cart, cartBusy, drawerOpen, setDrawerOpen, addToCart, setQuantity, removeItem, refreshCart,
        currency, setCurrency: setCurrencyState, rate, rateError, rateLoading, price, toasts, notify,
      }}
    >
      {children}
    </ShopContext.Provider>
  );
}

export function useShop() {
  const ctx = useContext(ShopContext);
  if (!ctx) throw new Error("useShop outside ShopProvider");
  return ctx;
}
