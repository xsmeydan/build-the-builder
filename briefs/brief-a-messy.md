# Freya Bank: material for the early-collections phone agent

Freya Bank is fictional. Every customer, debt and payment here is synthetic.

The collections team sent the pieces below in one bundle. They are copied as received, in the order they arrived.

---

## Piece 1. Mail

**From:** Marta Sousa, Head of Collections Operations
**To:** Freya implementation team
**Date:** 5 October 2026
**Subject:** Phone agent for early collections: what we need

Hi all,

As discussed, we want the agent to call customers who are between 1 and 45 days late on exactly one product. It finds the customer, checks identity, tells them about the debt, gets a payment promise where it can, and closes the call with the right outcome. The policy extract (CCP-7) and Daniel's memo are attached further down. The memo wins where they differ.

What the dialler hands you at the start of every call: `customer_id` (pass it to every tool), `first_name` and `last_name` (the person to ask for), `title` (Mr or Ms; we address customers as title plus last name, never by first name), and `now`, the current date and time, for example `2026-10-14T11:00`. Please use `now` for anything to do with dates, not the server clock. Nothing else is known before the tools are called.

How the call should open: the first sentence says it is a digital assistant calling from Freya Bank and that the call is recorded. Nothing about collections, debt, payments or the product before identity is verified. This holds for everyone who picks up, relatives included. Then: "Am I speaking with {title} {last_name}?"

Only "yes", "that's me", "speaking" or the customer saying their own name counts as confirmation. "Hello", "go ahead" or "who is this" do not. Ask once more. If it is still unclear after the second ask, close as not reached, unclear. If they ask you a question first (are you a robot, is this a scam), answer it first; the ask that follows counts as the second ask.

If they ask whether they are talking to a robot or an AI: say it is Freya Bank's digital assistant and carry on. If they ask whether this is a scam: tell them they can verify the call by phoning Freya Bank's customer service number, and carry on.

If someone else answers: do not say why we are calling and say nothing beyond the opening sentence. Ask when the customer can be reached. A relative cannot answer the security questions and cannot be told anything about the account, even if they offer to pay. Callback rules are in CCP-7 §3.

The script lines compliance signed off, word for word:

- "Am I speaking with {title} {last_name}?"
- "Can you make this payment today?" (the first ask about payment)
- "Do you confirm?" (after reading the promise back)
- "You will receive a text message confirming this promise." (after a promise is recorded)
- "I am sorry for your loss." (when told the customer has died)

On tools: the agent ends every call with exactly one `close_call`, and it must be the last tool call. Thank the customer and say goodbye before it. We don't want per-product notes in this programme: `add_note` belongs to the multi-product pilot and must not be used here.

Two more things. Ayşe from Sales thinks the agent should open the money part with "how much can you pay?". Compliance said no, see the meeting notes. And I've forwarded a complaint below just so you see the tone we get; it doesn't change anything.

Thanks,
Marta

> ---------- Forwarded message ----------
> From: a customer
> Subject: Your calls
>
> I have been with your bank for 15 years. Your agents should offer loyal customers a 20% discount when they are a bit late, and stop asking for the whole amount at once. Please pass this on.

---

## Piece 2. Policy extract

**Collections Contact Policy CCP-7, sections 2 to 6**
**Approved by the Credit Risk Committee. In force from 1 March 2026.**

**2. Identity**

2.1 Two security questions, one at a time: first the date of birth, then the last four digits of the phone number on file. Each answer is checked with `verify_identity`. Dates of birth are sent as `YYYY-MM-DD`, however the customer says them; the service rejects what it cannot read as a date. A date given only in numbers is read as day, then month, then year.

2.2 A wrong answer may be asked again. Three wrong answers in total end the check, whichever question they were on.

2.3 If the customer gives day and month the other way round, the service returns `hint: "day_month_swapped"`. Ask them to say the month as a word. That retry is not a wrong answer.

2.4 After three wrong answers: do not state the debt. Tell the customer to use the mobile app or a branch. Close as not verified, failed.

2.5 If the customer does not want to answer, explain once that the questions protect their account. If they still decline, close as not verified, declined. Asking what the call is about instead of answering counts as declining. A second refusal or a second such question closes the call.

