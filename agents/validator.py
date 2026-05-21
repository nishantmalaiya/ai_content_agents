"""
Agent 02 - Best Reel Finder
Scores competitor data and finds the best reel idea to make next.
"""
import re
from collections import defaultdict
from datetime import datetime, timedelta


class ContentValidator:
    WEIGHTS = {"views": 0.40, "engagement": 0.35, "comments": 0.25}

    TOPIC_PATTERNS = {
        "Claude Code tutorials":      [r"claude\s*code", r"claude\s*skills"],
        "AI automation income":        [r"income", r"money", r"earn", r"₹", r"\$", r"business"],
        "Agent setup walkthroughs":    [r"agent", r"setup", r"pipeline", r"workflow"],
        "AI vs traditional tools":     [r"replace", r"vs\b", r"kill", r"better\s*than", r"saas"],
        "Vibe coding & new paradigms": [r"vibe\s*coding", r"future", r"next\s*gen"],
        "AI content creation":         [r"content", r"creator", r"instagram", r"reel"],
        "N8N & workflow automation":   [r"n8n", r"zapier", r"automat"],
        "AI productivity hacks":       [r"hack", r"trick", r"tip", r"productiv", r"hours"],
    }

    def __init__(self, min_views=10000, min_engagement=2.0, max_age_days=30):
        self.min_views = min_views
        self.min_engagement = min_engagement
        self.max_age_days = max_age_days

    def validate(self, posts, topic=None, emit_progress=None):
        if emit_progress: emit_progress("Scoring posts…", 10)
        scored = self._score_posts(posts)
        if emit_progress: emit_progress("Filtering low performers…", 30)
        filtered = self._filter_posts(scored)
        if emit_progress: emit_progress("Clustering by topic…", 50)
        clusters = self._cluster_topics(filtered, topic)
        if emit_progress: emit_progress("Ranking…", 80)
        ranked = self._rank_topics(clusters)
        top_formats = self._top_formats(filtered)
        repeat = [{"topic": t, "occurrences": len(i)} for t, i in clusters.items() if len(i) >= 3]
        sustained = self._sustained_trends(filtered)

        rec = ""
        if ranked:
            t = ranked[0]
            rec = (f"Best reel to make: **{t['topic']}** - "
                   f"averaging {t['avg_views']:,} views and "
                   f"{t['avg_engagement']}% engagement ({t['count']} posts).")
        else:
            rec = "Not enough data. Run the scraper first."

        if emit_progress: emit_progress("✓ Validation complete", 100)

        cluster_summary = {}
        for cluster_name, items in clusters.items():
            cluster_summary[cluster_name] = {
                "count": len(items),
                "avg_views": round(sum(p["views"] for p in items) / max(len(items), 1)),
                "avg_engagement": round(sum(p["engagement_rate"] for p in items) / max(len(items), 1), 2),
                "top_post": max(items, key=lambda x: x["score"])["hook"] if items else "",
            }

        return {
            "recommendation": rec,
            "total_scored": len(scored),
            "posts_after_filter": len(filtered),
            "top_topics": ranked[:5],
            "top_formats": top_formats[:3],
            "repeat_viral_signals": repeat,
            "sustained_trends": sustained,
            "clusters": cluster_summary,
            "filtered_posts": filtered,
        }

    def _score_posts(self, posts):
        if not posts: return []
        max_v = max(p.get("views", 0) for p in posts) or 1
        max_c = max(p.get("comments", 0) for p in posts) or 1
        scored = []
        for p in posts:
            v, eng, c = p.get("views", 0), p.get("engagement_rate", 0), p.get("comments", 0)
            s = round((v/max_v)*10*0.4 + min(eng/5*10, 10)*0.35 + (c/max_c)*10*0.25, 2)
            entry = {**p, "score": s, "high_views": v >= 100000, "viral_engagement": eng >= 5.0}
            scored.append(entry)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _filter_posts(self, posts):
        cutoff = datetime.now().date() - timedelta(days=self.max_age_days)
        out = []
        for p in posts:
            if p.get("views", 0) < self.min_views: continue
            if p.get("engagement_rate", 0) < self.min_engagement: continue
            try:
                pd = datetime.strptime(str(p.get("post_date", "")), "%Y-%m-%d").date()
                if pd < cutoff: continue
            except ValueError: pass
            out.append(p)
        return out

    def _cluster_topics(self, posts, topic_focus=None):
        clusters = defaultdict(list)
        
        # If a specific topic is being searched, prioritize it
        topic_pattern = None
        if topic_focus:
            # Create a simple pattern from the topic words
            clean_topic = re.sub(r'[^a-zA-Z0-9\s]', '', topic_focus).strip()
            if clean_topic:
                topic_pattern = r'|'.join(re.escape(word) for word in clean_topic.split())

        for p in posts:
            text = f"{p.get('hook', '')} {p.get('caption', '')}".lower()
            matched = False
            
            # Check for specific topic focus first
            if topic_pattern and re.search(topic_pattern, text, re.IGNORECASE):
                clusters[topic_focus].append(p)
                matched = True
            
            # Then check hardcoded patterns
            if not matched:
                for topic, patterns in self.TOPIC_PATTERNS.items():
                    for pat in patterns:
                        if re.search(pat, text, re.IGNORECASE):
                            clusters[topic].append(p)
                            matched = True
                            break
                    if matched: break
            
            if not matched:
                clusters["Trending"].append(p)
        return dict(clusters)

    def _rank_topics(self, clusters):
        ranked = []
        for topic, items in clusters.items():
            if not items: continue
            ranked.append({
                "topic": topic, "count": len(items),
                "avg_views": round(sum(p["views"] for p in items) / len(items)),
                "avg_engagement": round(sum(p["engagement_rate"] for p in items) / len(items), 2),
                "avg_score": round(sum(p["score"] for p in items) / len(items), 2),
            })
        ranked.sort(key=lambda x: x["avg_views"], reverse=True)
        return ranked

    def _top_formats(self, posts):
        fmt = defaultdict(lambda: {"count": 0, "views": 0, "eng": 0, "shares": 0})
        for p in posts:
            f = p.get("format", "Unknown")
            fmt[f]["count"] += 1
            fmt[f]["views"] += p.get("views", 0)
            fmt[f]["eng"] += p.get("engagement_rate", 0)
            fmt[f]["shares"] += p.get("shares", 0)
        result = []
        for f, s in fmt.items():
            result.append({"format": f, "count": s["count"],
                           "avg_views": round(s["views"]/max(s["count"],1)),
                           "avg_engagement": round(s["eng"]/max(s["count"],1), 2),
                           "avg_shares": round(s["shares"]/max(s["count"],1))})
        result.sort(key=lambda x: (x["avg_shares"], x["avg_views"]), reverse=True)
        return result

    def _sustained_trends(self, posts):
        """Flag formats that appear in top 10 this week and previous week."""
        current_week, previous_week = [], []
        now = datetime.now().date()
        for p in posts:
            try:
                pd = datetime.strptime(str(p.get("post_date", ""))[:10], "%Y-%m-%d").date()
            except ValueError:
                current_week.append(p)
                continue
            age = (now - pd).days
            if age <= 7:
                current_week.append(p)
            elif age <= 14:
                previous_week.append(p)

        current_formats = {p.get("format", "Unknown") for p in sorted(current_week, key=lambda x: x.get("views", 0), reverse=True)[:10]}
        previous_formats = {p.get("format", "Unknown") for p in sorted(previous_week, key=lambda x: x.get("views", 0), reverse=True)[:10]}
        return [{"format": f, "signal": "top 10 last week and this week"} for f in sorted(current_formats & previous_formats)]
