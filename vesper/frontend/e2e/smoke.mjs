// End-to-end smoke test of the real app (needs backend on :8000 in PAYMENT_MODE=mock and `npm run dev`).
// Run: node e2e/smoke.mjs [screenshotDir]
import { createRequire } from "node:module";
import assert from "node:assert/strict";

// require() so a globally installed Playwright (NODE_PATH) also works.
const { chromium } = createRequire(import.meta.url)("playwright");

const BASE = process.env.BASE_URL ?? "http://localhost:5173";
const shots = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const snap = async (name) => {
  if (!shots) return;
  // Scroll through first so scroll-triggered reveals have played.
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 60)); }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
};
const step = (msg) => console.log("✓", msg);

await page.goto(BASE);
await page.getByRole("heading", { name: /Wear the/ }).waitFor();
await page.getByText("The bestsellers").waitFor();
await page.waitForTimeout(1800);
await snap("01-home");
step("homepage renders with live data");

await page.goto(`${BASE}/shop`);
await page.getByText("20 of 20 fragrances").waitFor();
await page.getByLabel("Search by perfume or house").fill("fjord");
await page.getByText("1 of 20 fragrances").waitFor();
await page.getByLabel("Search by perfume or house").fill("");
await page.getByRole("checkbox", { name: "Velours Noir" }).click();
await page.getByText("5 of 20 fragrances").waitFor(); // URL-driven state commits in a transition, so click() + wait on result
await page.getByRole("checkbox", { name: "Gourmand" }).click();
await page.getByText("2 of 20 fragrances").waitFor();
step("search and seller+family filters narrow results");
await page.getByText("Clear all filters").click();
await page.locator("select").last().selectOption("price_asc");
await page.getByText("20 of 20 fragrances").waitFor();
await page.waitForTimeout(800);
const first = await page.locator("article h3").first().textContent();
assert.equal(first, "Calamansi & Salt"); // cheapest at PHP 4,800
await snap("02-shop");
step("sort by price ascending puts the cheapest first");

await page.locator("article").first().getByRole("button", { name: "Quick view" }).click();
await page.getByRole("dialog", { name: /Quick view/ }).waitFor();
await page.keyboard.press("Escape");
step("quick view opens and closes with Escape");

await page.goto(`${BASE}/product/nordlys-fjord`);
await page.getByRole("heading", { name: "Fjord", level: 1 }).waitFor();
await page.getByRole("tab", { name: "Evening" }).click();
await page.getByLabel("Increase quantity").click();
await page.getByRole("button", { name: "Add to bag" }).first().click();
await page.getByText("Fjord added to your bag").waitFor();
await page.waitForTimeout(600);
await snap("03-product");
step("product page: gallery, quantity, add to bag");

await page.goto(`${BASE}/product/atlas-medina-rose`);
assert.equal(await page.getByRole("button", { name: "Sold out" }).first().isDisabled(), true);
step("sold-out product cannot be added");

await page.goto(`${BASE}/houses/casa-ylang`);
await page.getByRole("heading", { name: "Casa Ylang", level: 1 }).waitFor();
assert.equal(await page.locator("article").count(), 5);
await page.waitForTimeout(1500);
await snap("04-house");
step("seller storefront lists its 5 products");

await page.goto(`${BASE}/cart`);
await page.reload();
await page.getByText("Summary · 2 items").waitFor();
await page.getByLabel("Increase quantity").click();
await page.getByText("Summary · 3 items").waitFor();
await page.getByLabel("Decrease quantity").click();
await page.getByText("Summary · 2 items").waitFor();
await snap("05-cart");
step("cart survives reload; quantity up/down updates totals");

await page.locator("#currency").selectOption("USD");
await page.waitForTimeout(1500);
const note = await page.locator("main").textContent();
const usdOk = note.includes("1 PHP =");
const fallback = note.includes("Exchange rate unavailable");
assert.ok(usdOk || fallback, "currency switch shows either a rate or the PHP fallback notice");
step(usdOk ? "currency switched to USD with live rate" : "Frankfurter unreachable -> PHP fallback notice shown");
await page.locator("#currency").selectOption("PHP");

await page.goto(`${BASE}/checkout`);
await page.getByRole("button", { name: /^Pay/ }).click();
await page.getByText("Please enter your full name.").waitFor();
await page.getByText("Please enter a valid email address.").waitFor();
step("checkout validation blocks an empty form");
await page.getByLabel("Full name").fill("Maria Santos");
await page.getByLabel("Email address").fill("maria@example.com");
await page.getByLabel("Contact number").fill("0917 123 4567");
await page.getByLabel(/Street, barangay/).fill("12 Acacia St, Brgy. San Antonio, Pasig City 1605");
await page.getByRole("radio", { name: "GCash" }).check();
await snap("06-checkout");
await page.getByRole("button", { name: "Pay ₱15,980.00" }).click();
await page.getByText("Mock payment gateway · demo only").waitFor();
await snap("07-mockpay");
await page.getByRole("button", { name: "Simulate successful payment" }).click();
await page.getByRole("status").filter({ hasText: "Thank you." }).waitFor();
await page.getByText("Status: paid · Payment: paid").waitFor();
await snap("08-confirmation");
step("checkout -> mock gateway -> paid confirmation");

const stock = await (await fetch("http://localhost:8000/api/products/nordlys-fjord")).json();
console.log("  Fjord stock after purchase:", stock.product.stock);
await page.goto(`${BASE}/cart`);
await page.getByText("Your bag is empty.").waitFor();
step("cart cleared after verified payment");

await page.setViewportSize({ width: 390, height: 844 });
await page.goto(BASE);
await page.getByRole("button", { name: "Menu" }).click();
await page.getByRole("navigation", { name: "Mobile" }).waitFor();
await page.waitForTimeout(800);
await snap("09-mobile-menu");
await page.goto(`${BASE}/shop`);
await page.waitForTimeout(1000);
await snap("10-mobile-shop");
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
assert.equal(overflow, false, "no horizontal scroll on mobile");
step("mobile menu works, no horizontal overflow");

assert.deepEqual(errors, [], "no uncaught page errors");
await browser.close();
console.log("E2E smoke: all steps passed");
