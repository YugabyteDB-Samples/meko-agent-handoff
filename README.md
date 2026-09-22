# meko-agent-handoff

Three small Python agents that share what they learn through Meko.

The first, `chef.py`, decides what goes on a bistro's autumn menu and saves each decision it reaches. The second, `kitchen_manager.py`, starts in a new terminal with nothing in its memory, reads those dishes back, works out what each one needs, and saves that too. The third, `restaurant_manager.py`, runs on a teammate's account and can only publish the menu once the chef has shared the decided dishes.

The chef is built to call a model, and it will if you give it one. If you do not, it replays a recorded model answer from `chef_example.json`, so the record and recall parts of the demo run with nothing but a Meko key.

This is the code from the webinar "Shared Memory for AI Coding Agents: A Live Build with Meko".

## Words used in this repo

| Word | What it means here |
| --- | --- |
| Agent | A Python script that sends a question to a model and does something with the answer. There is no framework magic here. Each one is a short script you can read top to bottom. |
| Meko | The service where decisions are stored. Your code talks to it over MCP, a standard way for a program to call tools on a server. |
| Datapack | Your workspace in Meko. Everything in this repo happens inside one datapack. |
| Memory | A fact an agent saved. Your memories can be read by every agent you run, and each one records which agent wrote it. Nobody else on the datapack can read them. |
| Shared Knowledge | The part of the datapack everyone can read. Files you upload go here, and so do memories you choose to promote. |
| Trace | The record of one run. Every call an agent makes to Meko is listed under it, with what was sent and what came back. |
| Promote | Move a memory into Shared Knowledge. What that does is authorize the agents of the other Meko user accounts on the datapack to read that record. Only an owner or maintainer can promote, and it goes one way. |

## What each file does

| File | What it does |
| --- | --- |
| `chef.py` | Asks the model what to add to the menu, then saves each finding to Meko with `memory_add`. The model has no Meko tools, so it cannot decide what gets saved. With no `MODEL_PROVIDER` set, it replays the answer in `chef_example.json`. Run it again with `--promote` and a rule in code moves the decided dishes into Shared Knowledge. |
| `chef_example.json` | A recorded model answer to the menu question: three dishes and one open question. The chef replays this when no model is configured. |
| `kitchen_manager.py` | Reads your memories with `memory_search` and the team's Shared Knowledge with `knowledgebase_search`, keeps the decided dishes, works out what each needs, and saves one INGREDIENTS memory per dish under its own agent name. If it finds no dish, it stops instead of guessing. |
| `kitchen_manager_example.json` | The ingredients for each dish in `chef_example.json`. The kitchen manager looks dishes up here when no model is configured. |
| `restaurant_manager.py` | Runs with a teammate's token. Searches both scopes and publishes the menu from the decided dishes it can see. Until the chef promotes, it sees nothing and says the menu is not ready. |
| `promote.py` | Promotes from the terminal, asking you y or n for each memory. The person-in-the-loop version of `chef.py --promote`. |
| `prune.py` | Finds memories that never match the questions your project asks and offers to delete or correct them. |
| `meko.py` | The shared plumbing. Every Meko call goes through one function that attaches your datapack, the agent name, and the trace id. It also posts each run's question, answer, reasoning, and plan to the trace. |
| `meko_client.py` | Connects to Meko over MCP and picks the model provider from your `.env`. |

## How a decision travels

```mermaid
flowchart TD
C["chef.py"] -->|"1. memory_add, four records"| M[("Your memory")]
M -->|"2. memory_search"| K["kitchen_manager.py, your key"]
K -->|"3. memory_add, one note per dish"| M
M -.->|"4. nothing visible"| R1["restaurant_manager.py, teammate's key"]
M -->|"5. chef.py --promote, decided dishes only"| S[("Shared Knowledge")]
S -->|"6. knowledgebase_search"| R2["restaurant_manager.py, teammate's key"]
```

The kitchen manager finds the dishes in step 2 because it and the chef run under your Meko user account, and its own notes in step 3 are labeled with its agent name, not the chef's. The restaurant manager runs under a teammate's account, so in step 4 it sees none of it. In step 5 the chef shares the three decided dishes and nothing else: the open question and the kitchen's shopping notes stay private. In step 6 the restaurant manager finds exactly those three in Shared Knowledge and publishes the menu.

## Set up

You need three things.

