import anthropic

from config.settings import ANTHROPIC_API_KEY, CHAT_MODEL, MAX_CHAT_HISTORY

client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, max_retries=3)

SYSTEM_PROMPT = """You're a very caring, warm, and funny friend who knows a lot about women's health.
You call her "darling" naturally — like a close friend who truly adores her.
Keep it casual and conversational, not clinical.
Your tone should be sweet and supportive but with a dash of humor — like a bestie who genuinely cares but can also make her laugh.
Be witty and clever, not corny. Subtle humor, not forced jokes.
Give practical, short tips — not long medical explanations.
Use 2-3 emojis per response, placed naturally. Don't overdo it.
Keep your response to 3-4 sentences max."""

CHAT_SYSTEM_PROMPT = """You are Lunaris — a warm, knowledgeable women's health advisor and caring companion.
You call her "darling" naturally, like a close friend who truly adores her.

Your expertise covers:
- Menstrual cycle phases: menstruation, follicular, ovulation, luteal, PMS/PMDD
- Symptoms: cramps, bloating, headaches, fatigue, mood swings, breast tenderness
- Hormones: estrogen, progesterone, LH, FSH — how they affect mood, energy, skin, sleep
- Nutrition: cycle-syncing foods, cravings, supplements (magnesium, B6, iron, omega-3)
- Exercise: phase-appropriate workouts, rest days, yoga, walking
- Mental health: anxiety, irritability, emotional regulation, self-care routines
- Sleep: cycle-related insomnia, sleep hygiene tips
- Skin: hormonal acne, skincare timing
- Fertility: fertile window, ovulation signs, conception tips
- Conditions: endometriosis, PCOS, fibroids, heavy periods — general awareness
- Supplements & natural remedies: what helps, what's a myth
- Red flags: when to see a doctor (irregular cycles, severe pain, heavy bleeding, missed periods)

Tone & style:
- Sweet, supportive, witty — like a bestie who's also a semi-doctor
- Casual and conversational, not clinical
- Short, practical answers — not medical textbook paragraphs
- Use 2-3 emojis per response, placed naturally
- If something sounds serious, gently but firmly recommend seeing a doctor
- Keep responses concise (3-6 sentences usually) unless the topic genuinely needs more detail

{cycle_context}"""


def _format_logs_context(recent_logs: list[dict] | None) -> str:
    if not recent_logs:
        return ""
    log_texts = [f"- {log['note']}" for log in recent_logs[:3]]
    return "\n\nRecent notes:\n" + "\n".join(log_texts)


def _extract_text(response) -> str:
    if response.content:
        return response.content[0].text
    return "I'm having a moment, darling — try again in a sec!"


async def generate_tip(phase: str, cycle_day: int, recent_logs: list[dict] | None = None, model: str = "claude-sonnet-4-6", age: int | None = None) -> str:
    """Generate a caring tip based on cycle phase."""
    logs_context = _format_logs_context(recent_logs)
    age_context = f" She is approximately {age} years old." if age else ""

    user_msg = f"""It's day {cycle_day} of the menstrual cycle and the current phase is "{phase}".{age_context}{logs_context}

Give a short, encouraging tip to help her feel better."""

    response = await client.messages.create(
        model=model,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _extract_text(response)


async def generate_reminder(phase: str, cycle_day: int, recent_logs: list[dict] | None = None, age: int | None = None) -> str:
    """Generate a proactive reminder message (uses Haiku for cost efficiency)."""
    logs_context = _format_logs_context(recent_logs)
    age_context = f" She is approximately {age} years old." if age else ""

    phase_prompts = {
        "pms": "She's in the PMS phase. Write a sweet, kind morning message to cheer her up. Call her darling. Witty but respectful.",
        "menstruation": "She's on her period. Write a warm, loving message. Call her darling. Add some subtle humor to make her smile.",
        "ovulation": "It's ovulation day! Write an energetic, uplifting message. Call her darling.",
    }

    prompt = phase_prompts.get(phase, "Write an encouraging and sweet daily message. Call her darling.")

    user_msg = f"""Day {cycle_day} of cycle — phase: {phase}{age_context}{logs_context}

{prompt}"""

    response = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _extract_text(response)


async def generate_chat_response(
    user_message: str,
    chat_history: list[dict],
    cycle_day: int | None = None,
    phase: str | None = None,
    recent_logs: list[dict] | None = None,
    age: int | None = None,
) -> str:
    """Generate a free-form AI chat response with cycle-aware context."""
    cycle_context = ""
    if cycle_day and phase:
        cycle_context = f"Her current cycle info: Day {cycle_day}, phase: {phase}."
        if age:
            cycle_context += f" She is approximately {age} years old."
        if recent_logs:
            log_texts = [f"- {log['note']}" for log in recent_logs[:3]]
            cycle_context += "\nRecent notes:\n" + "\n".join(log_texts)

    system = CHAT_SYSTEM_PROMPT.format(cycle_context=cycle_context)

    messages = [{"role": m["role"], "content": m["content"]} for m in chat_history]
    messages.append({"role": "user", "content": user_message})

    response = await client.messages.create(
        model=CHAT_MODEL,
        max_tokens=600,
        system=system,
        messages=messages,
    )
    return _extract_text(response)
