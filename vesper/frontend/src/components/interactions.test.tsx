import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { validate } from "../pages/Checkout";
import { QuantitySelector } from "./CartDrawer";

function Harness({ max }: { max: number }) {
  const [n, setN] = useState(1);
  return <QuantitySelector value={n} max={max} onChange={setN} label="Fjord" />;
}

test("quantity selector stops at stock and at 1", async () => {
  render(<Harness max={3} />);
  const inc = screen.getByLabelText("Increase quantity");
  const dec = screen.getByLabelText("Decrease quantity");
  expect(dec).toBeDisabled();
  await userEvent.click(inc);
  await userEvent.click(inc);
  expect(screen.getByText("3")).toBeInTheDocument();
  expect(inc).toBeDisabled();
  await userEvent.click(dec);
  expect(screen.getByText("2")).toBeInTheDocument();
});

test("checkout validation flags each bad field and accepts a good form", () => {
  expect(Object.keys(validate({ name: "", email: "x", phone: "123", address: "short" })).sort()).toEqual(
    ["address", "email", "name", "phone"],
  );
  expect(validate({ name: "Maria Santos", email: "maria@example.com", phone: "0917 123 4567", address: "12 Acacia St, Pasig City" })).toEqual({});
  expect(validate({ name: "Maria", email: "m@example.com", phone: "+639171234567", address: "12 Acacia St, Pasig City" })).toEqual({});
});
