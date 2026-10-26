import { convertCentavos, formatMinor, formatPrice } from "./money";

test("converts PHP centavos with exact half-up rounding", () => {
  expect(convertCentavos(680000, "0.01724")).toBe(11723); // 117.232 -> 117.23
  expect(convertCentavos(1, "12.5")).toBe(13); // 0.125 -> 0.13
  expect(convertCentavos(2168000, "0.01724")).toBe(37376); // same as backend cart total test
});

test("formats currency with symbol and grouping", () => {
  expect(formatMinor(1850000, "PHP")).toBe("₱18,500.00");
  expect(formatMinor(5, "USD")).toBe("$0.05");
});

test("falls back to PHP when no rate is available", () => {
  expect(formatPrice(680000, "USD", null)).toBe("₱6,800.00");
  expect(formatPrice(680000, "USD", "0.01724")).toBe("$117.23");
});
