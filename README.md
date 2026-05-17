# Finance Agent

AI finance companion for Priya Sharma. Memory-persistent two-session agent built for the GoReach AI Engineer assignment.

## Setup

**1. Install dependencies**
```bash
pip install google-genai python-dotenv
```

**2. Configure your API key**

Create a `.env` file:
```
GEMINI_API_KEY=your_gemini_api_key_here
```

## Project structure

```
finance-agent/
├── agent.py                # Agent loop, memory layer, tool dispatch, analytics
├── tools.py                # Provided — four mock tool functions, do not modify
├── memory.json             # Created at runtime after Session 1
├── writeup.md              # One-page writeup (4 questions)
├── .env                    # Your API key (never commit)
├── requirements.txt
└── README.md
```

## Running

**Session 1 (Monday, Nov 3):**
```bash
python agent.py 1
```

**Session 2 (Thursday, Nov 6):**
```bash
python agent.py 2
```

The entry point flips `CURRENT_SESSION` in `tools.py` automatically based on the argument — no manual edit needed.

Memory persists between runs via `memory.json`.

## Architecture

### Agent loop
Handwritten ReAct-style loop in `run_turn()`. The LLM signals tool needs by emitting a JSON action block:

```json
{"action": "tool_call", "tool": "<name>", "params": {...}}
```

The loop detects this, calls the Python function from `tools.py`, injects the result back as a user-role message, and re-calls the LLM. This repeats until the LLM produces prose — the final response.

### Code-side analytics
When `get_recent_transactions` or `get_upcoming_bills` returns data, Python post-processes the result to compute category breakdowns and totals *before* passing it to the LLM. The model never does arithmetic — it references pre-computed numbers. This eliminates summation errors.

### Memory layer
After Session 1 completes, a dedicated LLM call extracts only decisions and commitments into a fixed JSON schema and writes to `memory.json`. Session 2 reads this file and injects it into the system prompt before the conversation begins.

What's stored: savings plan targets, transfer date, reminder confirmations, session summary.
What's not stored: raw transactions, account balances, bills — these are always fetched live via tools.

### Rate limiting
Gemini free tier allows 15 RPM for gemini-3.1-flash-lite. The agent tracks time between LLM calls and sleeps only the remaining gap needed to stay within that limit — no fixed blanket sleep. On 429, it backs off with increasing wait times before retrying.

### Tool vs. LLM discipline
- **LLM decides:** which tools to call, whether a purchase conflicts with a savings plan, how to frame advice
- **Python decides:** category sums, date filtering, bills totals, memory serialisation, rate limiting
