"""
AI Content Agent System — Flask Application
4-agent pipeline: Scraper → Validator → Writer → Hook Generator
"""
import os, json, threading
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

load_dotenv()

from agents.scraper import ContentScraper
from agents.validator import ContentValidator
from agents.writer import ScriptWriter
from agents.hooks import HookGenerator

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Data directory for persisting results
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Global state for pipeline results
pipeline_state = {
    "scraper_results": [],
    "platform_results": {"youtube": [], "instagram": [], "twitter": []},
    "validator_results": {},
    "script_result": {},
    "hook_result": {},
    "last_run": None,
    "running": False,
    "last_topic": "",
}

# Note: We still save results to files for agent communication, 
# but we no longer load them into the UI automatically on startup.
def clear_old_results():
    for filename in [
        "scraper_results.json", "youtube_results.json", "instagram_results.json",
        "twitter_results.json", "validator_results.json", "script_result.json",
        "hook_result.json",
    ]:
        path = DATA_DIR / filename
        if path.exists():
            try:
                path.unlink()
            except:
                pass

# Wipe files on every start as requested
clear_old_results()


def _emit(event, data):
    socketio.emit(event, data)


def _split_env_list(name, default=""):
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


def _competitor_handles():
    return [h for h in _split_env_list("COMPETITOR_HANDLES") if not h.lstrip("@").lower().startswith("competitor")]


# ------------------------------------------------------------------ #
#  Routes                                                              #
# ------------------------------------------------------------------ #
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    return jsonify({
        "last_run": pipeline_state["last_run"],
        "running": pipeline_state["running"],
        "has_scraper_data": bool(pipeline_state["scraper_results"]),
        "has_validator_data": bool(pipeline_state["validator_results"]),
        "has_script": bool(pipeline_state["script_result"]),
        "has_hooks": bool(pipeline_state["hook_result"]),
    })


@app.route("/api/results")
def get_results():
    return jsonify(pipeline_state)


@app.route("/api/config", methods=["GET", "POST"])
def config():
    config_file = DATA_DIR / "config.json"
    if request.method == "POST":
        cfg = request.get_json() or {}
        config_file.write_text(json.dumps(cfg, indent=2))
        return jsonify({"ok": True})
    if config_file.exists():
        return jsonify(json.loads(config_file.read_text()))
    return jsonify({
        "keywords": _split_env_list("SCRAPE_KEYWORDS", "Claude Code,AI agents,N8N automation"),
        "competitors": _competitor_handles(),
        "days_back": 7,
        "min_views": 10000,
        "min_engagement": 2.0,
        "platforms": ["instagram", "youtube", "twitter"],
    })


@app.route("/api/voice", methods=["GET", "POST"])
def voice():
    vf = DATA_DIR / "voice_profile.json"
    if request.method == "POST":
        data = request.get_json() or {}
        if "scripts" in data:
            try:
                writer = ScriptWriter(openai_key=data.get("openai_key"), data_dir=str(DATA_DIR))
                profile = writer.analyze_scripts(data["scripts"])
                return jsonify(profile)
            except Exception as e:
                return jsonify({"error": str(e)}), 400
        vf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return jsonify({"ok": True})
    if vf.exists():
        return jsonify(json.loads(vf.read_text(encoding="utf-8")))
    return jsonify({})


# ------------------------------------------------------------------ #
#  WebSocket events — Pipeline execution                               #
# ------------------------------------------------------------------ #
@socketio.on("run_scraper")
def handle_run_scraper(data):
    if pipeline_state["running"]:
        emit("agent_error", {"msg": "Pipeline already running"})
        return
    threading.Thread(target=_run_scraper, args=(data,), daemon=True).start()


@socketio.on("run_validator")
def handle_run_validator(data):
    if pipeline_state["running"]:
        emit("agent_error", {"msg": "Pipeline already running"})
        return
    threading.Thread(target=_run_validator, daemon=True).start()


@socketio.on("run_writer")
def handle_run_writer(data):
    if pipeline_state["running"]:
        emit("agent_error", {"msg": "Pipeline already running"})
        return
    threading.Thread(target=_run_writer, args=(data,), daemon=True).start()


@socketio.on("run_hooks")
def handle_run_hooks(data):
    if pipeline_state["running"]:
        emit("agent_error", {"msg": "Pipeline already running"})
        return
    threading.Thread(target=_run_hooks, args=(data,), daemon=True).start()


@socketio.on("run_full_pipeline")
def handle_full_pipeline(data):
    if pipeline_state["running"]:
        emit("agent_error", {"msg": "Pipeline already running"})
        return
    threading.Thread(target=_run_full_pipeline, args=(data,), daemon=True).start()


# ------------------------------------------------------------------ #
#  Pipeline runners                                                    #
# ------------------------------------------------------------------ #
def _progress(agent_name):
    def _fn(msg, pct):
        _emit("agent_progress", {"agent": agent_name, "message": msg, "percent": pct})
    return _fn


