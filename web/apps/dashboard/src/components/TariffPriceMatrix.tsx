import { Input } from "@xray/ui/components/input";
import { Switch } from "@xray/ui/components/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@xray/ui/components/select";
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
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-[140px_120px_100px_60px] gap-2 px-1 text-xs font-semibold text-muted-foreground">
        <span>Payment Method</span>
        <span>Price</span>
        <span>Currency</span>
        <span>Active</span>
      </div>
      {prices.map((price, idx) => (
        <div
          key={price.payment_method}
          className="grid grid-cols-[140px_120px_100px_60px] items-center gap-2 rounded-md bg-white/[0.02] p-1"
        >
          <span className="text-[13px] text-foreground/70">{price.payment_method}</span>
          <Input
            type="number"
            className="h-8"
            min={0}
            step={0.01}
            value={price.price}
            onChange={(e) => update(idx, "price", e.target.value === "" ? 0 : Number(e.target.value))}
          />
          <Select
            value={price.currency}
            onValueChange={(v: string) => update(idx, "currency", v)}
          >
            <SelectTrigger className="h-8">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CURRENCY_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Switch
            checked={price.is_active}
            onCheckedChange={(v: boolean) => update(idx, "is_active", v)}
          />
        </div>
      ))}
    </div>
  );
}
