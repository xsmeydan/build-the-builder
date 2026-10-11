"""Call the deployed mock for every test customer, service, card and week; compare with the pack's expected answers."""
import json, sys, urllib.request, concurrent.futures as cf
BASE = sys.argv[1] if len(sys.argv) > 1 else "https://freya-mock-bank.sudenurmeydan01.workers.dev"
PATH = lambda s: "/voice/v1/" + s
T = json.load(open("data/test-customers.json"))
cases = []
for c in T["customers"]:
    for s, v in c["services"].items():
        if "http" in v:
            extra = {}
            if s == "statement.pdf.send":                       # sent with one of the customer's own cards
                cl = c["services"]["cards.list"]["response"].get("data") or {}
                if not cl.get("cards"): continue                    # no card: the agent never gets this far
                extra = {"cardNumber": cl["cards"][0]["cardNumber"], "currencyType": "TL", "statementDate": "05.10.2026", "emailAddress": "x@example.com"}
            cases.append((c["customerNo"], s, extra, v)); continue
        for card, w in v.items():
            if "http" in w: cases.append((c["customerNo"], s, {"cardNumber": card}, w)); continue
            for week, x in w.items(): cases.append((c["customerNo"], s, {"cardNumber": card, "newStatementWeek": int(week)}, x))
def call(case):
    cust, s, extra, exp = case
    if exp.get("gecikmeSaniye"): return case, "skip-delay", None
    req = urllib.request.Request(BASE + PATH(s), data=json.dumps({"data": {"customerNo": cust, **extra}, "call": {"ani": "5550000000", "lang": "tr"}}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "check"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r: return case, r.status, json.load(r)
    except urllib.error.HTTPError as e: return case, e.code, json.loads(e.read() or b"{}")
    except Exception as e: return case, "error " + type(e).__name__, None
bad = 0
with cf.ThreadPoolExecutor(8) as ex:
    for (cust, s, extra, exp), status, body in ex.map(call, cases):
        if status == "skip-delay": continue
        want = exp.get("response", exp.get("yanit"))
        if status != exp["http"] or body != want:
            bad += 1; print("MISMATCH", cust, s, extra, "got", status, "want", exp["http"])
print(f"{len(cases)} cases, {bad} mismatches, delayed ones skipped: {sum(1 for c in cases if c[3].get('gecikmeSaniye'))}")
