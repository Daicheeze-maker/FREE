export type Currency = "PHP" | "USD";

const SYMBOL: Record<Currency, string> = { PHP: "₱", USD: "$" };

/** PHP centavos -> target minor units using exact integer math, rounded half-up (matches the backend's Decimal). */
export function convertCentavos(centavos: number, rate: string): number {
  const [int, frac = ""] = rate.split(".");
  const numerator = BigInt(int + frac);
  const denominator = 10n ** BigInt(frac.length);
  const n = BigInt(centavos) * numerator;
  let q = n / denominator;
  if ((n % denominator) * 2n >= denominator) q += 1n;
  return Number(q);
}

export function formatMinor(minor: number, currency: Currency): string {
  const major = Math.floor(minor / 100).toLocaleString("en-US");
  return `${SYMBOL[currency]}${major}.${String(minor % 100).padStart(2, "0")}`;
}

export function formatPrice(centavos: number, currency: Currency, rate: string | null): string {
  if (currency === "PHP" || !rate) return formatMinor(centavos, "PHP");
  return formatMinor(convertCentavos(centavos, rate), currency);
}
