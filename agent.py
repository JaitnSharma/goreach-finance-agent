import json
import os
import sys
import time
import tools as T
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MEMORY_PATH = "memory.json"
MONTHLY_SAVINGS_TARGET = 1_500_000 // 24
MIN_CALL_INTERVAL = 3.0

USER_PROFILE = {
    "name": "Priya Sharma",
    "age": 28,
    "city": "Bangalore",
    "monthly_income_inr": 120000,
    "stated_goal": "Save ₹15 lakh in 2 years for a house down payment in Bangalore",
}

TOOL_SCHEMAS = {
    "get_recent_transactions": {
        "description": "Transactions for last N days. Returns transactions plus computed category totals.",
        "params": {"days": "int"},
    },
    "get_account_balance": {
        "description": "Current balances: checking, savings, house_fund, mutual_funds (INR).",
        "params": {},
    },
    "get_upcoming_bills": {
        "description": "Scheduled bills due in next N days. Returns bills plus computed total.",
        "params": {"days": "int (default 30)"},
    },
    "set_reminder": {
        "description": "Set a reminder. Returns confirmation with reminder_id.",
        "params": {"date": "YYYY-MM-DD", "content": "string"},
    },
}

MEMORY_SCHEMA = """{
  "commitments": [
    {
      "category": "<string: e.g. food_delivery, house_fund, rent, investment, loan>",
      "action": "cap_monthly" | "transfer_once" | "reduce_by_pct" | "pay_by",
      "value": <int>,
      "by_date": "<YYYY-MM-DD>"
    }
  ],
  "reminders_set": [
    {"date": "<YYYY-MM-DD>", "content": "<string>", "reminder_id": "<string>"}
  ],
  "expenditure_profile": {
    "high_spend_categories": ["<category>", "..."],
    "impulse_triggers": "<what prompts unplanned spending, or 'not sufficient data yet'>",
    "awareness_level": "low | moderate | high | not sufficient data yet"
  },
  "behavioral_anchors": {
    "responds_to": "<framing that drives action: hard numbers, guilt, goal-tracking, peer comparison — or 'not sufficient data yet'>",
    "commitment_style": "impulsive | deliberate | avoidant | not sufficient data yet",
    "follow_through_signals": "<evidence of whether they act on advice or stall — or 'not sufficient data yet'>"
  },
  "risk_appetite": "conservative | moderate | aggressive | not sufficient data yet",
  "decision_triggers": "<events that prompt financial action: salary credit, peer influence, fear of missing goal — or 'not sufficient data yet'>",
  "session_summary": "< use compressed context anchoring for summaries the whole instance including previous sessions in this instance >",
  "last_session_date": "<YYYY-MM-DD>"
}"""

# ── Memory ───────────────────────────────────────────────────────────────────
def load_memory() -> dict:
    if os.path.exists(MEMORY_PATH):
        with open(MEMORY_PATH) as f:
            return json.load(f)
    return {}  # no prior session


def save_memory(mem: dict) -> None:
    with open(MEMORY_PATH, "w") as f:
        json.dump(mem, f, indent=2)
    log(f"[MEMORY WRITE] {MEMORY_PATH} updated")

# ── Tool dispatch ────────────────────────────────────────────────────────────
def call_tool(name: str, params: dict) -> Any:
    fn = T.TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    result = fn(**params)
    log(f"[TOOL CALL] {name}({params}) → {result}")

    if name == "get_recent_transactions":  # attach category sums so LLM never does arithmetic
        categories = set(t["category"] for t in result if t["amount"] < 0)
        breakdown = {cat: sum(abs(t["amount"]) for t in result
                             if t["category"] == cat and t["amount"] < 0)
                     for cat in categories}
        return {"transactions": result, "category_totals": breakdown,
                "total_debits": sum(breakdown.values())}
    if name == "get_upcoming_bills":  # same reason — total pre-computed
        return {"bills": result, "total_due": sum(b["amount"] for b in result)}
    return result


def log(msg: str) -> None:
    print(msg, flush=True)

