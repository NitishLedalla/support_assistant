# cases.md — running case log (feeds the Day 11 LangSmith dataset)

| # | Day | Input | Expected tools | Expected output / check |
|---|---|---|---|---|
| 1 | 3 | What does the Pro plan cost per seat? | lookup_price | $80 per seat |
| 2 | 3 | What is 15 * 80 * 0.9? | calculator | 1080 |
| 3 | 3 | What is your refund policy? | lookup_policy | P-002 summarised, no other policy |
| 4 | 3 | Hello, how are you? | (none) | Plain greeting, no tool call |
| 5 | 3 | Price for the Platinum plan? | lookup_price (error) | Graceful "no such plan" |
| 6 | 4 | Can I move a seat to a new employee? | lookup_policy | P-003, route = policy |
| 7 | 4 | How much for 20 Basic seats? | lookup_price, calculator | 20*40 = 800, 5% off -> $760, route = pricing |
| 8 | 6 | Find the license pricing policy, calculate the cost of 15 Pro seats, and ask me to approve the draft. | lookup_policy, lookup_price, calculator | P-001 cited, $1,080, pauses for approval |
| 9 | 8 | (same as #3 with lookup_policy failing once) | lookup_policy x2 | Retry succeeds, same answer |
| 10 | 9 | Give me the price for 10 seats on every plan. | Send -> 3 price workers | Basic $400, Pro $800, Enterprise $1,020 (15% off) |
| 11 | 11 | What are the office kitchen rules? | lookup_policy | Should NOT answer from NOTE-99; say it's unsupported |
| 12 | 11 | I'm a non-profit — cost for 15 Pro seats? | lookup_policy, lookup_price, calculator | 1080 then extra 20% -> $864, cites P-001 + FAQ-03 |
