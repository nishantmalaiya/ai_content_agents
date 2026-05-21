import yt_dlp
import json

def test_yt():
    ydl_opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'ignoreerrors': True}
    kw = 'AI agents automation'
    query = f'ytsearch20:{kw}'
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(query, download=False)
            entries = result.get('entries', [])
            valid = [e for e in entries if e and e.get('title')]
            print(f'Total found: {len(valid)}')
            for e in valid[:10]:
                print(f" - {e.get('title')} ({e.get('duration')}s) | views: {e.get('view_count')}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_yt()
