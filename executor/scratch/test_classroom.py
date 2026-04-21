"""
Quick test for Google Classroom API integration.
Run from e:\jarvis:
    py executor/scratch/test_classroom.py
"""
import os
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv
load_dotenv()

from executor.app.auth.google import get_access_token, CLASSROOM_SCOPES
import httpx

print("=" * 50)
print("  JARVIS — Google Classroom API Test")
print("=" * 50)

print("\n[1] Getting access token (browser may open for first-time auth)...")
try:
    token = get_access_token(CLASSROOM_SCOPES)
    print(f"    ✅ Token OK: {token[:20]}...")
except Exception as e:
    print(f"    ❌ Auth failed: {e}")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}
api = "https://classroom.googleapis.com/v1"

print("\n[2] Fetching active courses...")
with httpx.Client(timeout=30.0) as client:
    r = client.get(f"{api}/courses", headers=headers, params={"courseStates": "ACTIVE"})
    print(f"    Status: {r.status_code}")

    if r.status_code != 200:
        print(f"    ❌ Error: {r.text}")
        sys.exit(1)

    courses = r.json().get("courses", [])
    if not courses:
        print("    ⚠️  No active courses found.")
        sys.exit(0)

    print(f"    ✅ Found {len(courses)} course(s):")
    for c in courses:
        print(f"       - [{c['id']}] {c.get('name', '?')}")

    print("\n[3] Fetching pending assignments for each course...")
    pending = []
    for course in courses:
        cid = course["id"]
        cname = course.get("name", cid)
        cw_r = client.get(
            f"{api}/courses/{cid}/courseWork",
            headers=headers,
            params={"courseWorkStates": "PUBLISHED", "orderBy": "dueDate asc"},
        )
        if cw_r.status_code != 200:
            print(f"       ⚠️  Could not fetch coursework for '{cname}': {cw_r.status_code}")
            continue

        coursework = cw_r.json().get("courseWork", [])
        print(f"\n    Course: {cname} ({len(coursework)} assignment(s))")

        for cw in coursework:
            cwid = cw["id"]
            sub_r = client.get(
                f"{api}/courses/{cid}/courseWork/{cwid}/studentSubmissions",
                headers=headers,
                params={"userId": "me"},
            )
            if sub_r.status_code != 200:
                continue
            for sub in sub_r.json().get("studentSubmissions", []):
                state = sub.get("state", "?")
                due = cw.get("dueDate")
                due_str = ""
                if due:
                    due_str = f"{due.get('year')}-{due.get('month'):02}-{due.get('day'):02}"
                status_icon = "✅" if state in ("TURNED_IN", "RETURNED") else "⏳"
                print(f"       {status_icon} [{state}] {cw.get('title', 'Untitled')} — Due: {due_str or 'N/A'}")
                if state not in ("TURNED_IN", "RETURNED"):
                    pending.append(cw.get("title", "Untitled"))

print(f"\n{'='*50}")
print(f"  Total pending: {len(pending)}")
for i, t in enumerate(pending, 1):
    print(f"  {i}. {t}")
print("=" * 50)
