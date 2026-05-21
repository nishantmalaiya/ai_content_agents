"""
Agent 04 - Viral Hook Generator
Generates viral hook variations for the reel, matched to best-performing competitor posts.
"""
import os, json

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class HookGenerator:
    def __init__(self, openai_key=None):
        self.api_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.client = None
        if self._has_valid_api_key() and OpenAI:
            self.client = OpenAI(api_key=self.api_key, timeout=15.0)

    def _has_valid_api_key(self):
        return bool(self.api_key and self.api_key != "your_openai_api_key_here")

    def generate(self, topic, context=None, emit_progress=None):
        if emit_progress: emit_progress("Generating hooks...", 20)

        if not self.client:
            raise RuntimeError("Hook generator requires a valid OpenAI API key. No static hook fallback is enabled.")

        hooks = self._generate_with_ai(topic, context)
        if not hooks:
            raise RuntimeError("OpenAI returned no hooks.")

        # Pick recommended hook
        best = max(hooks, key=lambda h: h.get("confidence", 0))
        best["recommended"] = True

        if emit_progress: emit_progress("✓ Hooks ready", 100)

        return {
            "topic": topic,
            "hooks": hooks,
            "recommended": best,
            "recommendation_reason": f"'{best['hook']}' uses the {best['pattern']} pattern, "
                                     f"which historically gets the highest engagement in this niche.",
        }

    def _generate_with_ai(self, topic, context):
        sys = (
            "Generate exactly 5 hooks for a reel. Rules:\n"
            "- Max 2 lines each, speakable in under 4 seconds\n"
            "- Hinglish — natural mix, not forced\n"
            "- Never start with 'Aaj main' or 'Is video mein'\n"
            "- Each hook uses a different pattern:\n"
            "  1. Aspirational ('Aisi honi chahiye X')\n"
            "  2. Pain Point (name a frustration)\n"
            "  3. Exclusivity ('Log nahi jaante')\n"
            "  4. Number claim (specific result)\n"
            "  5. Curiosity gap (unanswerable question)\n\n"
            "For each hook, cite which provided top-performing post it best matches by hook/title and views.\n"
            "Return JSON with key hooks, an array of exactly 5 objects: "
            "{hook, pattern, confidence (1-10), matched_post, matched_views, reasoning}"
        )
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys},
                {"role": "user", "content": f"Topic: {topic}. Context: {json.dumps(context or {})}"},
            ],
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        hooks = data if isinstance(data, list) else data.get("hooks", [data])
        for h in hooks:
            h.setdefault("confidence", 7)
            h.setdefault("pattern", "Unknown")
            h.setdefault("matched_post", "")
            h.setdefault("matched_views", 0)
            h.setdefault("recommended", False)
        return hooks[:5]
