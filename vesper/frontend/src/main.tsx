import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import "./index.css";
import { Layout } from "./components/Layout";
import { ShopProvider } from "./lib/store";
import CartPage from "./pages/CartPage";
import Checkout from "./pages/Checkout";
import Home from "./pages/Home";
import { HousesIndex, SellerPage } from "./pages/Houses";
import { MockPay, OrderPage } from "./pages/Payment";
import ProductPage from "./pages/ProductPage";
import Shop from "./pages/Shop";

function NotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-6 px-4 pt-24 text-center">
      <p className="display text-8xl">404</p>
      <p className="text-smoke">This page has evaporated.</p>
      <Link to="/" className="btn btn-dark">Return home</Link>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ShopProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="shop" element={<Shop />} />
            <Route path="product/:id" element={<ProductPage />} />
            <Route path="houses" element={<HousesIndex />} />
            <Route path="houses/:id" element={<SellerPage />} />
            <Route path="cart" element={<CartPage />} />
            <Route path="checkout" element={<Checkout />} />
            <Route path="pay/mock/:id" element={<MockPay />} />
            <Route path="order/:id" element={<OrderPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </ShopProvider>
    </BrowserRouter>
  </StrictMode>,
);