# ── System prompt ────────────────────────────────────────────────────────────
def build_system_prompt(memory: dict, today: str) -> str:
    role = (
        "<role>You are a sharp, honest AI finance companion — not a generic assistant. "
        "Be direct and brief: 3-5 sentences, peer-level tone, no filler.</role>"
    )

    profile = (
        "<profile>\n"
        f"User: {USER_PROFILE['name']}, {USER_PROFILE['age']}, {USER_PROFILE['city']}\n"
        f"Income: ₹{USER_PROFILE['monthly_income_inr']:,}/month (post-tax, credited on the 1st)\n"
        f"Goal: {USER_PROFILE['stated_goal']}\n"
        f"Required monthly savings: ₹{MONTHLY_SAVINGS_TARGET:,}\n"
        f"Today: {today}\n"
        "</profile>"
    )

    mem_block = (  # populated from disk in Session 2, empty in Session 1
        "<memory>\n"
        f"Prior session memory (loaded from disk):\n{json.dumps(memory, indent=2)}\n\n"
        f"Key commitments: {memory.get('session1_summary', '')}\n"
        "</memory>"
    ) if memory else "<memory>No prior session memory.</memory>"

    tool_block = (
        "<tools>\n"
        f"Available tools:\n{json.dumps(TOOL_SCHEMAS, indent=2)}\n\n"
        "Always respond with a JSON object in this exact format:\n"
        "{\n"
        '  "have_unfinished_business": "yes" | "no",\n'
        '  "tool": "<tool_name>",\n'
        '  "params": {...},\n'
        '  "message": "<your response to the user>"\n'
        "}\n\n"
        "have_unfinished_business rules:\n"
        '- "yes": you need the tool result back to reason further before giving final advice '
        "(e.g. get_account_balance, get_upcoming_bills, get_recent_transactions). "
        "Include message only for internal context if needed.\n"
        '- "no": tool runs as a side-effect and you are done '
        "(e.g. set_reminder). Put your final advice in message.\n"
        '- "no" with no tool: pure advice response. Put it in message.\n'
        "Never quote stale numbers from memory when a tool can give current data.\n"
        "Tool results include pre-computed totals — use those numbers directly.\n"
        "</tools>"
    )

    rules = (
        "<rules>\n"
        "1.. Use tools for live data (balances, transactions, bills). Memory is for decisions only\n"
        "2. Do not compute arithmetic yourself — tool results include computed totals.\n"
        "3. When evaluating any purchase or financial decision, ALWAYS check both "
        "get_account_balance AND get_upcoming_bills first.\n"
        "4. When the user discusses a future action, proactively set a reminder "
        "using set_reminder — do not ask, just do it.\n"
        "5. Only recommend actions the user can take themselves. Your scope: advise, remind, analyse.\n"
        "</rules>"
    )

    return "\n\n".join([role, profile, mem_block, tool_block, rules])

# ── Gemini client ────────────────────────────────────────────────────────────
def make_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not found. Set it in .env or environment.")
    return genai.Client(api_key=api_key)

_last_call_time: float = 0.0

def call_llm(
    client: genai.Client,
    system: str,
    conversation: list[dict],
    retries: int = 3,
) -> str:
    global _last_call_time

    contents = []
    for msg in conversation:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(
            role=role, parts=[types.Part(text=msg["content"])],
        ))

    for attempt in range(retries):
        elapsed = time.time() - _last_call_time
        wait = MIN_CALL_INTERVAL - elapsed
        if wait > 0:
            time.sleep(wait)
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=1024,
                    temperature=0.2,
                ),
            )
            _last_call_time = time.time()
            return response.text.strip()
        except Exception as e:
            _last_call_time = time.time()
            if "429" in str(e) and attempt < retries - 1:
                backoff = 15 * (attempt + 1)
                log(f"[RATE LIMIT] 429 hit, backing off {backoff}s...")
                time.sleep(backoff)
            else:
                raise

# ── Agent loop ───────────────────────────────────────────────────────────────
def parse_response(raw: str) -> dict:
    """Parse LLM response as structured JSON. Falls back to plain prose if parsing fails."""
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"have_unfinished_business": "no", "message": raw}


