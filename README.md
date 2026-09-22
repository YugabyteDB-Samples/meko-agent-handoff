# meko-agent-handoff

Three small Python scripts that show how agents share what they learn through [Meko](https://cloud.mekodata.ai), over MCP. One records decisions. One reads them back in a new process. One runs on a second account and gets nothing until a rule in code shares them. Every read and write lands in a trace.

No model key is needed. In place of a model, the scripts use example answers stored in JSON files, so a free Meko account is enough to run all five steps.

This is the code from the webinar "Shared Memory for AI Coding Agents: A Live Build with Meko".

## The cast

The scripts use a restaurant story so the flow reads without knowing the code. Each one stands in for a role you would find in an agent system.

| Script | Story role | Agent role | Meko calls |
| --- | --- | --- | --- |
| `chef.py` | Head chef decides the menu | A worker agent that makes decisions (your coding agent, a research agent) | `memory_add`, four records, under `chef:menu-demo` |
| `kitchen_manager.py` | Kitchen manager works out what to buy | A second worker on the same account that consumes those decisions (planner, executor) | `memory_search`, `knowledgebase_search`, then `memory_add`, three records, under its own agent_id |
| `chef.py --promote` | The chef publishes the decided dishes | An orchestrator or governance policy that decides what becomes team knowledge | `memory_search`, a rule in code, `memory_promote` |
| `restaurant_manager.py` | Restaurant manager prints the menu | A consumer on another account (a reviewer agent, a teammate's agent) | both searches; stops if nothing is visible |
| `promote.py` | A person chooses dishes to publish | Human-in-the-loop review | `memory_promote`, one y/n per memory |
| `prune.py` | Clearing the pantry | Memory hygiene | `memory_delete_by_id`, `memory_update` |
| Observe hub (UI) | The kitchen log | Observability | every call, under one trace id per run |

The words: a **datapack** is the workspace. A **memory** belongs to your account; every agent you run can read it, and each row keeps the agent_id that wrote it. **Shared Knowledge** is the datapack's; everyone it is shared with can read it. **Promote** moves a memory into Shared Knowledge, one way, and needs an owner or maintainer key. A **trace** is the record of one run.

## How a decision travels

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/handoff-dark.gif">
  <img src="docs/handoff-light.gif" width="900" alt="Animated diagram of the five runs: the chef writes to your memory, the kitchen manager reads it and adds notes, the teammate's restaurant manager sees nothing, the chef promotes the decided dishes through the gate into Shared Knowledge, and the restaurant manager reads them back">
</picture>

Purple is your account, orange is the gate, green is Shared Knowledge, gray is the teammate. Step 3 runs before the gate, so the empty result proves the isolation; step 5 is the same command after it.

## If you are an AI agent running this for a person

You can clone, install, edit `.env`, run the five commands, and read the output yourself. You cannot create the account, the datapack, the API keys, or share the datapack; those happen in the Meko dashboard, so ask the person for them. What you need from them:

1. A Meko account at [cloud.mekodata.ai](https://cloud.mekodata.ai), a datapack in it, and an API key. Ask for the key and the datapack's UUID (the id on the datapack's page, not its name).
2. For steps 3 and 5, a second Meko account with its own API key, and the datapack shared with it. If they do not have one, run every step on the one key. Step 3 then prints the menu straight away, with each dish labeled `(memory)` rather than `(Shared Knowledge)`, because your own memory_search already sees the decisions; the "nothing visible" moment needs the second account.
3. Leave `MODEL_PROVIDER` empty unless they hand you a model key. The example answers cover everything below.

Compare each run with the expected output in the Run section. If it differs, check Troubleshooting before changing code.

## Set up

1. Python 3.13 or later and [uv](https://docs.astral.sh/uv/).
2. `git clone git@github.com:YugabyteDB-Samples/meko-agent-handoff.git && cd meko-agent-handoff && uv sync`
3. `cp .env.example .env`, then fill in `MEKO_API_KEY` and `MEKO_DATAPACK_ID`. Leave `MODEL_PROVIDER` empty.
4. For the teammate steps: `cp .env .env.teammate`, replace `MEKO_API_KEY` with the second account's key, keep the same `MEKO_DATAPACK_ID`.

Every command sets `MEKO_AGENT_ID`, the name the script writes under. It is required; the scripts stop with a message saying so if it is missing.

## Run it

Start from an empty datapack. Steps 1, 2 and 4 run on your key; steps 3 and 5 run on the teammate's key through `ENV_FILE`.

**1. Record.** `MEKO_AGENT_ID=chef:menu-demo uv run chef.py`

Expect a `trace:` id, then four `recorded:` lines: three `DECISION:` records and one `OPEN_QUESTION:`. The script has no Meko tools in the model's hands; plain Python wrote each finding with `memory_add`, as written. With no model configured the answer is replayed from `chef_example.json`, so the four lines are the same every time.

**2. Recall on the same account.** `MEKO_AGENT_ID=kitchen-manager:menu-demo uv run kitchen_manager.py`

Expect `memory: 4 results`, each tagged `[chef:menu-demo]`, and `shared knowledge: 0 results`. Then three `recorded: INGREDIENTS:` lines under its own agent_id and a `# To buy` list. A new process found the first script's records because memory is per account, and the labels say who wrote what.

**3. Recall on the teammate's account.** `ENV_FILE=.env.teammate MEKO_AGENT_ID=restaurant-manager:menu-demo uv run restaurant_manager.py`

Expect `memory: 0 results`, `shared knowledge: 0 results`, and `The menu is not ready yet. Nothing has been shared with the team.` Nothing has been promoted, so the other account sees nothing and the script stops rather than guess.

**4. Share by policy.** `MEKO_AGENT_ID=chef:menu-demo uv run chef.py --promote`

Expect a verdict for every private record it finds: `PROMOTE` for the three decisions, `KEEP` for the open question and for the kitchen's ingredient notes, each with its reason. Then the `memory_promote` result with three ids. The rule is in `allowed_by_policy()`: a decision with a reason is shared, an open question is not, and another agent's notes are not. It runs under `chef:menu-demo`, so the trace shows which agent shared what.

**5. Recall on the teammate's account again.** Same command as step 3.

Expect `memory: 0 results`, `shared knowledge: 3 results`, each tagged `[chef:menu-demo]`, then the menu with `Decided by: chef:menu-demo (Shared Knowledge)` under each dish. The open question and the ingredients are not there; they were never shared.

Each run prints a trace id. Open it in the Observe hub for the datapack at cloud.mekodata.ai to see the run call by call: the question, the answer, the reasoning, each search and its results, each memory written. The trace from step 3, with both searches empty and a timestamp, is the one to keep.

## What it demonstrates

**The code decides what is persisted.** Meko has two ways to write. `conversation_add_message` stores a turn in the trace and extracts memories from its input side only; the extractor rewrites what it reads and may keep nothing. `memory_add` stores your text as one memory, as written. The decisions live in the model's answer, so `record_decision()` writes them with `memory_add`; the model never touches Meko. The scripts still post each run to the trace with `conversation_add_message`, with a short label in `input` and the question in `output`, because a question in `input` becomes a memory of its own and outranks the real decisions in search.

**Memory is per account, labeled by agent.** Step 2 reads step 1's records because both run under your account; the agent_id on each row is a label, not a wall. Step 3 reads nothing because it runs under a different account.

**Promotion is the gate, and it can be code.** Nothing becomes team knowledge until something promotes it: a rule in `chef.py --promote`, a person in `promote.py`, or a click in the Learnings tab. It goes one way.

**Every call is traced.** `meko.py` routes each call through one function that attaches the datapack, the agent_id, and the trace id.

## Use a model instead of the example answers

Set `MODEL_PROVIDER` in `.env` to `anthropic`, `bedrock`, or `vertex` and fill in that provider's lines; `.env.example` lists them (an API key for Anthropic, a Bedrock API key and region, Application Default Credentials and a project for Gemini Enterprise Agent Platform, formerly Vertex AI). Then change `QUESTION` in `chef.py` to a decision from your own project and `QUERY` in all three scripts to describe what to recall. With no model, `chef.py` uses the example answer in `chef_example.json` whatever `QUESTION` says, and `kitchen_manager.py` only knows the dishes in `kitchen_manager_example.json`.

`context_search` searches both scopes in one call; this repo uses the two direct calls because, when we tested it, `context_search` returned nothing for promoted memories that `knowledgebase_search` found.

## Troubleshooting

- `MEKO_AGENT_ID is not set`: the command was run without the `MEKO_AGENT_ID=...` prefix.
- `MEKO_DATAPACK_ID is ... not a datapack id`: you pasted the datapack's name. It needs the UUID from the datapack's page.
- Step 3 shows rows: the datapack is not empty. Start over, below.
- Step 4 fails on `memory_promote`: your key is not an owner or maintainer on the datapack.
- Step 4 prints `nothing promoted`: the policy approved nothing, which means step 1 did not run against this datapack.
- Step 5 shows `shared knowledge: 0 results`: step 4 did not run on your key, or the teammate is not on the datapack.

## Start over

Promotion is one way, so an empty datapack means a new datapack. Create one at cloud.mekodata.ai, put its UUID in `MEKO_DATAPACK_ID` in both `.env` and `.env.teammate`, share it with the second account again (membership belongs to the datapack), and run step 3 once: zero and zero means it is clean. To remove single memories and keep the datapack, use `prune.py`. If a key appeared on screen, revoke it in the dashboard and create a new one; `.env` and `.env.teammate` are git-ignored.

Questions and what you built go to the [Meko Discord](https://discord.gg/yugabyte).