def _run_scraper(data):
    pipeline_state["running"] = True
    _emit("agent_start", {"agent": "scraper"})
    try:
        cfg = data or {}
        # Ensure topic is always a primary keyword if provided
        keywords = cfg.get("keywords") or []
        topic = cfg.get("topic", "").strip()
        pipeline_state["last_topic"] = topic
        if topic and topic not in keywords:
            keywords = [topic] + keywords

        scraper = ContentScraper(
            apify_token=cfg.get("apify_token"),
            keywords=keywords,
            competitors=cfg.get("competitors"),
            days_back=cfg.get("days_back", 7),
            ig_user=cfg.get("ig_user"),
            ig_pass=cfg.get("ig_pass"),
        )
        results = scraper.run(
            platforms=cfg.get("platforms", ["instagram", "youtube", "twitter"]),
            emit_progress=_progress("scraper"),
        )
        pipeline_state["scraper_results"] = results
        pipeline_state["platform_results"] = _split_platform_results(results)
        _save("scraper_results.json", results)
        _save_platform_results(results)
        _emit("agent_done", {"agent": "scraper", "count": len(results)})
    except Exception as e:
        _emit("agent_error", {"agent": "scraper", "msg": str(e)})
    finally:
        pipeline_state["running"] = False


def _run_validator():
    pipeline_state["running"] = True
    pipeline_state["validator_results"] = {}
    _emit("agent_start", {"agent": "validator"})
    try:
        posts = pipeline_state.get("scraper_results", [])
        if not posts:
            raise RuntimeError("Validator needs live scraper results. Run scraper first.")
        validator = ContentValidator()
        result = validator.validate(posts, topic=pipeline_state.get("last_topic"), emit_progress=_progress("validator"))
        pipeline_state["validator_results"] = result
        _save("validator_results.json", result)
        _emit("agent_done", {"agent": "validator", "data": {
            "recommendation": result["recommendation"],
            "total_scored": result["total_scored"],
            "posts_after_filter": result["posts_after_filter"],
            "top_topics": result["top_topics"],
            "top_formats": result["top_formats"],
            "repeat_viral_signals": result["repeat_viral_signals"],
            "sustained_trends": result["sustained_trends"],
            "clusters": result["clusters"],
        }})
    except Exception as e:
        _emit("agent_error", {"agent": "validator", "msg": str(e)})
    finally:
        pipeline_state["running"] = False


def _run_writer(data):
    pipeline_state["running"] = True
    pipeline_state["script_result"] = {}
    _emit("agent_start", {"agent": "writer"})
    try:
        data = data or {}
        topic = data.get("topic", "AI automation with Claude Code")
        ctx = {}
        if pipeline_state.get("validator_results", {}).get("top_topics"):
            t = pipeline_state["validator_results"]["top_topics"][0]
            ctx = _generation_context(pipeline_state["validator_results"])
        writer = ScriptWriter(openai_key=data.get("openai_key"), data_dir=str(DATA_DIR))
        result = writer.write_script(topic, context=ctx, emit_progress=_progress("writer"))
        pipeline_state["script_result"] = result
        _save("script_result.json", result)
        _emit("agent_done", {"agent": "writer", "data": result})
    except Exception as e:
        _emit("agent_error", {"agent": "writer", "msg": str(e)})
    finally:
        pipeline_state["running"] = False


def _run_hooks(data):
    pipeline_state["running"] = True
    pipeline_state["hook_result"] = {}
    _emit("agent_start", {"agent": "hooks"})
    try:
        data = data or {}
        topic = data.get("topic", "AI automation")
        ctx = {}
        if pipeline_state.get("validator_results"):
            ctx = _generation_context(pipeline_state["validator_results"])
        gen = HookGenerator(openai_key=data.get("openai_key"))
        result = gen.generate(topic, context=ctx, emit_progress=_progress("hooks"))
        pipeline_state["hook_result"] = result
        _save("hook_result.json", result)
        _emit("agent_done", {"agent": "hooks", "data": result})
    except Exception as e:
        _emit("agent_error", {"agent": "hooks", "msg": str(e)})
    finally:
        pipeline_state["running"] = False