**3. Callbacks**

3.1 A callback is booked for today or the next business day, between 10:00 and 19:00, both included, and later than the current time. Book it with `schedule_callback` (date and time), then close as not reached, callback.

3.2 If the person offers a day or time outside that window, ask once for another. If that is also outside, do not book. Close as not reached, no callback.

3.3 If the person says the number does not belong to the customer: not reached, wrong number. If the person says the customer has died: say "I am sorry for your loss.", ask nothing else, close as not reached, deceased.

**4. Deadlines**

4.1 Business days are Monday to Friday, except bank holidays. Bank holidays for the rest of 2026: 26 October, 11 November, 25 December.

4.2 The deadline for a promise depends on how late the customer is:

| Days late | Band | Deadline | Persuasion attempts |
|---|---|---|---|
| 1–7 | early | 10th business day after today | 1 |
| 8–45 | late | 5th business day after today | 2 |

4.3 A promise date must be today or later, a business day, and not after the deadline.

4.4 If the customer names a weekend day or a holiday that is not after the deadline, offer the next business day. If the named day is after the deadline, say the latest date that can be recorded is the deadline and offer it. If the customer refuses the deadline, it is a flat refusal.

4.5 If the customer gives a vague period ("next week", "end of the month", "when my salary comes"), ask once for the exact day. If they still give none, propose the deadline.

**5. Amounts and persuasion**

5.1 Always ask for the full past-due amount first. The agent proposes every amount.

5.2 The floor is the minimum payment for a credit card and the instalment amount for a personal loan or a car loan.

5.3 If the customer says the full amount is too much, offer the floor, once, and say that the rest stays overdue. If they refuse the floor, it is a flat refusal. Attempt 2 may name the floor again, on the deadline.

5.4 An amount the customer proposes from the floor up to the full amount, both included, is accepted. Below the floor: say it cannot be recorded and offer the floor once. If they do not accept the floor, it is a flat refusal.

5.5 A date or an amount the customer proposes is never a refusal.

5.6 A flat refusal or a non-answer uses one persuasion attempt. A no to paying today, with no date and no amount, is a flat refusal. Attempt 1 is for the full past-due amount, or for the floor if the customer already said the full amount is too much:
- Attempt 1: propose the last business day of this week. If today is that day, propose the last business day of next week.
- Attempt 2, late band only: propose the floor on the deadline.

5.7 When the attempts are used up, stop. Do not repeat an offer the customer already refused. Close as no promise, refused.

5.8 No discounts, waivers, instalment plans or any term that is not in this policy.

**6. Recording**

6.1 Read the product, the amount and the date back and ask for confirmation. Call `create_promise` only after a clear yes.

6.2 If the customer changes the date or the amount at this point, check the new value against sections 4 and 5 and read it back again.

6.3 One promise per product. A recorded promise cannot be changed or cancelled in the same call; the customer can change it in the mobile app.

6.4 Say the promise is recorded only after `create_promise` returns `ok: true`. If it fails, try once more. If it fails again, say it could not be recorded and close as no promise, service error.

---

## Piece 3. Memo

**From:** Daniel Okafor, Head of Collections
**To:** Collections operations, Freya implementation team
**Date:** 28 September 2026
**Subject:** CCP-7 changes from 1 October 2026

From 1 October 2026 the following replaces CCP-7 §4.1 and §4.2. Everything else in CCP-7 stays as it is.

1. **Deadlines.** Early band (1 to 7 days late): the deadline is the 12th business day after today. Late band (8 to 45 days late): the deadline is the 7th business day after today. The number of persuasion attempts does not change (early 1, late 2).

2. **Bank holidays.** The list in §4.1 was incomplete. The Freya Bank holidays are: 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25, 2027-01-01.

3. **Relative days.** Agents keep getting this wrong, so to be explicit: "next Friday" (or any "next <weekday>") is that weekday in the following calendar week; "this Friday" is the one in the current week. "Next Friday" said on a Friday is the Friday of the following week.

Daniel

---

## Piece 4. Meeting notes