| What | Where to get it |
| --- | --- |
| Python 3.13 or later and uv | [uv](https://docs.astral.sh/uv/) installs the dependencies. |
| A Meko account | https://cloud.mekodata.ai. Signing up creates a datapack and an API token. Copy the token, and copy the datapack's ID from the datapack page. |
| A model key, if you want live answers | Optional. Anthropic, Amazon Bedrock, or Google's Gemini Enterprise Agent Platform (formerly Vertex AI) all work. Without one, the chef replays a recorded answer, the kitchen manager looks ingredients up in a recorded list, and the restaurant manager formats the menu from the records. |

Then:

```bash
git clone git@github.com:YugabyteDB-Samples/meko-agent-handoff.git
cd meko-agent-handoff
uv sync
cp .env.example .env
```

Open `.env` and fill in `MEKO_API_KEY` and `MEKO_DATAPACK_ID`. That is enough to run everything: with `MODEL_PROVIDER` left empty, the chef replays the recorded answer in `chef_example.json`, the kitchen manager looks each dish up in `kitchen_manager_example.json`, and the restaurant manager formats the menu from the records.

To have them call a model instead, set `MODEL_PROVIDER` to `anthropic`, `bedrock`, or `vertex` and fill in that provider's lines. `.env.example` shows what each one reads: an API key for Anthropic, a Bedrock API key and region for Bedrock, and Application Default Credentials plus a project for Gemini Enterprise Agent Platform.

## Run it

The demo is five runs across two accounts. Add a second Meko user to the datapack first. Copy `.env` to `.env.teammate`, replace `MEKO_API_KEY` with that user's token, and keep the same `MEKO_DATAPACK_ID`.

```bash
MEKO_AGENT_ID=chef:menu-demo uv run chef.py
MEKO_AGENT_ID=kitchen-manager:menu-demo uv run kitchen_manager.py
ENV_FILE=.env.teammate MEKO_AGENT_ID=restaurant-manager:menu-demo uv run restaurant_manager.py
MEKO_AGENT_ID=chef:menu-demo uv run chef.py --promote
ENV_FILE=.env.teammate MEKO_AGENT_ID=restaurant-manager:menu-demo uv run restaurant_manager.py
```

`MEKO_AGENT_ID` is the name each agent saves under. Every memory the scripts print carries it, which is how you tell the chef's records from the kitchen manager's.

1. The chef prints four `recorded:` lines: three dishes and one open question. With no model configured they are the same four every time, and the trace's "Model answer" entry says the answer was replayed.
2. The kitchen manager prints four memory rows, all labeled `chef:menu-demo`, and zero from Shared Knowledge. It keeps the three dishes, prints three `recorded:` lines of its own, then a shopping list with every ingredient and the dish that needs it.
3. The restaurant manager, on the teammate's token, prints zero and zero and stops: the menu is not ready. Your memories are yours.
4. The chef, with `--promote`, searches its memories and prints a verdict for each: PROMOTE for the three dishes, KEEP for the open question and for the kitchen manager's notes. Then it calls `memory_promote` for the three. Promotion needs an owner or maintainer key on the datapack.
5. The restaurant manager runs again: zero in memory, three in Shared Knowledge, each labeled `chef:menu-demo`, and it prints the menu. The open question and the shopping notes are not there, because they were never shared.

Each run prints a trace id. Paste it into the Observe hub for your datapack at cloud.mekodata.ai and you get the run laid out call by call: the question the agent was given, the model's answer, why the code did what it did, each search and what it returned, and each memory written. The restaurant manager's first trace, with both searches empty and a timestamp, is the one to keep.

Meko also has `context_search`, which searches memory and Shared Knowledge in one call. This sample uses the two direct calls because, when we tested it, `context_search` returned nothing for promoted memories that `knowledgebase_search` found.

## Why the chef saves with memory_add

Meko has two ways to write, and they do different things.

`conversation_add_message` stores a question and answer pair in the trace, then reads the question side and pulls facts out of it. The answer side is never read. What gets stored is whatever the extractor decides is a fact, in its own words, and it may decide there is nothing.

`memory_add` stores your text as one memory, as written.

The chef's decisions are in the answer, not the question. If this sample posted the turn, the extractor would read the question, never see the dishes, and save nothing useful. So `record_decision()` calls `memory_add`. The decision is saved every time the loop runs, in the words the model used, and each save shows up in the trace with its text and timing.

The sample still posts each run to the trace with `conversation_add_message`, so the question, the answer, the reasoning, and the plan are all there to read later. It puts a short label in the `input` field and the question in `output`, because a question in `input` becomes a memory of its own and shows up in the kitchen manager's search results above the real decisions.

## Who decides what to share

`chef.py --promote` is an agent promoting by policy. The rule is in code: a record is shared only if it is a decision with a reason. Open questions stay private until settled, and the kitchen manager's notes are not menu items. The chef runs the rule under its own agent name, so the trace shows which agent promoted what. If you would rather a person make the call, `promote.py` walks your memories and asks y or n for each, and the Learnings tab in the Meko UI does the same thing with a click.

## Change the question

Edit `QUESTION` in `chef.py` to a decision from your own project, and set `MODEL_PROVIDER` so the chef and the kitchen manager ask a model. With no model configured, the chef replays `chef_example.json` no matter what `QUESTION` says, and the kitchen manager only knows the dishes in `kitchen_manager_example.json`. The shared `QUERY` in all three scripts describes what to recall, so change it with the question. Everything else stays the same.

## The rule

Memory while you and your agents are still working it out. Shared Knowledge when the team should build on it. Your code makes the write, so the record exists after every run.

## Reset the demo

Every run adds to the datapack: memories from the chef and the kitchen manager, promotions from `chef.py --promote` or the Learnings tab, and one conversation per script run in the Observe hub. Promotion is one way, so once a dish is in Shared Knowledge the only way back to an empty datapack is a new datapack.

To start over:

1. Delete the datapack at cloud.mekodata.ai, or call `datapack_delete` from any MCP client connected to Meko. This removes its memories, its Shared Knowledge, and its traces together. If you want to keep the traces from a run, keep that datapack and make a new one instead.
2. Create a new datapack and copy its ID from the datapack page.
3. Put the new ID in `MEKO_DATAPACK_ID` in both `.env` and `.env.teammate`. The tokens do not change.
4. Add the second Meko user to the new datapack again. Membership belongs to the datapack, so it does not carry over.
5. Run the restaurant manager on the teammate's token once. Both searches should return zero and it should say the menu is not ready. That is your check that the datapack is clean.

If you only want to remove what one run wrote and keep the datapack, `prune.py` deletes or corrects individual memories, and `memory_delete_all` from an MCP client clears every memory at once. Neither undoes a promotion.

If a token appeared on screen during a recording or a shared session, revoke it at cloud.mekodata.ai and create a new one. `.env` and `.env.teammate` are the only places the tokens live in this repo, and both are ignored by git.

Questions and what you built go to the Meko Discord.
