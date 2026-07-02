import { marked } from "marked";
import katex from "katex";
import "katex/dist/katex.min.css";

marked.setOptions({ gfm: true, breaks: true });

export function renderMd(text, highlightLinks = false) {
  if (!text) return "";

  const mathPlaceholders = [];

  let processed = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), {
        displayMode: true,
        throwOnError: true,
      });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`$$${expr}$$`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  processed = processed.replace(/\$([^\$\n]+?)\$/g, (_, expr) => {
    try {
      const html = katex.renderToString(expr.trim(), {
        displayMode: false,
        throwOnError: true,
      });
      mathPlaceholders.push(html);
    } catch {
      mathPlaceholders.push(`$${expr}$`);
    }
    return `%%MATH_BLOCK_${mathPlaceholders.length - 1}%%`;
  });

  let html = marked.parse(processed);

  if (highlightLinks) {
    html = html.replace(
      /<a\s+(.+?)>/g,
      '<a class="doc-link" target="_blank" rel="noopener noreferrer" $1>',
    );
  }

  html = html.replace(
    /%%MATH_BLOCK_(\d+)%%/g,
    (_, idx) => mathPlaceholders[parseInt(idx)],
  );

  return html;
}