def run_turn(client: genai.Client, conversation: list[dict], system: str) -> str:
    """ReAct loop — routes each LLM response based on have_unfinished_business flag."""
    for _ in range(8):
        raw = call_llm(client, system, conversation)
        log(f"[LLM RAW] {raw}")

        parsed = parse_response(raw)
        tool_name = parsed.get("tool")
        params = parsed.get("params", {})
        message = parsed.get("message", "")
        unfinished = parsed.get("have_unfinished_business", "no") == "yes"

        if tool_name:
            result = call_tool(tool_name, params)
            if unfinished:
                # LLM needs the result to reason further — feed it back and loop
                conversation.append({"role": "assistant", "content": raw})
                conversation.append({
                    "role": "user",
                    "content": f"[TOOL RESULT: {tool_name}]\n{json.dumps(result, indent=2)}",
                })
                continue
            else:
                # fire-and-forget tool (e.g. set_reminder) — execute silently, return message
                return message

        return message or raw

    return "[Agent loop exceeded max iterations]"

# ── Memory extraction ────────────────────────────────────────────────────────
def extract_and_save_memory(client: genai.Client, conversation: list[dict], system: str) -> None:
    """Separate prompt from the main one — enforces strict JSON output, no conversational text."""
    prompt = (
        "Extract the memory that must persist to the next session.\n"
        f"Respond ONLY with valid JSON matching this schema (no prose, no markdown fences):\n"
        f"{MEMORY_SCHEMA}\n"
        "Extract only what was explicitly committed to. Do not invent details."
    )
    msgs = conversation + [{"role": "user", "content": prompt}]
    raw = call_llm(client, system, msgs)
    log(f"[MEMORY EXTRACTION RAW] {raw}")

    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1].lstrip("json").strip()

    try:
        save_memory(json.loads(clean))
    except json.JSONDecodeError as e:
        log(f"[ERROR] Memory extraction parse failed: {e}\n{raw}")

# ── Session runner ───────────────────────────────────────────────────────────
def run_session(session_num: int, user_turns: list[str]) -> None:
    today = "2025-11-03" if session_num == 1 else "2025-11-06"
    log(f"\n{'='*60}\nSESSION {session_num} — {today}\n{'='*60}\n")

    memory = load_memory()
    log(f"[MEMORY READ] Loaded:\n{json.dumps(memory, indent=2)}\n" if memory
        else "[MEMORY READ] No prior memory found.\n")

    client = make_client()
    system = build_system_prompt(memory, today)
    conversation = []

    for i, user_msg in enumerate(user_turns, 1):
        log(f"\n--- Turn {i} ---")
        log(f"[USER] {user_msg}")
        conversation.append({"role": "user", "content": user_msg})
        response = run_turn(client, conversation, system)
        conversation.append({"role": "assistant", "content": response})
        log(f"[AGENT] {response}")

    log("\n[POST-SESSION] Extracting memory...")
    extract_and_save_memory(client, conversation, system)

    log(f"\n{'='*60}\nSESSION {session_num} COMPLETE\n{'='*60}\n")

# ── Session definitions ──────────────────────────────────────────────────────
SESSION_1_TURNS = [
    "I just got my salary credited. Help me figure out how much I can realistically save this month.",
    "I feel like I'm spending too much on food delivery. How much did I actually spend on it last month?",
    "Okay that's worse than I thought. Let's say I want to cut that in half AND put aside ₹30,000 "
    "for my house fund this month — is that realistic given my upcoming bills?",
    "Got it. Remind me to actually transfer the ₹30,000 to my house fund on the 25th.",
]

SESSION_2_TURNS = [
    "Hey, my colleague is selling his MacBook for ₹80,000, barely used. "
    "I've been wanting to upgrade. Should I buy it?",
]


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("1", "2"):
        print("Usage: python agent.py 1   or   python agent.py 2")
        sys.exit(1)

    session = int(sys.argv[1])
    T.CURRENT_SESSION = session
    run_session(session, SESSION_1_TURNS if session == 1 else SESSION_2_TURNS)
