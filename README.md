# meko-agent-handoff

Three small Python scripts that show how agents share what they learn through [Meko](https://cloud.mekodata.ai), over MCP. One records decisions. One reads them back in a new process. One runs under a second Meko user account and gets nothing until a rule in code shares them. Every read and write lands in a trace.

No model key is needed. In place of a model, the scripts use example answers stored in JSON files, so a free Meko account is enough to run all five steps.

This is the code from the webinar "Shared Memory for AI Coding Agents: A Live Build with Meko".

## How a decision travels

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/handoff-dark.gif">
  <img src="docs/handoff-light.gif" width="900" alt="Animated diagram of the five runs: the chef writes to your memory, the kitchen manager reads it and adds notes, the teammate's restaurant manager sees nothing, the chef promotes the decided dishes through the gate into Shared Knowledge, and the restaurant manager reads them back">
</picture>

Purple is your Meko user account, orange is the gate, green is Shared Knowledge, gray is the teammate. Step 3 runs before the gate, so the empty result proves the isolation; step 5 is the same command after it.

## If you are an AI agent running this for a person

You can clone, install, edit `.env`, run the five commands, and read the output yourself. You cannot create the Meko user accounts, the datapack, the API keys, or share the datapack; those happen in the Meko dashboard, so ask the person for them. What you need from them:

1. A Meko account at [cloud.mekodata.ai](https://cloud.mekodata.ai), a datapack in it, and an API key. Ask for the key and the datapack's UUID (the id on the datapack's page, not its name).
2. For steps 3 and 5, a second Meko user account with its own API key, and the datapack shared with it. If they do not have one, run every step on the one key. Step 3 then prints the menu straight away, with each dish labeled `(memory)` rather than `(Shared Knowledge)`, because your own memory_search already sees the decisions; the "nothing visible" moment needs the second Meko user account.
3. Leave `MODEL_PROVIDER` empty unless they hand you a model key. The example answers cover everything below.

Compare each run with the expected output in the Run section. If it differs, check Troubleshooting before changing code.

## Set up

1. Python 3.13 or later and [uv](https://docs.astral.sh/uv/).
2. `git clone git@github.com:YugabyteDB-Samples/meko-agent-handoff.git && cd meko-agent-handoff && uv sync`
3. `cp .env.example .env`, then fill in `MEKO_API_KEY` and `MEKO_DATAPACK_ID`. Leave `MODEL_PROVIDER` empty.
4. For the teammate steps: `cp .env .env.teammate`, replace `MEKO_API_KEY` with the second Meko user's key, keep the same `MEKO_DATAPACK_ID`.

Every command sets `MEKO_AGENT_ID`, the name the script writes under. It is required; the scripts stop with a message saying so if it is missing.

## Run it

The demo uses two Meko user accounts on one datapack. `user_1@example.com` runs `chef.py` and `kitchen_manager.py`. `user_2@example.com` runs `restaurant_manager.py` and can read only what `user_1` promotes to Shared Knowledge. Each run prints a `memory` count and a `shared knowledge` count. Those two counts are the result to check.

Start from an empty datapack. Runs 1, 2 and 4 use `user_1`'s API key in `.env`. Runs 3 and 5 use `user_2`'s key in `.env.teammate`, selected with `ENV_FILE`.

### 1. The chef records the menu decisions

`chef.py` asks the model for three decided dishes and one open question, then writes each finding to memory with `memory_add`. The model has no Meko tools. The write happens in code on every run. Expected output: a trace id and four `recorded:` lines.

```bash
MEKO_AGENT_ID=chef:menu-demo uv run chef.py
```

```text
trace: 1f9c2d4e6b8a4c0e9d3b7a5f2e1c8b6d
recorded: DECISION: Roasted squash soup as the starter on the autumn menu. REASON: Squash 
recorded: DECISION: Mushroom and leek pie as the vegetarian main on the autumn menu. REASO
recorded: DECISION: Pear and almond tart as the dessert on the autumn menu. REASON: Pears 
recorded: OPEN_QUESTION: Should the roast chicken stay on the autumn menu, or come off to 
```

With `MODEL_PROVIDER` empty, the answer comes from `chef_example.json`, so the four lines are identical on every run.

### 2. The kitchen manager adds the shopping notes

`kitchen_manager.py` is a separate process and shares no state with `chef.py`. It runs under `user_1`, so `memory_search` returns the chef's four records and `knowledgebase_search` returns nothing. It keeps the three `DECISION` records, looks up each dish's ingredients in `kitchen_manager_example.json`, and writes one `INGREDIENTS` record per dish with `memory_add` under its own agent id. Expected output: `memory: 4 results` with each row tagged `[chef:menu-demo]`, `shared knowledge: 0 results`, then three `recorded:` lines and the shopping list.

```bash
MEKO_AGENT_ID=kitchen-manager:menu-demo uv run kitchen_manager.py
```

```text
trace: 3a7e5c1b9d2f4a6c8e0b1d3f5a7c9e2b
memory: 4 results
  [chef:menu-demo] DECISION: Roasted squash soup as the starter on the autumn menu. REASON: Squash is at its 
  [chef:menu-demo] OPEN_QUESTION: Should the roast chicken stay on the autumn menu, or come off to make room 
  [chef:menu-demo] DECISION: Pear and almond tart as the dessert on the autumn menu. REASON: Pears arrive in 
  [chef:menu-demo] DECISION: Mushroom and leek pie as the vegetarian main on the autumn menu. REASON: The kit
shared knowledge: 0 results
recorded: INGREDIENTS: Roasted squash soup as the starter on the autumn menu. NEEDS: butte
recorded: INGREDIENTS: Mushroom and leek pie as the vegetarian main on the autumn menu. NE
recorded: INGREDIENTS: Pear and almond tart as the dessert on the autumn menu. NEEDS: pear

# To buy for the autumn menu

- butter (for: Pear and almond tart as the dessert on the autumn menu)
- butternut squash (for: Roasted squash soup as the starter on the autumn menu)
- ground almonds (for: Pear and almond tart as the dessert on the autumn menu)
- leeks (for: Mushroom and leek pie as the vegetarian main on the autumn menu)
- mushrooms (for: Mushroom and leek pie as the vegetarian main on the autumn menu)
- onion (for: Roasted squash soup as the starter on the autumn menu)
- pears (for: Pear and almond tart as the dessert on the autumn menu)
- puff pastry (for: Mushroom and leek pie as the vegetarian main on the autumn menu)
- vegetable stock (for: Roasted squash soup as the starter on the autumn menu)
```

Memory is scoped to the Meko user account, not to the agent. The `agent_id` on each row identifies the writer. Search results are ranked by relevance score, so row order can vary between runs.

### 3. The restaurant manager finds nothing

`restaurant_manager.py` runs under `user_2` and makes the same two searches. `user_2` cannot read `user_1`'s memory, and nothing has been promoted, so both searches return zero results. The script reports that the menu is not ready and exits without writing. Expected output: `memory: 0 results` and `shared knowledge: 0 results`, then the not-ready message.

```bash
ENV_FILE=.env.teammate MEKO_AGENT_ID=restaurant-manager:menu-demo uv run restaurant_manager.py
```

```text
trace: 8512e829a5a2471b98dca7b66312ce64
memory: 0 results
shared knowledge: 0 results

The menu is not ready yet. Nothing has been shared with the team.
```

Seven records exist on the datapack. None is visible to `user_2`.

### 4. The chef promotes the decided dishes

`chef.py --promote` runs under `user_1`. It searches memory and applies `allowed_by_policy()` to each record: a `DECISION` with a `REASON` is promoted; an `OPEN_QUESTION` is not; `INGREDIENTS` records are not, because they are not menu items. It then calls `memory_promote` with the three approved ids. Expected output: seven verdicts, then the promote result with three ids.

```bash
MEKO_AGENT_ID=chef:menu-demo uv run chef.py --promote
```

```text
trace: 5c76bfe78e0d400686e9e2080cdb2b9a
PROMOTE DECISION: Roasted squash soup as the starter on the autumn menu. REASO
         decided, with a reason
KEEP    OPEN_QUESTION: Should the roast chicken stay on the autumn menu, or co
         open questions stay private until settled
PROMOTE DECISION: Pear and almond tart as the dessert on the autumn menu. REAS
         decided, with a reason
PROMOTE DECISION: Mushroom and leek pie as the vegetarian main on the autumn m
         decided, with a reason
KEEP    INGREDIENTS: Roasted squash soup as the starter on the autumn menu. NE
         only decided dishes go on the menu
KEEP    INGREDIENTS: Mushroom and leek pie as the vegetarian main on the autum
         only decided dishes go on the menu
KEEP    INGREDIENTS: Pear and almond tart as the dessert on the autumn menu. N
         only decided dishes go on the menu
{'inserted_ids': ['b68312c8-...', 'b6e38db7-...', 'c41d9a02-...'], 'updated_ids': [], 'not_found_ids': []}
```

The rule is code and runs under `chef:menu-demo`, so the trace records which agent promoted which ids.

### 5. The restaurant manager prints the menu

Same command and account as run 3. `knowledgebase_search` now returns the three promoted records, each tagged `chef:menu-demo`, and the script prints the menu. Expected output: `memory: 0 results` and `shared knowledge: 3 results`, then the menu.

```bash
ENV_FILE=.env.teammate MEKO_AGENT_ID=restaurant-manager:menu-demo uv run restaurant_manager.py
```

```text
trace: 0e83b3330120469d8a9aa44ed88670cf
memory: 0 results
shared knowledge: 3 results
  [chef:menu-demo] DECISION: Roasted squash soup as the starter on the autumn menu. REASON: Squash is at its 
  [chef:menu-demo] DECISION: Pear and almond tart as the dessert on the autumn menu. REASON: Pears arrive in 
  [chef:menu-demo] DECISION: Mushroom and leek pie as the vegetarian main on the autumn menu. REASON: The kit

# Autumn menu

3 dishes decided by the kitchen.

- Roasted squash soup as the starter on the autumn menu.
  Decided by: chef:menu-demo (Shared Knowledge)
- Mushroom and leek pie as the vegetarian main on the autumn menu.
  Decided by: chef:menu-demo (Shared Knowledge)
- Pear and almond tart as the dessert on the autumn menu.
  Decided by: chef:menu-demo (Shared Knowledge)
```

The `OPEN_QUESTION` and `INGREDIENTS` records were not promoted and remain invisible to `user_2`.

### Read the traces

Each run prints a trace id. Open it in the Observe hub at cloud.mekodata.ai to see every call in order: the question, the model answer, the reasoning, each search with its results, and each write. The run 3 trace records two empty searches with a timestamp, which is the evidence that `user_2` did not have the decisions at that time.

## The cast

The scripts use a restaurant story so the flow reads without knowing the code. Each one stands in for a role you would find in an agent system.

| Script | Story role | Agent role | Meko calls |
| --- | --- | --- | --- |
| `chef.py` | Head chef decides the menu | A worker agent that makes decisions (your coding agent, a research agent) | `memory_add`, four records, under `chef:menu-demo` |
| `kitchen_manager.py` | Kitchen manager works out what to buy | A second worker under the same Meko user account that consumes those decisions (planner, executor) | `memory_search`, `knowledgebase_search`, then `memory_add`, three records, under its own agent_id |
| `chef.py --promote` | The chef publishes the decided dishes | An orchestrator or governance policy that decides what becomes team knowledge | `memory_search`, a rule in code, `memory_promote` |
| `restaurant_manager.py` | Restaurant manager prints the menu | A consumer under another Meko user account (a reviewer agent, a teammate's agent) | both searches; stops if nothing is visible |
| `promote.py` | A person chooses dishes to publish | Human-in-the-loop review | `memory_promote`, one y/n per memory |
| `prune.py` | Clearing the pantry | Memory hygiene | `memory_delete_by_id`, `memory_update` |
| Observe hub (UI) | The kitchen log | Observability | every call, under one trace id per run |

The words: a **datapack** is the workspace. A **memory** belongs to your Meko user account; every agent you run can read it, and each row keeps the agent_id that wrote it. **Shared Knowledge** is the datapack's; everyone it is shared with can read it. **Promote** moves a memory into Shared Knowledge, one way, and needs an owner or maintainer key. A **trace** is the record of one run.

## What it demonstrates

**The code decides what is persisted.** Meko has two ways to write. `conversation_add_message` stores a turn in the trace and extracts memories from its input side only; the extractor rewrites what it reads and may keep nothing. `memory_add` stores your text as one memory, as written. The decisions live in the model's answer, so `record_decision()` writes them with `memory_add`; the model never touches Meko. The scripts still post each run to the trace with `conversation_add_message`, with a short label in `input` and the question in `output`, because a question in `input` becomes a memory of its own and outranks the real decisions in search.

**Memory is per Meko user account, labeled by agent.** Step 2 reads step 1's records because both run under `user_1`; the agent_id on each row is a label, not a wall. Step 3 reads nothing because it runs under `user_2`.

**Promotion is the gate, and it can be code.** Nothing becomes team knowledge until something promotes it: a rule in `chef.py --promote`, a person in `promote.py`, or a click in the Learnings tab. It goes one way.

**Every call is traced.** `meko.py` routes each call through one function that attaches the datapack, the agent_id, and the trace id.

## Use a model instead of the example answers

Set `MODEL_PROVIDER` in `.env` to `anthropic`, `bedrock`, or `vertex` and fill in that provider's lines; `.env.example` lists them (an API key for Anthropic, a Bedrock API key and region, Application Default Credentials and a project for Gemini Enterprise Agent Platform, formerly Vertex AI). Then change `QUESTION` in `chef.py` to a decision from your own project and `QUERY` in all three scripts to describe what to recall. With no model, `chef.py` uses the example answer in `chef_example.json` whatever `QUESTION` says, and `kitchen_manager.py` only knows the dishes in `kitchen_manager_example.json`.

## Troubleshooting

- `MEKO_AGENT_ID is not set`: the command was run without the `MEKO_AGENT_ID=...` prefix.
- `MEKO_DATAPACK_ID is ... not a datapack id`: you pasted the datapack's name. It needs the UUID from the datapack's page.
- Step 3 shows rows: the datapack is not empty. Start over, below.
- Step 4 fails on `memory_promote`: your key is not an owner or maintainer on the datapack.
- Step 4 prints `nothing promoted`: the policy approved nothing, which means step 1 did not run against this datapack.
- Step 5 shows `shared knowledge: 0 results`: step 4 did not run on your key, or the teammate is not on the datapack.

## Start over

Promotion is one way, so an empty datapack means a new datapack. Create one at cloud.mekodata.ai, put its UUID in `MEKO_DATAPACK_ID` in both `.env` and `.env.teammate`, share it with the second Meko user account again (membership belongs to the datapack), and run step 3 once: `memory: 0 results` and `shared knowledge: 0 results` means it is clean. To remove single memories and keep the datapack, use `prune.py`. If a key appeared on screen, revoke it in the dashboard and create a new one; `.env` and `.env.teammate` are git-ignored.

Questions and what you built go to the [Meko Discord](https://discord.gg/yugabyte).
