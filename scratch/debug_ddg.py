import requests
from bs4 import BeautifulSoup

def debug_ddg():
    query = "site:instagram.com AI agents"
    url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {resp.status_code}")
    # print(resp.text[:1000])
    soup = BeautifulSoup(resp.text, 'html.parser')
    results = soup.find_all('a', class_='result__a')
    print(f"Found {len(results)} results")
    for r in results[:5]:
        print(f" - {r.text} | {r.get('href')}")

if __name__ == "__main__":
    debug_ddg()
