import { InputNumber, Switch, Select } from "antd";
import type { TariffPrice } from "../api/types";

const CURRENCY_OPTIONS = [
  { value: "⭐️", label: "⭐️ Stars" },
  { value: "USDT", label: "USDT" },
  { value: "RUB", label: "RUB" },
];

interface TariffPriceMatrixProps {
  prices: TariffPrice[];
  onChange: (prices: TariffPrice[]) => void;
}

export default function TariffPriceMatrix({ prices, onChange }: TariffPriceMatrixProps) {
  const update = (index: number, field: keyof TariffPrice, value: unknown) => {
    const next = prices.map((p, i) => (i === index ? { ...p, [field]: value } : p));
    onChange(next);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "140px 120px 100px 60px",
          gap: 8,
          fontSize: 12,
          color: "rgba(255,255,255,0.45)",
          fontWeight: 600,
          padding: "0 4px",
        }}
      >
        <span>Payment Method</span>
        <span>Price</span>
        <span>Currency</span>
        <span>Active</span>
      </div>
      {prices.map((price, idx) => (
        <div
          key={price.payment_method}
          style={{
            display: "grid",
            gridTemplateColumns: "140px 120px 100px 60px",
            gap: 8,
            alignItems: "center",
            padding: "4px",
            borderRadius: 6,
            background: "rgba(255,255,255,0.02)",
          }}
        >
          <span style={{ fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
            {price.payment_method}
          </span>
          <InputNumber
            size="small"
            min={0}
            step={0.01}
            value={price.price}
            onChange={(v) => update(idx, "price", v ?? 0)}
            style={{ width: "100%" }}
          />
          <Select
            size="small"
            value={price.currency}
            onChange={(v) => update(idx, "currency", v)}
            options={CURRENCY_OPTIONS}
            style={{ width: "100%" }}
          />
          <Switch
            size="small"
            checked={price.is_active}
            onChange={(v) => update(idx, "is_active", v)}
          />
        </div>
      ))}
    </div>
  );
}
