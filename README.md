# Home Repair Chatbot

CLI LangGraph chatbot for diagnosing home-repair problems. It remembers users and past repairs in PostgreSQL, runs a guided intake + web search, recommends tools/parts from a catalog, and records resolution notes.

## Stack

- **Python** 3.10+
- **LangGraph** — conversation graph and routing
- **OpenAI** — email/component-type/manufacturer normalization, yes/no and satisfaction parsing, tool extraction and selection parsing, and writing the short `ResolutionDetail` note and last-resolution recap (default model `gpt-4o-mini`)
- **Tavily** — repair search (optional; mock answer if `TAVILY_API_KEY` is unset)
- **PostgreSQL** — users, components, searches, tools

## Conversation flow

```
Initializer → TavilySearch → ToolRecommendation → CheckResult
                  ↑                                    │
                  └────────────────────────────────────┘
      not fixed (search again, optionally with a follow-up problem)
      fixed + "another repair?" yes (start a new component)
```

| Node | Role |
|------|------|
| **Initializer** | Collect email; create or load user (new users give `StreetAddress \| City \| State \| Zip` and a Preference); greet; for returning users, recap the last `ResolutionDetail` and ask if it is settled — satisfied marks that component resolved and starts a new one, otherwise resumes the same component with a new problem |
| **TavilySearch** | Intake (type → optional reuse of same type → manufacturer → problem); search; save `SearchResult` |
| **ToolRecommendation** | Extract tools/parts from search; match `ToolRecommandation` catalog; save chosen items to `ToolSelected` |
| **CheckResult** | Capture satisfaction + resolution summary; mark resolved or chain a new search; offer another job |

Component types are free-form `SCREAMING_SNAKE_CASE` names stored in `ComponentType` (seeded examples: `SINK`, `TOILET`, `WATER_HEATER`). Unknown types are added via `add_component_type` during intake.

New users are asked for an answer **Preference** (`concise` or `detail`, default `concise`) before `add_user`. That value is returned by `get_userinfo_from_email` and controls TavilySearch depth (`concise` → top 2 basic results; `detail` → more results + advanced search).

## Project layout

```
HomeRepairChatbot/
├── main.py                 # CLI entrypoint
├── .env.example            # Env template
├── docker-compose.yml      # Optional Postgres 16 container
├── requirements.txt
├── requirements-dev.txt    # pytest
├── db/
│   ├── connection.py
│   ├── schema.sql          # Full schema + seed catalog (fresh databases)
│   ├── migrate_component_type.sql   # Older DBs: enum Type -> ComponentType table
│   └── migrate_user_preference.sql  # Older DBs: add User.Preference
├── tools/                  # One module per DB tool
├── graph/
│   ├── __init__.py         # Graph wiring + route_entry
│   ├── state.py
│   └── nodes/              # initializer, tavily_search, tool_recommendation, check_result, common
└── tests/                  # Mirrors tools/ and graph/
```

## Setup

### 1. Environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY (required). TAVILY_API_KEY is optional.
```

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string |
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Optional; default `gpt-4o-mini` |
| `TAVILY_API_KEY` | Optional; without it, search returns a mock repair answer |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Used by Docker Compose |

### 2. Database

**Option A — Docker Compose**

```bash
docker compose up -d
```

**Option B — local Postgres (e.g. Homebrew)**

```bash
brew services start postgresql@14
# Create role/DB if needed, matching .env values
```

Apply schema + seed data:

```bash
PGPASSWORD=home_repair_pass psql -h localhost -U home_repair_user -d home_repair_db -f db/schema.sql
```

**Existing database?** `schema.sql` only creates missing tables; it does not alter ones that already exist. If your database predates the current schema, run whichever migrations apply:

```bash
# Add User.Preference (safe to re-run)
PGPASSWORD=home_repair_pass psql -h localhost -U home_repair_user -d home_repair_db -f db/migrate_user_preference.sql

# Move from the old enum Type column to the ComponentType table
PGPASSWORD=home_repair_pass psql -h localhost -U home_repair_user -d home_repair_db -f db/migrate_component_type.sql
```

Tables: `User`, `ComponentType`, `HomeComponent`, `SearchResult`, `ToolRecommandation`, `ToolSelected`, and `Session` (created but not used by the app yet).

### 3. Python deps and run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Type `quit` / `exit` / `q` to leave the CLI.

## Database tools (`tools/`)

| Module | Purpose |
|--------|---------|
| `add_user` | Create user (Email + Zip required; Preference `concise`/`detail`, default `concise`); idempotent on email |
| `add_component` | Insert `HomeComponent` (type must exist in `ComponentType`) |
| `add_component_type` | Add normalized type name (e.g. `WATER_HEATER`) |
| `get_component_types` | List known type names |
| `get_userinfo_from_email` | Profile + components (latest first) with nested searches and selected tools |
| `update_home_component` | Update one field (`Type`, `ManufacturerId`, `ProblemDesc`, `ResolutionDetail`, `Resolved`) and refresh timestamp |
| `add_search_result` | Persist Tavily Q&A |
| `get_tool_recommandation` | Catalog lookup (exact, then unique fuzzy; ambiguous matches error) |
| `add_tool_selected` | Save a tool/part the user chose for a component |

## Tests

Unit tests mock Postgres and LLM calls (no live DB/API required):

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Layout mirrors the app: `tests/tools/`, `tests/graph/`, `tests/graph/nodes/`.
