import { marked } from "marked";
import katex from "katex";
import "katex/dist/katex.min.css";

marked.setOptions({ gfm: true, breaks: true });

export function renderMd(text) {
  if (!text) return "";

  const mathPlaceholders = [];

  let processed = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), {
        displayMode: true,
        throwOnError: false,
      });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`<span class="katex-error">$$${expr}$$</span>`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  processed = processed.replace(/\$([^\$\n]+?)\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), {
        displayMode: false,
        throwOnError: false,
      });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`<span class="katex-error">$${expr}$</span>`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  let html = marked.parse(processed);

  html = html.replace(
    /%%MATH_BLOCK_(\d+)%%/g,
    (_, idx) => mathPlaceholders[parseInt(idx)],
  );

  return html;
}
