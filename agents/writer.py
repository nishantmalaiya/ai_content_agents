"""
Agent 03 - Writing Style Script Writer
Studies your writing style and writes reel scripts in your voice using OpenAI GPT.
Returns an error when OpenAI is unavailable instead of using static templates.
"""
import os, json
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class ScriptWriter:
    VOICE_FILE = "voice_profile.json"

    DEFAULT_VOICE = {
        "vocabulary": ["bhai", "dekho", "basically", "game-changer", "legit"],
        "avoid_words": ["leverage", "synergy", "utilize", "henceforth"],
        "sentence_style": "Short and punchy. 5-10 words per sentence max.",
        "structure": "BEAT 1 (problem) → BEAT 2 (solution) → BEAT 3 (proof) → CTA",
        "cta_style": "Comment trigger — 'AI comment karo, main bhej dunga'",
        "hinglish": True,
        "energy": "Excited but authoritative. Fast-paced.",
    }

    def __init__(self, openai_key=None, voice_profile=None, data_dir=None):
        self.api_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.data_dir = Path(data_dir or os.path.join(os.path.dirname(__file__), "..", "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.voice = voice_profile or self._load_voice()
        self.client = None
        if self._has_valid_api_key() and OpenAI:
            self.client = OpenAI(api_key=self.api_key)

    def _has_valid_api_key(self):
        return bool(self.api_key and self.api_key != "your_openai_api_key_here")

    def _load_voice(self):
        vf = self.data_dir / self.VOICE_FILE
        if vf.exists():
            return json.loads(vf.read_text(encoding="utf-8"))
        return None

    def save_voice(self, profile: dict):
        vf = self.data_dir / self.VOICE_FILE
        vf.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
        self.voice = profile

    def analyze_scripts(self, scripts: list) -> dict:
        """Analyze past scripts to build a voice profile."""
        if not self.client:
            raise RuntimeError("Voice analysis requires a valid OpenAI API key.")
        prompt = (
            "Analyze these reel scripts and identify:\n"
            "1. Vocabulary (frequent words, avoided words)\n"
            "2. Sentence style (length, rhythm)\n"
            "3. Structure pattern (how they open, build, close)\n"
            "4. CTA style\n"
            "5. Hinglish patterns\n"
            "6. Energy level\n\n"
            "Return as JSON with keys: vocabulary, avoid_words, sentence_style, "
            "structure, cta_style, hinglish, energy.\n\n"
            "Scripts:\n" + "\n---\n".join(scripts[:30])
        )
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        profile = json.loads(resp.choices[0].message.content)
        self.save_voice(profile)
        return profile

    def write_script(self, topic: str, context: dict = None, emit_progress=None) -> dict:
        """Generate a reel script on the given topic."""
        if emit_progress: emit_progress("Writing script...", 20)

        if not self.client:
            raise RuntimeError("Writer requires a valid OpenAI API key. No static script fallback is enabled.")
        if not self.voice:
            raise RuntimeError("Writer requires a saved voice profile. Analyze 20-30 past scripts first.")

        result = self._write_with_ai(topic, context)
        if emit_progress: emit_progress("Script ready", 100)
        return result

    def _write_with_ai(self, topic, context):
        sys_prompt = (
            "You are a reel script writer. Write in the creator's exact voice.\n"
            f"Voice profile: {json.dumps(self.voice)}\n"
            "Rules:\n"
            "- Structure: [BEAT 1] → [BEAT 2] → [BEAT 3] → [CTA]\n"
            "- Each beat: 2-3 sentences max\n"
            "- Do NOT include a hook (handled by hook agent)\n"
            "- Use Hinglish naturally if the profile says so\n"
            "- Keep it punchy and fast-paced\n"
            "- CTA must be a comment trigger\n"
        )
        user_msg = f"Topic: {topic}"
        if context:
            user_msg += f"\nContext: avg {context.get('avg_views', 'N/A')} views in this niche."
            if context.get("recommendation"):
                user_msg += f"\nValidated recommendation: {context['recommendation']}"
            if context.get("top_posts"):
                user_msg += "\nTop-performing source posts:\n" + json.dumps(context["top_posts"][:5], ensure_ascii=False)

        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        script_text = resp.choices[0].message.content
        beats = self._parse_beats(script_text)
        return {"topic": topic, "full_script": script_text, "beats": beats, "source": "ai"}

    def _parse_beats(self, text):
        beats = {}
        parts = text.split("[BEAT")
        for part in parts[1:]:
            idx = part.strip()[0] if part.strip() else "?"
            content = part.split("]", 1)[-1].strip() if "]" in part else part.strip()
            beats[f"beat_{idx}"] = content.split("[")[0].strip()
        if "[CTA]" in text:
            beats["cta"] = text.split("[CTA]")[-1].strip()
        return beats if beats else {"beat_1": text}