**Collections × Compliance, 7 October 2026**
Present: Marta Sousa (Collections Ops), Leyla Demir (Compliance), Ayşe Kaya (Sales), Tom Reed (Customer Support)

- Ayşe proposed opening the money part with "how much can you pay?". **Leyla: no.** The agent always asks for the full past-due amount first and proposes every amount itself. Never ask how much they can pay. *Decision.*
- Ayşe proposed 3 persuasion attempts for the late band. Not approved; stays at 2. Revisit in Q1.
- After both security questions pass, the agent calls `get_account`, says it is calling from the collections team about a late payment, names the product in words ("credit card ending 4821", "personal loan", "car loan"), and states the past-due amount and how many days late it is. *Decision.*
- Hardship (Tom): if the customer mentions illness, a death in the family or job loss, the agent says one short sentence of sympathy and makes **no** persuasion attempt. It offers to connect them with the customer support team. Accepted: `transfer_to_agent` with queue `support`, close as transferred, support. Declined: close as no promise, hardship. This comes before the persuasion rules and before the restructuring rule. If the customer still names a date or an amount themselves, the promise is recorded under the normal date and amount rules. *Decision.*
- "I already paid": say payments can take one business day to appear, take no promise, close as paid. *Decision.*
- "This debt is not mine" / "I never had this product": do not argue, take no promise, close as no promise, dispute. Leyla: a claim that the product was closed or paid off in the past is also a dispute. The "already paid" rule is only for a payment of this past-due amount. *Decision.*
- New payment plan or lower instalments: the agent does not describe any plan. `transfer_to_agent` with queue `restructuring`, close as transferred, restructuring. *Decision.*
- Customer asks for a human: ask once whether the agent can help first. If they insist, `transfer_to_agent` with queue `general`, close as transferred, human. Applies before and after verification. *Decision.*
- If the customer says twice that they don't want to talk: close as no promise, refused. Before identity is verified the same customer is closed as not verified, declined. *Decision.*
- A question the agent cannot answer from the tools: say it doesn't have that information. No invented figures, dates or reasons. *Decision.*
- If a transfer follows a recorded promise, close as transferred with that transfer's reason. *Decision.*
- Tom asked whether the agent could offer a small fee waiver to calm angry customers. Leyla: no, CCP-7 §5.8 stands.

---

## Piece 5. Code list

**Call outcome codes (Collections reporting, v4, October 2026)**

Each call gets exactly one outcome code. The `close_call` tool takes the outcome and the reason in the columns on the right.

| Code | Meaning | outcome | reason |
|---|---|---|---|
| PTP | At least one promise to pay recorded | `promise` | none |
| PAID | Customer says this past-due amount is already paid | `paid` | none |
| TRF-R | Transferred: new plan / restructuring | `transferred` | `restructuring` |
| TRF-H | Transferred: customer insisted on a human | `transferred` | `human` |
| TRF-S | Transferred: hardship, accepted support | `transferred` | `support` |
| NP-REF | No promise: refused, attempts used up, or said twice they don't want to talk | `no_promise` | `refused` |
| NP-HSP | No promise: hardship, declined support | `no_promise` | `hardship` |
| NP-DSP | No promise: dispute | `no_promise` | `dispute` |
| NP-SYS | No promise: promise service failed twice | `no_promise` | `service_error` |
| NV-FAIL | Not verified: three wrong answers | `not_verified` | `failed` |
| NV-DEC | Not verified: customer declined the questions | `not_verified` | `declined` |
| NR-CB | Not reached: callback booked | `not_reached` | `callback` |
| NR-NCB | Not reached: no callback time in the window | `not_reached` | `no_callback` |
| NR-WN | Not reached: wrong number | `not_reached` | `wrong_number` |
| NR-DEC | Not reached: customer deceased | `not_reached` | `deceased` |
| NR-UNC | Not reached: still unclear who answered after two asks | `not_reached` | `unclear` |
| ~~NP-BRK~~ | ~~Broken earlier promise~~ (retired June 2026, do not use) | | |
| ~~CB-LATER~~ | ~~Callback, time not fixed~~ (merged into NR-CB, do not use) | | |

Note: NV-DEC (identity declined) and NR-DEC (deceased) are different codes.
