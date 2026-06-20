import { BRAND_LOGO } from "../branding";
import CheezyLogo from "./CheezyLogo";

interface Props {
  size?: number;
  style?: React.CSSProperties;
}

export default function BrandLogo({ size = 36, style }: Props) {
  if (BRAND_LOGO) {
    return (
      <img
        src={BRAND_LOGO}
        alt="logo"
        width={size}
        height={size}
        style={{ objectFit: "contain", ...style }}
      />
    );
  }
  return <CheezyLogo size={size} style={style} />;
}
