import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent))

from agents.scraper import ContentScraper

def test_scraper():
    keywords = ["AI agents", "n8n automation"]
    scraper = ContentScraper(keywords=keywords)
    
    print("Testing YouTube scraper...")
    yt_results = scraper._free_youtube()
    print(f"YouTube results: {len(yt_results)}")
    for res in yt_results[:3]:
        print(f" - {res['hook']} (Source: {res['source']})")
        
    print("\nTesting Instagram Search Index Fallback...")
    ig_results = scraper._search_index_scrape("instagram")
    print(f"Instagram results: {len(ig_results)}")
    for res in ig_results[:3]:
        print(f" - {res['hook']} (Source: {res['source']})")

if __name__ == "__main__":
    test_scraper()
