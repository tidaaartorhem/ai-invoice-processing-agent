# Matchboard — 5-minute walkthrough script

The live site replays the AP queue as it stood on the morning of **Monday, 2011-10-31**: 530 vendor invoices, £260,555.63 under review.

## Minute 0–1 — the queue

Open the **Review queue** tab. 530 invoices, ranked by what needs a human first. The top of the queue is the whole thesis: invoices **573077 and 573080** — both £4,161.06, same account, issued **7 minutes apart**. The pipeline flags the pair as duplicate-risk; the human decides whether it's one order entered twice. Click either row for the full evidence panel: line items vs PO lines, the duplicate reason, GL suggestion, discount math.

## Minute 1–2 — match evidence

Click into invoice **572881** (account 12748). Every line shows a price variance: the vendor raised prices ~4% after the PO was cut. Click **572870** (account 13408): the goods receipt covers only the first two invoices — the later ones were invoiced before the goods arrived. Then filter the queue by *No PO*: 139 invoices from one-off vendors with nothing to match against — the long tail the AP clerk spends Monday on.

## Minute 2–3 — duplicates

Open the **Duplicates** tab. The near-duplicate check scanned all 19,960 invoices in the corpus and found **195 real duplicate-risk pairs** (same account, same total to the penny, different invoice numbers, within 7 days). Three touch this week's queue. Exact duplicates would be blocked outright; near-duplicates go to human review.

## Minute 3–4 — discounts

Open the **Discounts** tab. **£678.06** in early-pay discounts is still capturable this week — each row shows the deadline and days left, plus the APR equivalent (a 2%-for-10-days discount is ~36% APR; paying fast is the cheapest money there is). Below: **£239.10 already lost**, itemized by invoice — the cost of slow approvals, in pounds.

## Minute 4–5 — paste an invoice

Open the **Paste an invoice** tab. Paste any invoice-shaped text — the extractor pulls the invoice number, date, vendor, total, terms, and line items with deterministic patterns (missing fields are reported, never invented), then runs the same match against the shipped PO register and returns one recommended action. Try the sample buttons, or paste your own.

## The line to close on

371 of 530 invoices matched clean and are ready to approve. 159 need a human. Zero pay anything without one.
