# LangGraph + LangSmith — 14 Days, Simple Local Project (v3)

**Goal:** Get familiar with LangGraph's Graph API and LangSmith's tracing, prompt, and evaluation workflows by building one small project incrementally.
**Schedule:** 3 hours/day × 14 days baseline. Days 5, 7 and 13 are extended to ~3.5–4 hours to absorb durable persistence, concurrency, and cost control. Total ≈ 44–45 hours.
**Deployment / infrastructure:** None to build. The only external piece is one free hosted Postgres database (Neon or Supabase) used on Day 5 onward — a single connection string, nothing to install or host. No servers, Docker, cloud deploy, LangGraph Platform, background runs, webhooks or cron.

## Daily time budget

| Activity | Minutes |
|---|---:|
| Theory (concepts + targeted docs) | 30 |
| Implementation (project work + that day's LangSmith exercise) | 90 |
| Verify / explain / inspect traces | 30 |
| Buffer (debugging, repetition, break) | 30 |
| **Total** | **180** |

Heavy days are marked ⚠️ — if you don't finish the last implementation step on those days, that is expected, not a failure. Cut the last step, don't compress everything.

Extended days are marked ⏱ — their implementation block is 120–135 min instead of 90 and the day runs ~3.5–4 h. Plan those as weekend-style sessions or split across two sittings on the same day.

---

## The project: "Support Assistant"

One small agent that answers customer questions about software licenses. It grows a little every day. All data is synthetic and lives in plain files inside the project folder.

### Data files (create on Day 1, reuse all 14 days)

| File | Format | Contents | Used by |
|---|---|---|---|
| `pricing.xlsx` | Excel → loaded with pandas | Columns: `plan`, `price_per_seat`, `min_seats_for_discount`, `discount_pct`. Rows: Basic ($40, 20 seats, 5%), Pro ($80, 15 seats, 10%), Enterprise ($120, 10 seats, 15%) | `lookup_price` tool |
| `policies.txt` | Plain text | 5–6 short synthetic policies, each with an ID and a title, e.g. `P-001 License Pricing`, `P-002 Refunds`, `P-003 Seat Transfers`, `P-004 Trial Period`, `P-005 Support Hours`. One paragraph each. | `lookup_policy` tool |
| `faqs.txt` | Plain text | 3–4 short FAQs + 1 deliberately irrelevant paragraph (to test that the agent ignores noise) | `lookup_policy` tool (same file reader, or a second reader) |
| `customers.csv` | CSV → pandas | Columns: `customer_id`, `name`, `preferred_tone` (formal/casual), `current_plan`. 3–4 fake rows. | Runtime context + memory store exercises (Day 4–5) |

### Tools (built once, reused)

- `calculator(expression)` — safe arithmetic on a string expression.
- `lookup_price(plan)` — reads `pricing.xlsx` with pandas, returns price/discount rule for the plan.
- `lookup_policy(query)` — reads `policies.txt` + `faqs.txt`, returns the best-matching paragraph (simple keyword match is fine; no vector DB).
- `lookup_customer(customer_id)` — reads `customers.csv` with pandas, returns the row.

### The reference test question

**"Find the license pricing policy, calculate the cost of 15 Pro seats, and ask me to approve the draft."**

Expected: `P-001` cited, 15 × $80 = $1,200, 10% discount → **$1,080**, then a pause for approval. Every later day should still be able to answer this correctly.

### Case log

From Day 2 onward, keep a `cases.md` file: input, expected output, which tools should fire. This becomes your LangSmith evaluation dataset on Day 11 without inventing anything from scratch.

---

## The two-week map

| Day | LangGraph | LangSmith | Project step |
|---|---|---|---|
| 1 | State, nodes, edges, START/END, compile, invoke | Setup, projects, runs vs traces | Skeleton graph + data files |
| 2 | Reducers, `add_messages`, `MessagesState`, input/output schemas | Tags, metadata, finding runs | Message history + clean output |
| 3 | Tools, `.bind_tools()`, `ToolNode`, `tools_condition` | Tool/model spans, `@traceable`, errors, cost | Working tool loop |
| 4 ⚠️ | Conditional edges, `Command`, runtime context | Playground, prompt versions | Routing + customer tone |
| 5 ⏱ | Checkpointer, threads, `get_state`, store, **Postgres persistence** | Thread-level trace inspection | Memory that survives restarts |
| 6 | `interrupt()`, `Command(resume=…)` | Inline feedback on a run | Approval pause |
| 7 ⏱⚠️ | Streaming modes, async, **concurrency + `max_concurrency`** | Latency, time-to-first-token, parallel thread traces | Live output + many threads at once |
| 8 | `RetryPolicy`, loop limits, time travel, **history trimming** | Filter failed runs | Failure handling |
| 9 ⚠️ | Fan-out/fan-in, `Send`, concurrent reducers | Trace parallel branches | Parallel lookups |
| 10 | Subgraphs, shared vs private state | Nested traces | Worker graphs |
| 11 | Supervisor pattern, finish conditions | Datasets, splits, versions | Supervisor + dataset |
| 12 ⚠️ | Deterministic graph tests | Offline evaluation, evaluators, LLM-as-judge, prompt comparison | First evaluation run |
| 13 ⏱ | Run varied cases locally, **token budgets / cost control** | Annotation queues, online evaluators, cost dashboards, privacy | Review loop + cost |
| 14 | Rebuild from blank file; Functional API overview | Re-run evals, inspect regression | Consolidation |

---

## Day 1 — Graph skeleton and tracing setup

**Topics:** State, `TypedDict`, `StateGraph`, nodes, edges, `START`, `END`, `compile()`, `invoke()`. LangSmith: project, run, trace, parent/child spans.

**Theory (30 min)**
- A node is a plain function: `state in → partial update out`.
- An edge is a fixed connection; `START` and `END` are the built-in boundaries.
- Without a reducer, a returned field simply overwrites the old value.
- LangSmith: one `.invoke()` = one trace; each node inside = one run (child span).

**Implementation (90 min) — how each topic shows up in the project**
1. *(30 min) Setup.* Create the venv, install `langgraph`, `langchain`, `langsmith`, `pandas`, `openpyxl`, one model provider SDK. Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT=support-assistant`. Create all four data files with synthetic content.
2. *(40 min) State + nodes + edges.* State = `{"question": str, "answer": str}`. Node 1 `normalize` lowercases/strips the question. Node 2 `respond` returns a fixed placeholder answer (no LLM yet). Edges: `START → normalize → respond → END`. Compile, invoke with a question.
3. *(20 min) Trace.* Open LangSmith, find the trace, expand it — see `normalize` and `respond` as two child runs with their inputs/outputs. Print the graph diagram (`get_graph().draw_mermaid()`).

**Verify (30 min)** — Point to: the initial state, each node's update, the final state, and where each of those appears in the trace.

---

## Day 2 — Reducers, messages, and organized traces

**Topics:** Partial updates vs replacement, reducers, `Annotated`, `add_messages`, `MessagesState`, separate input/output schemas. LangSmith: tags, metadata, filtering runs.

**Theory (30 min)**
- A reducer decides how a node's partial update merges into existing state (append vs overwrite).
- `add_messages` appends new messages, and *replaces* a message when the ID matches.
- Input/output schemas let internal state stay private while the user only sees the public output.
- `TypedDict` does not validate at runtime — it only guides your editor/type-checker.

**Implementation (90 min)**
1. *(35 min) Reducer in the project.* Change state to `messages: Annotated[list, add_messages]` plus `notes: Annotated[list, operator.add]`. `respond` now calls the LLM and appends an `AIMessage`. Show that invoking twice with `messages` carried over produces a growing list, not an overwrite. Demonstrate ID-based replacement once.
2. *(30 min) Schemas.* Define `InputState` (`question`) and `OutputState` (`answer`) so the public result is clean while `messages`/`notes` stay internal.
3. *(25 min) LangSmith organization.* Add `tags=["day2"]` and `metadata={"case": "..."}` via `config`. Filter the project by tag. Log the first two cases into `cases.md`.

**Verify (30 min)** — Predict the state after each node before running, then compare. Explain why `add_messages` alone does not remember anything between separate `.invoke()` calls (memory is Day 5).

---

## Day 3 — Tools and the agent loop

**Topics:** Defining tools with `@tool`, `.bind_tools()`, tool-call messages, `ToolNode`, `tools_condition`, ending the loop. LangSmith: tool/model spans, `@traceable`, error runs, token/cost.

**Theory (30 min)**
- `.bind_tools()` lets the model *request* a tool call; it never executes anything.
- `ToolNode` executes the request and returns a `ToolMessage` linked by `tool_call_id`.
- `tools_condition`: last message has tool calls → go to tools; otherwise → `END`.
- `@traceable` makes a plain helper function show up as its own span.

**Implementation (90 min)**
1. *(25 min) Tools.* Build `calculator`, `lookup_price` (pandas reads `pricing.xlsx`), `lookup_policy` (reads the text files). Bind all three. Ask "what does Pro cost?" and observe the tool-call request in the AI message.
2. *(45 min) Loop.* `START → agent → tools_condition → (tools → agent) | END`. Add a simple counter in state to cap tool calls at 5. Ask the reference question (without the approval part yet) and get $1,080 with `P-001` cited.
3. *(20 min) LangSmith.* Wrap the keyword-matching helper inside `lookup_policy` with `@traceable`. Force one tool error (unknown plan). Inspect prompt, tool args/results, tokens, latency, cost.

**Verify (30 min)** — Run a no-tool question, a pure calculation, a policy lookup. Match each answer to its tool spans. Explain the error from the trace, not the code. Add all cases to `cases.md`.

---

## Day 4 ⚠️ — Routing, `Command`, runtime context, prompt versions

**Topics:** `add_conditional_edges`, rule-based vs model-based routing (structured output), `Command(goto=…, update=…)`, runtime context (`context_schema`). LangSmith: Playground, prompt variables, saved prompt versions, pulling a pinned version.

**Theory (30 min)**
- A conditional edge returns the *name* of the next node.
- Rule route = deterministic Python; model route = LLM with structured output constrained to allowed values.
- `Command` lets a node both update state and choose the next node in one return.
- Runtime context = per-call configuration (who is calling, what tone) that is *not* graph state.

**Implementation (90 min)**
1. *(35 min) Routing.* Add a `classify` node → route to `pricing`, `policy`, or `general`. Do it once with a keyword rule and once with a structured-output LLM classification. Convert one route to use `Command`.
2. *(15 min) Runtime context.* Pass `customer_id` in context; `lookup_customer` reads `customers.csv` and the response node uses `preferred_tone` from it.
3. *(40 min) Prompts.* In the Playground, create two versions of the system prompt (`baseline`, `candidate`). Save both, pull the pinned `baseline` into the graph, record the version name in run metadata.

**Verify (30 min)** — Exercise every route plus one invalid classification. Confirm which prompt version actually ran from the trace. Confirm routing never runs two branches by accident.

---

## Day 5 ⏱ — Memory: checkpointer, threads, store, durable persistence (~3.5 h)

**Topics:** `InMemorySaver`, `thread_id`, `get_state()`, `get_state_history()`, `InMemoryStore` + namespaces, then `PostgresSaver` + `PostgresStore` and restart survival. LangSmith: locating all runs of one thread.

**Theory (30 min)**
- Checkpointer saves state after every node, keyed by thread; that is what gives memory across invocations.
- Store = cross-thread memory (facts about a user), separate from conversation state.
- In-memory versions lose everything on process exit. Postgres versions keep the *same API* and persist across restarts — the swap is two class names and a connection string.
- A paused (`interrupt`) graph is only truly pausable if its checkpoint is durable — this is why Day 6 needs today.

**Implementation (120 min)**
1. *(30 min) Threads (in-memory).* Compile with `InMemorySaver`. Ask a question, then "what did I just ask?" on the same thread → remembered. New thread → not remembered. Inspect `get_state()`.
2. *(25 min) Store (in-memory).* Save a customer's `preferred_tone` in an `InMemoryStore` namespace keyed by `customer_id`; read it from a different thread for the same customer.
3. *(15 min) Hosted Postgres.* Create a free Neon or Supabase project, copy the connection string into `.env` as `DATABASE_URL`. Install `langgraph-checkpoint-postgres` and `psycopg`. No Docker, no local install.
4. *(35 min) Durable swap.* Replace `InMemorySaver` → `PostgresSaver.from_conn_string(...)` (call `.setup()` once) and `InMemoryStore` → `PostgresStore`. Rerun steps 1–2 unchanged. Then: start a conversation, kill the Python process, start it again, continue the same `thread_id` — the history is still there. Do the same for the store value.
5. *(15 min) LangSmith.* Find all runs for one `thread_id` across both process runs; confirm they line up with the checkpoints.

**Verify (30 min)** — Show thread isolation, store scope, and restart survival. Explain in one sentence why the graph code didn't change when the backend did. From here on, the project uses Postgres by default.

---

## Day 6 — Human approval with `interrupt()`

**Topics:** `interrupt()`, `Command(resume=…)`, approve / edit / reject flows, node re-execution on resume. LangSmith: attaching feedback and comments to a run.

**Theory (30 min)**
- `interrupt()` pauses and persists the graph; requires a checkpointer.
- Resuming re-runs the node from its start up to the interrupt — code before it executes twice.
- A human *decision* controls execution; a LangSmith *feedback score* just labels quality. They are different things.

**Implementation (90 min)**
1. *(40 min) Approval.* Add a `review` node before the final answer that calls `interrupt()` with the draft. Implement approve (send as-is), edit (human replaces text), reject (regenerate). Same thread throughout.
2. *(25 min) Idempotency.* Add a fake "send email" step with a stable ID; prove that resuming does not send twice.
3. *(25 min) LangSmith.* Inspect the paused and resumed runs. Add inline feedback (score + comment) to one final answer and write down the scoring rule you used.

**Verify (30 min)** — Demonstrate all three outcomes on the reference question (now it *does* pause for approval). Explain why feedback never authorizes a graph action.

---

## Day 7 ⏱⚠️ — Streaming, async, and concurrency (~4 h)

**Topics:** `stream_mode` = `values` / `updates` / `messages`; `ainvoke` / `astream`; running many threads concurrently with `asyncio.gather`; `max_concurrency`; concurrent writes against a shared checkpointer/store. LangSmith: latency, time-to-first-token, viewing parallel thread traces.

**Theory (30 min)**
- `values` = full state after each node; `updates` = only the delta; `messages` = LLM tokens as generated.
- Streaming shows progress; it does not make the graph run faster.
- Async is what allows *many* graph runs at once — one process, many threads in flight.
- `max_concurrency` (in `config`) caps how many nodes/tasks run in parallel inside one graph run; provider rate limits cap how many runs you can have in flight at once. These are two different limits.
- Different `thread_id`s never collide on state; the shared risk is the store (same namespace/key) and provider rate limits.

**Implementation (135 min)**
1. *(20 min) Async.* Convert the LLM node and the tool node path to `async def`; run the reference question with `ainvoke` against the Postgres checkpointer (async connection).
2. *(40 min) Stream.* Run the reference question with `updates`, then `messages`. Compare the two outputs. (Custom progress events: read-only.)
3. *(50 min) Concurrency.* Build a list of 15 different inputs from `cases.md` (repeat with different `thread_id`s). Fire them all with `asyncio.gather(*[graph.ainvoke(...)])`. Observe: total wall time vs. sequential, any provider rate-limit errors, and whether all 15 checkpoints landed in Postgres. Then deliberately make two threads write the same store key at the same time and see last-write-wins. Finally set `max_concurrency` on a run that uses Day 9-style fan-out later — for today, just set it and confirm it's accepted in `config`.
4. *(25 min) LangSmith.* Measure time-to-first-token vs. total latency on one run. Then open the project view for the 15 concurrent runs — sort by latency, spot the slowest thread, and see what made it slow.

**Verify (30 min)** — Match streamed chunks to the final state. State the sequential vs. concurrent wall time. Explain the difference between "parallel nodes inside one run" and "many runs at once." Everything stays in the terminal — no UI.

---

## Day 8 — Failures, retries, time travel

**Topics:** `RetryPolicy`, loop/recursion limits, fallback path, `get_state_history()`, `update_state()`, replay vs fork; trimming/summarizing long histories (moved from Day 5). LangSmith: filter failed runs.

**Theory (30 min)**
- Retry only what is safe to retry; an external side effect retried twice is a bug.
- Checkpoint history lets you rewind to any step, change state, and continue on a new branch.
- Checkpointing gives resumability, not exactly-once external effects.
- Long histories need trimming before the model call; keep tool-call/result pairs together.

**Implementation (90 min)**
1. *(30 min) Retries.* Make `lookup_policy` fail once at random; attach a `RetryPolicy`. Trigger an exhausted retry. Set `recursion_limit` and hit it deliberately.
2. *(35 min) Time travel.* List checkpoint history, pick the one before `classify`, `update_state` to force a different route, resume — compare both outcomes.
3. *(25 min) Trimming.* Build a 20-message fixture conversation on one thread, trim to the last N messages before the model call, run one short summarization pass, verify tool-call pairs stayed intact. Filter LangSmith runs by error status and add the failure case to `cases.md`.

**Verify (30 min)** — Explain retry vs resume vs replay vs fork in your own words. Show a loop that stops predictably. Show the model's actual (trimmed) context in the trace.

---

## Day 9 ⚠️ — Parallelism and `Send`

**Topics:** Supersteps, static fan-out/fan-in, dynamic `Send`, concurrent updates needing a reducer, ordering results. (Caching: read-only walkthrough.)

**Theory (30 min)**
- Nodes in the same superstep run in parallel; all their updates are merged via reducers at the end of the step.
- Two parallel nodes writing the same key without a reducer = error.
- `Send` launches N copies of a node with different inputs when N is unknown until runtime.

**Implementation (90 min)**
1. *(25 min) Static fan-out.* Run `lookup_price` and `lookup_policy` in parallel for the reference question, then a `merge` node combines them.
2. *(45 min) `Send`.* Input: a list of plans (`["Basic", "Pro", "Enterprise"]`). `Send` one `price_worker` per plan; results land in a list reducer ordered by plan name. Deliberately cause a conflicting update, fix it with the reducer.
3. *(20 min) LangSmith.* Compare the parallel trace to the earlier sequential one — latency and cost.

**Verify (30 min)** — Test with 0, 1, and 3 plans; handle empty input explicitly. Explain why concurrent writes need a merge rule. *(Read the `CachePolicy` docs only if time remains.)*

---

## Day 10 — Subgraphs

**Topics:** Compiled graph as a node, shared-key composition, wrapper functions for different schemas, private worker state, subgraph memory scope. LangSmith: nested traces.

**Theory (30 min)**
- A subgraph is a compiled graph used as a single node in a parent.
- If schemas match, add it directly; if not, wrap it in a function that maps state in/out.
- Worker-internal messages should not leak into the parent's public output.

**Implementation (90 min)**
1. *(40 min) Workers.* Package `pricing_worker` (price lookup + calculator loop) and `policy_worker` (policy lookup) as standalone compiled graphs. Test each alone.
2. *(30 min) Compose.* Add one worker via shared keys and the other via a schema-mapping wrapper. Show fresh vs retained worker state across two calls.
3. *(20 min) LangSmith.* Inspect nested traces; introduce a wrapper mapping bug and find it from the trace.

**Verify (30 min)** — Parent output is clean; worker messages stay private; explain the chosen memory scope.

---

## Day 11 — Supervisor and the evaluation dataset

**Topics:** Supervisor node with structured next-step decision, delegation limits, explicit finish condition, handoff (`Command.PARENT`) walkthrough. LangSmith: datasets, examples, reference outputs, versions, dev/holdout splits.

**Theory (30 min)**
- Supervisor = LLM that picks which worker runs next (LLM-driven routing, unlike Day 4's rules).
- Always define how it *finishes*, and cap how many times it can delegate.
- A dataset is inputs + expected outputs; a holdout split is never used to tune prompts.

**Implementation (90 min)**
1. *(40 min) Supervisor.* Supervisor routes to `policy_worker`, then `pricing_worker`, synthesizes both results, then reaches the `review` (approval) node. Require both results before finishing; cap at 4 delegations.
2. *(20 min) Handoff.* Read/inspect a minimal `Command.PARENT` handoff example; compare with "worker returns to supervisor".
3. *(30 min) Dataset.* Create a LangSmith dataset from the ~12 cases in `cases.md` (routing, arithmetic, grounded lookup, combined, unsupported input, one failure). Add one example directly from a trace. Version it and create `dev` / `holdout` splits.

**Verify (30 min)** — Reference question uses both workers, returns $1,080, pauses for approval. Explain why holdout must not guide prompt edits.

---

## Day 12 ⚠️ — Tests and evaluations

**Topics:** Deterministic graph tests with fake tools/models; evaluation targets (final answer, single step, tool trajectory); code evaluators, LLM-as-judge, experiment comparison. 

**Theory (30 min)**
- Unit test = fixed input, fake model, assert route/state. Evaluation = real model, scored against references.
- Code evaluators check facts (is $1,080 present? was `P-001` cited? did `pricing_worker` run?). Judges score fuzzier qualities.
- A 12-case dataset is a smoke test, not a reliability guarantee.

**Implementation (90 min)**
1. *(25 min) Tests.* Write 3 tests with fake tool/model outputs: correct routing, approval pause reached, delegation cap respected.
2. *(35 min) Offline eval.* Run `evaluate()` on the `dev` split with three code evaluators: correct total, policy ID present, required worker used.
3. *(30 min) Compare + judge.* Run the same eval with the `candidate` prompt; compare score, latency, tokens. Apply a simple LLM-judge rubric to 3 outputs and compare its scores with your own labels.

**Verify (30 min)** — Show one defect caught by a test or evaluator; explain one place you disagreed with the judge; state which prompt won on measured cases.

---

## Day 13 ⏱ — Human review, online evaluation, monitoring, cost control (~3.5 h)

**Topics:** Annotation queues, online (live) evaluators, project dashboards (latency, errors, tokens, cost, feedback), hiding sensitive fields, sampling/retention; token budgets and per-thread cost control.

**Theory (30 min)**
- Offline eval = dataset you control; online eval = scoring live traces as they arrive.
- Annotation queue = humans review runs against a rubric; results become feedback and can become dataset examples.
- Cost control has three levers: cap tokens per model call (`max_tokens`), cap steps per run (`recursion_limit` + delegation cap), and trim context (Day 8). LangSmith tells you which lever to pull by showing cost per run and per thread.
- Fixture data is fake, but the habit of not sending real customer fields to traces matters.

**Implementation (120 min)**
1. *(30 min) Annotation queue.* Create one queue, review 3 of your runs against a short rubric, add one reviewed case to the dataset.
2. *(30 min) Online evaluator.* Configure one narrow online evaluator (e.g., "answer cites a policy ID"). Generate fresh traces by running the graph on 5 varied inputs locally. Inspect feedback.
3. *(35 min) Cost control.* Rerun the 15-thread concurrent batch from Day 7. In LangSmith, sort by tokens/cost per run and per thread; identify the most expensive case. Add a token budget to state (count tokens from each model response via usage metadata; stop with a clear message when the budget is exceeded), set `max_tokens` on the model, and rerun the batch. Compare total cost before and after.
4. *(25 min) Dashboard + privacy.* Look at project metrics (latency, errors, tokens, cost, feedback). Hide `customer_id`/`name` from trace inputs with an input processor. Read about sampling/retention; no alerts or webhooks needed.

**Verify (30 min)** — Show human vs automated score on the same run; explain how a bad trace becomes a regression example. State the before/after cost of the batch and which lever produced the saving. Features your account tier blocks: read the docs and mark "reviewed".

---

## Day 14 — Rebuild and close the loop

**Topics:** Recall of full architecture; Functional API (`@entrypoint`, `@task`) as a read-only comparison. LangSmith: rerun evals, inspect a regression.

**Theory (30 min)**
- 15 min: sketch the final graph from memory (nodes, edges, where memory/interrupt/parallelism/subgraphs live).
- 15 min: read the Functional API overview — same runtime (checkpoints, interrupts, streaming), function-style instead of graph-style.

**Implementation (90 min)**
1. *(60 min) Rebuild.* From a blank file, using only the data files and tools: state, one route, memory, and *either* the tool loop *or* the approval pause. Small rebuild, not everything.
2. *(20 min) Evaluate.* Run the holdout split on the rebuild. Inspect one failed or changed result, compare its trace and prompt version.
3. *(10 min) Recap.* One page: graph diagram, one informative trace link, dataset version, two experiment links, one feedback example.

**Verify (30 min)** — Without reading code, explain: state, routing, memory, interrupt, parallelism, subgraphs. Then: how traces, datasets, evaluators, prompt versions, feedback, and metrics feed improvement. Use leftover buffer on your weakest day.

---

## Coverage summary

| Area | Days | Depth |
|---|---|---|
| State, nodes, edges, reducers, schemas | 1–2 | Build |
| Tools, tool loop, routing, `Command`, runtime context | 3–4 | Build |
| Checkpointer, threads, store — in-memory and Postgres, restart survival | 5 | Build |
| Interrupts, approve/edit/reject | 6 | Build |
| Streaming, async, concurrency, `max_concurrency` | 7 | Build primary modes; custom events read only |
| Retries, limits, time travel, history trimming | 8 | Build |
| Parallelism, `Send` | 9 | Build; caching = read only |
| Subgraphs | 10 | Build |
| Supervisor | 11 | Build; handoff = walkthrough |
| Functional API | 14 | Read only |
| LangSmith tracing, tags, metadata, `@traceable` | 1–10 | Build throughout |
| Playground, prompt versions | 4, 12 | Build |
| Datasets, splits, versions | 11, 13 | Build |
| Offline evaluation, code evaluators, LLM judge, experiments | 12, 14 | Build |
| Annotation queues, online eval, dashboards, privacy, token budgets / cost control | 13 | Build where account allows; else reviewed |
| LangGraph Server / Platform, Docker, cloud deploy, background runs, webhooks, cron | — | Excluded |

## Boundaries

The only database is one free hosted Postgres used as a checkpointer/store backend — you never install, host, or administer it. No API servers, Docker, cloud deploy, LangGraph Server/Platform, background runs, webhooks, cron, or CI. No vector stores — `lookup_policy` uses keyword matching over a text file. No real MCP integrations. No RAG pipeline. A deployed app is not a completion requirement.

## Completion checklist

- [ ] Build and explain a small Graph API workflow and change its routing.
- [ ] Have exercised tools, memory, interrupts, streaming, parallelism, subgraphs, and failure handling.
- [ ] Conversation and store data survive a process restart via Postgres.
- [ ] Have run 15 threads concurrently, measured wall time vs sequential, and reduced batch cost with a token budget.
- [ ] Follow a trace from input through model/tool steps to output.
- [ ] Find a run by tag/metadata and identify which prompt version it used.
- [ ] Have a versioned dataset with dev/holdout splits, built from `cases.md`.
- [ ] Have compared two prompt versions in an experiment with code evaluators.
- [ ] Have tried human feedback and an LLM judge and can explain their limits.
- [ ] Can explain online evaluation and demonstrate it if the account allows.
- [ ] Reference question returns $1,080 with `P-001` and pauses for approval, on the final graph.
- [ ] Can clearly say which topics were built vs only reviewed.
