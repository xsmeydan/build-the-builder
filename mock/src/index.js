// Mock of Freya Bank's voice statement services (service contract 2026-10-01), served from the bank's test data.
// Stateless on purpose: a test customer gets exactly the answer listed in test-customers.json, every time.
import TEST from "../data/test-customers.json";

const BASE = "/voice/v1/";
// service -> [required data fields, error for a customer/card that is not in the test data]
const SERVICES = {
  "cards.list":            [["customerNo"], [404, "FB_IVR_CHANNEL_102", "WARNING", "Müşteriye ait geçerli kart bilgisi bulunamadı."]],
  "cards.balance":         [["cardNumber"], [404, "FB_IVR_CHANNEL_120", "WARNING", "Kart bulunamadı."]],
  "statement.week.get":    [["cardNumber"], [404, "FB_IVR_CHANNEL_121", "WARNING", "Kart bulunamadı."]],
  "statement.week.decide": [["cardNumber", "newStatementWeek"], null],
  "statement.week.change": [["cardNumber", "newStatementWeek"], null],
  "contact.email.get":     [["customerNo"], null],
  "statement.pdf.send":    [["customerNo", "cardNumber"], [404, "FB_IVR_CHANNEL_107", "WARNING", "Pdf dokümanı bulunamadı"]],
};
const CUSTOMERS = Object.fromEntries(TEST.customers.map(c => [String(c.customerNo), c]));
const CARD_OWNER = {};                                   // masked card number -> customer (each card belongs to one customer)
for (const c of TEST.customers) for (const v of Object.values(c.services)) if (!("http" in v)) for (const card of Object.keys(v)) CARD_OWNER[card] = c;

const FIELD_WORDS = { customerNo: "customer number", cardNumber: "card number", newStatementWeek: "new statement week" };
let seq = 0;
const guid = () => (Date.now().toString(16) + (++seq).toString(16)).padEnd(32, "0").slice(0, 32);
const send = (body, status) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });
function error(status, code, type, message) {
  const g = guid();
  return send({ result: { guid: g, returnCode: code, messageText: message, code, message, type, details: { guid: g, rootCause: type === "ERROR" ? "InvalidArguments" : "NotFound", errorOrigin: "freya-mock" } } }, status);
}
const invalid = message => error(400, "INVALID_ARGUMENTS_ERROR", "ERROR", message);
const empty = v => v === undefined || v === null || String(v).trim() === "";
const sleep = s => new Promise(r => setTimeout(r, s * 1000));

function cardKey(value) {                                 // the number exactly as cards.list gave it; also a full number with the same first six and last four
  const v = String(value).replace(/\s+/g, "");
  if (CARD_OWNER[v]) return v;
  if (/^\d{16}$/.test(v)) return Object.keys(CARD_OWNER).find(k => k.slice(0, 6) === v.slice(0, 6) && k.slice(-4) === v.slice(-4)) || null;
  return null;
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === "/" || url.pathname === "/health")
      return send({ ok: true, base: BASE, services: Object.keys(SERVICES), customers: Object.keys(CUSTOMERS).length }, 200);
    const name = url.pathname.startsWith(BASE) ? url.pathname.slice(BASE.length) : null;
    if (!name || !SERVICES[name]) return send({ result: { returnCode: "404", messageText: "Not found", code: "404", message: "Not found", type: "ERROR" } }, 404);
    if (request.method !== "POST") return send({ result: { returnCode: "405", messageText: "Method not allowed", code: "405", message: "Method not allowed", type: "ERROR" } }, 405);
    let body;
    try { body = await request.json(); } catch (e) { return invalid("request body is not valid JSON"); }
    const data = (body && typeof body.data === "object" && body.data) || {};
    const [required, notFound] = SERVICES[name];
    for (const f of required) if (empty(data[f])) return invalid((FIELD_WORDS[f] || f) + " cannot be empty");

    const missing = () => notFound ? error(...notFound) : invalid("no record for the given " + required.map(f => FIELD_WORDS[f] || f).join(" and "));
    let customer, entry;
    if (required.includes("cardNumber")) {
      const card = cardKey(data.cardNumber);
      customer = card && CARD_OWNER[card];
      if (name === "statement.pdf.send" && customer && String(customer.customerNo) !== String(data.customerNo)) customer = null;
      entry = customer && customer.services[name];
      if (entry && !("http" in entry)) entry = entry[card];
      if (entry && !("http" in entry)) entry = entry[String(parseInt(data.newStatementWeek, 10))];
    } else {
      customer = CUSTOMERS[String(data.customerNo).trim()];
      entry = customer && customer.services[name];
    }
    if (!entry || !("http" in entry)) return missing();
    if (entry.gecikmeSaniye) await sleep(Math.min(Number(entry.gecikmeSaniye) || 0, 25));
    return send(entry.response ?? entry.yanit ?? {}, entry.http);
  },
};
