const ALLOWED_TAGS = new Set([
  "b", "i", "u", "a", "code", "em", "strong", "br", "pre", "s", "strike",
]);

const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(["href"]),
};

/**
 * Sanitize HTML to only allow Telegram-safe tags.
 * Strips all tags/attributes not in the whitelist.
 */
export function sanitizeTelegramHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");

  function walk(node: Node): string {
    if (node.nodeType === Node.TEXT_NODE) {
      return (node.textContent ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    if (node.nodeType !== Node.ELEMENT_NODE) return "";

    const el = node as Element;
    const tag = el.tagName.toLowerCase();

    const childrenHtml = Array.from(el.childNodes).map(walk).join("");

    if (!ALLOWED_TAGS.has(tag)) return childrenHtml;

    const allowedAttrs = ALLOWED_ATTRS[tag];
    let attrs = "";
    if (allowedAttrs) {
      for (const attr of Array.from(el.attributes)) {
        if (allowedAttrs.has(attr.name)) {
          const val = attr.value.replace(/"/g, "&quot;");
          // Only allow safe href protocols
          if (attr.name === "href" && !/^https?:\/\//i.test(val)) continue;
          attrs += ` ${attr.name}="${val}"`;
        }
      }
    }

    if (tag === "br") return "<br/>";

    return `<${tag}${attrs}>${childrenHtml}</${tag}>`;
  }

  return Array.from(doc.body.childNodes).map(walk).join("");
}