def _run_full_pipeline(data):
    pipeline_state["running"] = True
    pipeline_state["validator_results"] = {}
    pipeline_state["script_result"] = {}
    pipeline_state["hook_result"] = {}
    _emit("pipeline_start", {})
    try:
        data = data or {}
        topic = data.get("topic", "").strip()
        pipeline_state["last_topic"] = topic
        
        # Agent 01 — Scraper
        _emit("agent_start", {"agent": "scraper"})
        
        # Ensure topic is always a primary keyword if provided
        keywords = data.get("keywords") or []
        topic = data.get("topic", "").strip()
        if topic and topic not in keywords:
            # Prepend topic so it gets priority
            keywords = [topic] + keywords
            
        scraper = ContentScraper(
            apify_token=data.get("apify_token"),
            keywords=keywords,
            competitors=data.get("competitors"),
            days_back=data.get("days_back", 7),
            ig_user=data.get("ig_user"),
            ig_pass=data.get("ig_pass"),
        )
        results = scraper.run(
            platforms=data.get("platforms", ["instagram", "youtube", "twitter"]),
            emit_progress=_progress("scraper"),
        )
        if not results:
            raise RuntimeError("Scraper returned no live posts. Pipeline stopped before validator/writer/hooks.")
        pipeline_state["scraper_results"] = results
        pipeline_state["platform_results"] = _split_platform_results(results)
        _save("scraper_results.json", results)
        _save_platform_results(results)
        _emit("agent_done", {"agent": "scraper", "count": len(results)})

        # Agent 02 — Validator
        _emit("agent_start", {"agent": "validator"})
        validator = ContentValidator()
        val_result = validator.validate(results, topic=topic, emit_progress=_progress("validator"))
        pipeline_state["validator_results"] = val_result
        _save("validator_results.json", val_result)
        _emit("agent_done", {"agent": "validator", "data": {
            "recommendation": val_result["recommendation"],
            "top_topics": val_result["top_topics"],
            "top_formats": val_result["top_formats"],
            "repeat_viral_signals": val_result["repeat_viral_signals"],
            "sustained_trends": val_result["sustained_trends"],
            "clusters": val_result["clusters"],
        }})

        # Determine topic
        topic = data.get("topic", "")
        if not topic and val_result.get("top_topics"):
            topic = val_result["top_topics"][0]["topic"]

        # Agent 03 — Writer
        _emit("agent_start", {"agent": "writer"})
        ctx = {}
        if val_result.get("top_topics"):
            ctx = _generation_context(val_result)
        writer = ScriptWriter(openai_key=data.get("openai_key"), data_dir=str(DATA_DIR))
        script = writer.write_script(topic, context=ctx, emit_progress=_progress("writer"))
        pipeline_state["script_result"] = script
        _save("script_result.json", script)
        _emit("agent_done", {"agent": "writer", "data": script})

        # Agent 04 — Hook Generator
        _emit("agent_start", {"agent": "hooks"})
        gen = HookGenerator(openai_key=data.get("openai_key"))
        hooks = gen.generate(topic, context=ctx, emit_progress=_progress("hooks"))
        pipeline_state["hook_result"] = hooks
        _save("hook_result.json", hooks)
        _emit("agent_done", {"agent": "hooks", "data": hooks})

        pipeline_state["last_run"] = datetime.now().isoformat()
        _emit("pipeline_done", {
            "recommendation": val_result.get("recommendation", ""),
            "topic": topic,
        })
    except Exception as e:
        _emit("pipeline_error", {"msg": str(e)})
    finally:
        pipeline_state["running"] = False


def _save(filename, data):
    (DATA_DIR / filename).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _generation_context(validator_result):
    top_topic = (validator_result.get("top_topics") or [{}])[0]
    filtered = sorted(
        validator_result.get("filtered_posts", []),
        key=lambda item: item.get("views", 0),
        reverse=True,
    )
    top_posts = [
        {
            "hook": p.get("hook", ""),
            "views": p.get("views", 0),
            "platform": p.get("platform", ""),
            "format": p.get("format", ""),
            "url": p.get("url", ""),
        }
        for p in filtered[:10]
    ]
    return {
        "avg_views": top_topic.get("avg_views", 0),
        "top_topics": validator_result.get("top_topics", []),
        "top_formats": validator_result.get("top_formats", []),
        "recommendation": validator_result.get("recommendation", ""),
        "repeat_viral_signals": validator_result.get("repeat_viral_signals", []),
        "sustained_trends": validator_result.get("sustained_trends", []),
        "top_posts": top_posts,
    }


def _split_platform_results(results):
    platform_results = {"youtube": [], "instagram": [], "twitter": []}
    for item in results:
        platform = str(item.get("platform", "")).lower()
        if "youtube" in platform:
            platform_results["youtube"].append(item)
        elif "instagram" in platform:
            platform_results["instagram"].append(item)
        elif "twitter" in platform or platform == "x":
            platform_results["twitter"].append(item)
    return platform_results


def _save_platform_results(results):
    for platform, items in _split_platform_results(results).items():
        _save(f"{platform}_results.json", items)


# ------------------------------------------------------------------ #
if __name__ == "__main__":
    print("\n>>> AI Content Agent System running at http://localhost:5050\n")
    socketio.run(app, host="0.0.0.0", port=5050, debug=True,
                 allow_unsafe_werkzeug=True, use_reloader=False)
