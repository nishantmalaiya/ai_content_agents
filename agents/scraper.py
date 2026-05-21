"""
Agent 01 -- Competitor Reel Scraper
Scrapes competitor Instagram Reels, YouTube Shorts, and Twitter/X posts.

Priority: Apify API first when a token is configured, then free scrapers.
Returns no rows if live scraping fails.
"""

import os
import json
import time
import traceback
from datetime import datetime, timezone, timedelta

# ---------- Optional free scraper imports ----------
try:
    import instaloader
except ImportError:
    instaloader = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import snscrape.modules.twitter as sntwitter
except ImportError:
    sntwitter = None

try:
    import requests as _requests
except ImportError:
    _requests = None


class ContentScraper:
    """Pulls competitor reel/post data from Instagram, YouTube & Twitter."""

    DEFAULT_KEYWORDS = [
        "Claude Code", "AI agents", "N8N automation",
        "AI coding", "vibe coding", "Claude skills",
        "OpenClaw", "AI automation",
    ]

    # Apify Actor IDs used as the preferred scraper when APIFY_TOKEN is configured.
    APIFY_ACTORS = {
        "instagram": "shu8hvrXbJbY3Eb9W",
        "youtube":   "h7sDV53CddomktSi5",
        "twitter":   "61RPP7dywgiy0JPD0",
    }

    def __init__(self, apify_token=None, keywords=None,
                 competitors=None, days_back=7, ig_user=None, ig_pass=None):
        self.token = apify_token or os.getenv("APIFY_TOKEN")
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        self.competitors = competitors or []
        self.days_back = days_back
        self.ig_user = ig_user or os.getenv("IG_USERNAME")
        self.ig_pass = ig_pass or os.getenv("IG_PASSWORD") or os.getenv("IG_SESSIONID")
        self.results = []

    # ================================================================== #
    #  Public API                                                         #
    # ================================================================== #
    def run(self, platforms=None, emit_progress=None):
        """Run the scraper across selected platforms."""
        platforms = platforms or ["instagram", "youtube", "twitter"]
        self.results = []

        for idx, platform in enumerate(platforms):
            pct = int((idx / len(platforms)) * 100)
            if emit_progress:
                emit_progress(f"Scraping {platform}...", pct)
            try:
                posts = self._scrape_platform(platform, emit_progress)
                self.results.extend(posts)
            except Exception as e:
                tb = traceback.format_exc()
                if emit_progress:
                    emit_progress(f"{platform} error: {str(e)[:80]}", -1)

        # Sort by views descending
        self.results.sort(key=lambda x: x.get("views", 0), reverse=True)

        # Flag viral posts
        for post in self.results:
            reasons = []
            if post.get("views", 0) >= 100_000:
                reasons.append("100K+ views")
            if post.get("engagement_rate", 0) >= 5.0:
                reasons.append("5%+ engagement")
            post["viral"] = bool(reasons)
            post["viral_reasons"] = reasons

        if emit_progress:
            emit_progress(f"Scraped {len(self.results)} posts total", 100)

        return self.results

    def get_results_json(self):
        return json.dumps(self.results, indent=2, default=str)

    # ================================================================== #
    #  Dispatcher                                                         #
    # ================================================================== #
    def _scrape_platform(self, platform, emit_progress=None):
        """Try Apify first, then free scrapers. Never generate fake rows."""
        if self.token and _requests:
            try:
                actor_id = self.APIFY_ACTORS.get(platform)
                if actor_id:
                    if emit_progress:
                        emit_progress(f"{platform}: using Apify API...", -1)
                    apify_results = self._apify_scrape(platform, actor_id)
                    if apify_results:
                        return apify_results
                    if emit_progress:
                        emit_progress(f"{platform}: Apify returned no rows", -1)
            except Exception as e:
                if emit_progress:
                    emit_progress(f"{platform} Apify failed: {str(e)[:90]}", -1)

        # --- FREE scrapers ---
        free_results = []
        try:
            if platform == "youtube" and yt_dlp:
                if emit_progress:
                    emit_progress("YouTube: using free yt-dlp search...", -1)
                free_results = self._free_youtube(emit_progress)

            elif platform == "instagram" and instaloader:
                if emit_progress:
                    emit_progress("Instagram: using free instaloader...", -1)
                free_results = self._free_instagram(emit_progress)

            elif platform == "twitter" and sntwitter:
                if emit_progress:
                    emit_progress("Twitter: using free snscrape...", -1)
                free_results = self._free_twitter()
        except Exception as e:
            if emit_progress:
                emit_progress(f"{platform} free scraper error: {str(e)[:50]}", -1)

        if free_results:
            if emit_progress:
                emit_progress(f"{platform}: got {len(free_results)} posts (free)", -1)
            return free_results

        if emit_progress:
            emit_progress(f"{platform}: no live data returned", -1)
        return []

    # ================================================================== #
    #  FREE: YouTube via yt-dlp                                           #
    # ================================================================== #
    def _free_youtube(self, emit_progress=None):
        posts = []
        seen_ids = set()
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreerrors": True,
            "no_check_certificates": True,
            "extract_flat": True,
            "proxy": "",
        }

        # Search with multiple queries for better coverage
        queries = []
        for kw in self.keywords[:5]:
            queries.append(f"ytsearch25:{kw}")

        for query in queries:
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(query, download=False)
                for entry in (result.get("entries") or []):
                    if not entry:
                        continue
                    vid_id = entry.get("id", "")
                    if vid_id in seen_ids:
                        continue
                    seen_ids.add(vid_id)

                    title = entry.get("title", "") or ""
                    views = entry.get("view_count", 0) or 0
                    duration = entry.get("duration", 0) or 0
                    channel = entry.get("channel", "") or entry.get("uploader", "") or ""
                    url = entry.get("url", "") or f"https://www.youtube.com/watch?v={vid_id}"

                    # Accept videos up to 1 hour
                    if duration and duration > 3600:
                        continue
                    fmt = "Short" if (duration and duration <= 90) else "Video"

                    likes = entry.get("like_count", 0) or 0
                    comments = entry.get("comment_count", 0) or 0
                    eng = round((likes + comments) / max(views, 1) * 100, 2)

                    upload_date = entry.get("upload_date", "")
                    if upload_date and len(upload_date) == 8:
                        post_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                    else:
                        post_date = str(datetime.now(timezone.utc).date())

                    posts.append({
                        "platform": "YouTube",
                        "format": fmt,
                        "hook": title[:120],
                        "caption": f"{title} | {channel}",
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "shares": 0,
                        "engagement_rate": eng,
                        "post_date": post_date,
                        "url": url,
                        "channel": channel,
                        "transcript": "",
                        "transcript_source": "not_available",
                        "source": "yt-dlp (free)",
                    })
                    if len(posts) >= 60: return posts
            except Exception as e:
                if emit_progress:
                    emit_progress(f"YouTube yt-dlp failed for {query}: {str(e)[:90]}", -1)
                continue
        return posts

    # ================================================================== #
    #  FREE: Instagram via instaloader                                    #
    # ================================================================== #
    def _free_instagram(self, emit_progress=None):
        posts = []
        L = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            quiet=True,
            max_connection_attempts=1,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.days_back)

        self._instagram_login(L, emit_progress)

        # Try competitors
        for handle in self.competitors[:2]:
            handle = handle.lstrip("@").strip()
            if handle.lower().startswith("competitor"):
                if emit_progress:
                    emit_progress(f"Instagram: skipping placeholder handle @{handle}", -1)
                continue
            if not handle: continue
            try:
                profile = instaloader.Profile.from_username(L.context, handle)
                if emit_progress:
                    emit_progress(f"Instagram: reading @{handle}", -1)
                for post_obj in profile.get_posts():
                    if post_obj.date_utc < cutoff: break
                    if not post_obj.is_video: continue

                    views = post_obj.video_view_count or 0
                    likes = post_obj.likes or 0
                    comments = post_obj.comments or 0
                    eng = round((likes + comments) / max(views, 1) * 100, 2)
                    caption = post_obj.caption or ""

                    posts.append({
                        "platform": "Instagram",
                        "format": "Reel",
                        "hook": caption.split("\n")[0][:120],
                        "caption": caption[:500],
                        "views": views,
                        "likes": likes,
                        "comments": comments,
                        "shares": 0,
                        "engagement_rate": eng,
                        "post_date": str(post_obj.date_utc.date()),
                        "url": f"https://www.instagram.com/p/{post_obj.shortcode}/",
                        "owner": handle,
                        "transcript": "",
                        "transcript_source": "not_available",
                        "source": "instaloader (free)",
                    })
                    if len(posts) >= 20: break
            except Exception as e:
                if emit_progress:
                    emit_progress(f"Instagram @{handle} failed: {str(e)[:90]}", -1)
                continue

        # Try hashtags if still empty
        if not posts:
            for kw in self.keywords[:2]:
                tag = kw.replace(" ", "").lower()
                try:
                    if emit_progress:
                        emit_progress(f"Instagram: reading #{tag}", -1)
                    hashtag = instaloader.Hashtag.from_name(L.context, tag)
                    count = 0
                    for post_obj in hashtag.get_top_posts():
                        if count >= 10: break
                        if not post_obj.is_video: continue

                        views = post_obj.video_view_count or 0
                        likes = post_obj.likes or 0
                        comments = post_obj.comments or 0
                        posts.append({
                            "platform": "Instagram", "format": "Reel",
                            "hook": (post_obj.caption or "")[:120],
                            "caption": post_obj.caption or "",
                            "views": views, "likes": likes, "comments": comments,
                            "shares": 0,
                            "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                            "post_date": str(post_obj.date_utc.date()),
                            "url": f"https://www.instagram.com/p/{post_obj.shortcode}/",
                            "transcript": "",
                            "transcript_source": "not_available",
                            "source": "instaloader (free)",
                        })
                        count += 1
                except Exception as e:
                    if emit_progress:
                        emit_progress(f"Instagram #{tag} failed: {str(e)[:90]}", -1)
                    continue
        return posts

    def _instagram_login(self, loader, emit_progress=None):
        """Best-effort Instagram auth for Instaloader.

        Instagram blocks anonymous scraping aggressively. A saved session is the
        most reliable Instaloader path, followed by username/password login.
        """
        if not self.ig_user and not self.ig_pass:
            if emit_progress:
                emit_progress("Instagram: no login/session configured; anonymous access may be blocked", -1)
            return

        session_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        session_file = os.path.abspath(os.path.join(session_dir, f"instaloader-session-{self.ig_user or 'session'}"))

        if self.ig_user and os.path.exists(session_file):
            try:
                loader.load_session_from_file(self.ig_user, session_file)
                user = loader.test_login()
                if emit_progress:
                    emit_progress(f"Instagram: loaded saved session for @{user or self.ig_user}", -1)
                return
            except Exception as e:
                if emit_progress:
                    emit_progress(f"Instagram saved session failed: {str(e)[:90]}", -1)

        if self.ig_user and self.ig_pass and len(self.ig_pass) <= 30:
            try:
                loader.login(self.ig_user, self.ig_pass)
                os.makedirs(session_dir, exist_ok=True)
                loader.save_session_to_file(session_file)
                if emit_progress:
                    emit_progress(f"Instagram: logged in as @{self.ig_user}", -1)
                return
            except Exception as e:
                if emit_progress:
                    emit_progress(f"Instagram login failed: {str(e)[:90]}", -1)
                return

        if self.ig_pass and len(self.ig_pass) > 30:
            loader.context._session.cookies.set("sessionid", self.ig_pass, domain=".instagram.com")
            if emit_progress:
                emit_progress("Instagram: using provided sessionid cookie", -1)

    # ================================================================== #
    #  FREE: Twitter via snscrape                                         #
    # ================================================================== #
    def _free_twitter(self):
        import ssl, os
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        try: ssl._create_default_https_context = ssl._create_unverified_context
        except Exception: pass

        posts = []
        since = (datetime.now() - timedelta(days=self.days_back)).strftime("%Y-%m-%d")

        for kw in self.keywords[:2]:
            try:
                query = f'"{kw}" since:{since} min_faves:20'
                scraper = sntwitter.TwitterSearchScraper(query)
                count = 0
                for tweet in scraper.get_items():
                    if count >= 15: break
                    views = getattr(tweet, "viewCount", 0) or 0
                    likes = getattr(tweet, "likeCount", 0) or 0
                    text = tweet.rawContent if hasattr(tweet, "rawContent") else str(tweet)
                    posts.append({
                        "platform": "Twitter/X", "format": "Tweet",
                        "hook": text[:120], "caption": text[:500],
                        "views": views, "likes": likes, "comments": getattr(tweet, "replyCount", 0),
                        "shares": getattr(tweet, "retweetCount", 0) or 0,
                        "engagement_rate": round((likes + 5) / max(views, 1) * 100, 2),
                        "post_date": str(tweet.date.date()) if hasattr(tweet, "date") else "",
                        "url": tweet.url if hasattr(tweet, "url") else "",
                        "transcript": "",
                        "transcript_source": "not_applicable",
                        "source": "snscrape (free)",
                    })
                    count += 1
            except Exception:
                continue
        return posts

    # ================================================================== #
    #  Apify fallback (requires token)                                    #
    # ================================================================== #
    def _apify_scrape(self, platform, actor_id):
        """Run an Apify actor and normalize results."""
        payload = self._apify_payload(platform)
        url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={self.token}"
        resp = _requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        run_data = resp.json()["data"]
        run_id = run_data["id"]
        dataset_id = run_data["defaultDatasetId"]

        for _ in range(24):
            sr = _requests.get(
                f"https://api.apify.com/v2/actor-runs/{run_id}?token={self.token}",
                timeout=15,
            )
            status = sr.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            if status in ("FAILED", "ABORTED"):
                raise RuntimeError(f"Apify {status}")
            time.sleep(5)

        items = _requests.get(
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={self.token}&limit=50&format=json",
            timeout=30,
        ).json()

        if platform == "youtube":
            return self._norm_yt(items)
        if platform == "instagram":
            return self._norm_ig(items)
        return self._norm_tw(items)

    def _apify_payload(self, platform):
        if platform == "instagram":
            return {
                "search": f"#{self.keywords[0].replace(' ','').lower()}",
                "searchType": "hashtag",
                "resultsType": "posts",
                "searchLimit": 1,
                "resultsLimit": 20,
                "mediaType": "VIDEO"
            }
        if platform == "youtube":
            return {"searchKeywords": self.keywords[:5], "maxResults": 50,
                    "uploadDate": "week", "type": "video", "videoDuration": "short"}
        return {"searchTerms": [f'"{kw}"' for kw in self.keywords[:5]],
                "maxTweets": 50, "tweetLanguage": "en"}

    def _norm_ig(self, items):
        posts = []
        for item in items:
            caption = item.get("caption") or item.get("text") or ""
            likes = item.get("likesCount") or item.get("likes_count") or 0
            views = item.get("videoViewCount") or item.get("video_view_count") or item.get("viewsCount") or 0
            comments = item.get("commentsCount") or item.get("comments_count") or 0
            shares = item.get("sharesCount") or item.get("shareCount") or 0
            posts.append({
                "platform": "Instagram", "format": "Reel",
                "hook": caption.split("\n")[0][:120], "caption": caption,
                "views": views, "likes": likes, "comments": comments, "shares": shares,
                "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                "post_date": str(item.get("timestamp", ""))[:10],
                "url": item.get("url") or f"https://www.instagram.com/p/{item.get('shortCode', '')}/",
                "transcript": item.get("transcript") or item.get("videoTranscript") or "",
                "transcript_source": "apify" if (item.get("transcript") or item.get("videoTranscript")) else "not_available",
                "source": "Apify (Pro)",
            })
        return posts

    def _norm_yt(self, raw):
        out = []
        for item in raw:
            views = item.get("viewCount", 0) or 0
            likes = item.get("likes", 0) or item.get("likeCount", 0) or 0
            comments = item.get("commentsCount", 0) or 0
            shares = item.get("shareCount", 0) or item.get("shares", 0) or 0
            out.append({"platform": "YouTube", "format": "Short",
                        "hook": (item.get("title", ""))[:120],
                        "caption": item.get("description", "")[:500],
                        "views": views, "likes": likes, "comments": comments, "shares": shares,
                        "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                        "post_date": str(item.get("date", "")),
                        "url": item.get("url", ""),
                        "transcript": item.get("transcript") or item.get("subtitles") or "",
                        "transcript_source": "apify" if (item.get("transcript") or item.get("subtitles")) else "not_available",
                        "source": "Apify (Pro)"})
        return out

    def _norm_tw(self, raw):
        out = []
        for item in raw:
            text = item.get("text", "") or item.get("full_text", "")
            views = item.get("viewCount", 0) or 0
            likes = item.get("likeCount", 0) or item.get("favoriteCount", 0)
            comments = item.get("replyCount", 0) or 0
            shares = item.get("retweetCount", 0) or item.get("quoteCount", 0) or 0
            out.append({"platform": "Twitter/X", "format": "Tweet",
                        "hook": text[:120], "caption": text[:500],
                        "views": views, "likes": likes, "comments": comments, "shares": shares,
                        "engagement_rate": round((likes + comments) / max(views, 1) * 100, 2),
                        "post_date": str(item.get("createdAt", "")),
                        "url": item.get("url", ""),
                        "transcript": "",
                        "transcript_source": "not_applicable",
                        "source": "Apify (Pro)"})
        return out

    def _parse_view_count(self, text):
        text = text.lower().replace(",", "").replace("views", "").strip()
        try:
            if "m" in text: return int(float(text.replace("m", "")) * 1_000_000)
            if "k" in text: return int(float(text.replace("k", "")) * 1_000)
            return int(float(text)) if text else 0
        except: return 0

    def _duration_seconds(self, dur_str):
        try:
            parts = str(dur_str).split(":")
            if len(parts) == 2: return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3: return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            return 0
        except: return 0

    def _relative_date(self, text):
        text, now = str(text).lower().strip(), datetime.now(timezone.utc)
        try:
            if "day" in text: return str((now - timedelta(days=int("".join(c for c in text if c.isdigit()) or "1"))).date())
            if "week" in text: return str((now - timedelta(weeks=int("".join(c for c in text if c.isdigit()) or "1"))).date())
        except: pass
        return str(now.date())
