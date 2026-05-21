
import requests
import re

def test():
    query = "site:instagram.com/p/ Mother's Day reels"
    url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    print(f"Searching: {url}")
    r = requests.get(url, headers=headers)
    print(f"Status: {r.status_code}")
    
    links = re.findall(r'href="(https://(?:www\.)?instagram\.com/p/[^"]+)"', r.text)
    # Bing often uses <h2><a ...>Title</a></h2>
    titles = re.findall(r'<h2[^>]*><a[^>]*>([^<]+)</a>', r.text)
    
    print(f"Found {len(links)} links")
    print(f"Found {len(titles)} titles")
    
    for i in range(min(len(links), 5)):
        print(f"[{i}] {titles[i] if i < len(titles) else 'N/A'} -> {links[i]}")

if __name__ == "__main__":
    test()
