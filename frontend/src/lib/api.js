export const BB_API = "https://api.butterbase.ai";
export const APP_ID = "app_x89ezf73vxrn";
export const PRODUCT_ID = "5d385dad-e200-4ca3-b897-67bc9967314e";
export const BACKEND =
  localStorage.SS_BACKEND ||
  (location.hostname.endsWith("butterbase.dev")
    ? "https://batteries-affairs-ind-conferencing.trycloudflare.com"
    : location.port === "8788"
      ? location.origin
    : "http://localhost:8788");

export const api = (path, opt = {}) =>
  fetch(BACKEND + path, opt).then((r) => {
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  });

export const fmt$ = (v) =>
  (v < 0 ? "-$" : "$") + Math.abs(Math.round(v)).toLocaleString();

export const fmtN = (v) =>
  typeof v === "number"
    ? v.toLocaleString(undefined, { maximumFractionDigits: 1 })
    : v;

export const esc = (s) =>
  String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
