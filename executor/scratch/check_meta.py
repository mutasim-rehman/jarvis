import httpx
import re

url = "https://www.worldmonitor.app"
with httpx.Client(follow_redirects=True) as client:
    resp = client.get(url, timeout=15.0)
    html = resp.text
    
    # Look for NEXT_DATA
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if match:
        print("FOUND NEXT_DATA")
        print(match.group(1)[:1000] + "...")
    else:
        print("NEXT_DATA NOT FOUND")
        # Look for any large JSON blocks
        json_blocks = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
        print(f"Found {len(json_blocks)} JSON blocks")
        for i, block in enumerate(json_blocks):
            print(f"Block {i}: {block[:200]}...")
