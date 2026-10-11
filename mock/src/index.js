// Mock bank for the phone agent. One Durable Object holds every customer's state, so each call sees consistent data.
// Fill SERVICES from the case's service contract; load the test customers into data/customers.json.
import CUSTOMERS from "../data/customers.json";

const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

// Each service: (ctx) => response object. ctx = { body, customer, state, save(), log(entry) }.
// state is this customer's mutable record (counters, promises, notes...). Return { ok: false, error } for refusals.
const SERVICES = {
  // example_service: ({ body, customer, state }) => ({ ok: true }),
};

export class Bank {
  constructor(ctx) { this.storage = ctx.storage; }
  async fetch(request) {
    const url = new URL(request.url);
    const parts = url.pathname.replace(/^\/+|\/+$/g, "").split("/");
    if (request.method === "GET" && parts[0] === "ledger") {
      return json((await this.storage.get("c:" + parts[1])) || { calls: [] });
    }
    if (request.method === "POST" && parts[0] === "reset") { await this.storage.deleteAll(); return json({ ok: true }); }
    const name = parts[parts.length - 1];
    const service = SERVICES[name];
    if (!service) return json({ ok: false, error: "unknown service " + name }, 404);
    let body = {};
    try { body = await request.json(); } catch (e) { return json({ ok: false, error: "body is not JSON" }, 400); }
    const id = body.customer_id || body.musteri_id || body.customerId || "";
    const customer = CUSTOMERS[id];
    if (!customer) return json({ ok: false, error: "unknown customer_id" });
    const key = "c:" + id;
    const state = (await this.storage.get(key)) || { calls: [] };
    let out;
    try { out = await service({ body, customer, state }); }
    catch (e) { out = { ok: false, error: "service error: " + e.message }; }
    state.calls.push({ at: new Date().toISOString(), service: name, body, result: out });
    await this.storage.put(key, state);
    return json(out);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health") return json({ ok: true, services: Object.keys(SERVICES), customers: Object.keys(CUSTOMERS).length });
    const stub = env.BANK.get(env.BANK.idFromName("bank"));
    return stub.fetch(request);
  },
};
