import { esc } from "./api.js";

/* tiny markdown renderer (headers, bold, code, tables, lists).
   Input is HTML-escaped first, so the output is safe for innerHTML. */
export function md(src) {
  const lines = esc(src).split("\n");
  let html = "",
    inTable = false,
    inList = false;
  const flush = () => {
    if (inTable) { html += "</table>"; inTable = false; }
    if (inList) { html += "</ul>"; inList = false; }
  };
  const inline = (s) =>
    s.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")
     .replace(/`([^`]+)`/g, "<code>$1</code>");

  for (const ln of lines) {
    if (/^\s*\|.*\|\s*$/.test(ln)) {
      if (/^\s*\|[\s\-:|]+\|\s*$/.test(ln)) continue;
      const cells = ln.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      if (!inTable) {
        flush(); html += "<table>"; inTable = true;
        html += "<tr>" + cells.map((c) => "<th>" + inline(c) + "</th>").join("") + "</tr>";
      } else {
        html += "<tr>" + cells.map((c) => {
          const num = /^[-+]?[\d,.$%()]+$/.test(c.replace(/\*\*/g, ""));
          return `<td class="${num ? "num" : ""}">` + inline(c) + "</td>";
        }).join("") + "</tr>";
      }
      continue;
    }
    if (/^#{1,4}\s/.test(ln)) { flush(); html += "<h3>" + inline(ln.replace(/^#+\s*/, "")) + "</h3>"; continue; }
    if (/^\s*[-*]\s+/.test(ln)) {
      if (!inList) { flush(); html += "<ul>"; inList = true; }
      html += "<li>" + inline(ln.replace(/^\s*[-*]\s+/, "")) + "</li>";
      continue;
    }
    if (/^\s*(---|\*\*\*)\s*$/.test(ln)) { flush(); continue; }
    if (ln.trim() === "") { flush(); continue; }
    flush(); html += "<p>" + inline(ln) + "</p>";
  }
  flush();
  return html;
}
