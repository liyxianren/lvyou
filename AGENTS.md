# Project Agent Rules

This is a real travel execution website, not a static travel article. Every itinerary edit must make the trip easier to execute on the road.

## Canonical Data

- `data/trip.json` is the canonical source for the website and API.
- `content/dayX.md` is visible supplemental content for each day page.
- `plans/dayX.md` is the maintenance and planning note for future edits.
- `bookings`, `budget`, `supplies`, and route map links in `data/trip.json` are user-visible operational records.
- If one of these surfaces changes, update all related surfaces in the same turn. Do not leave stale restaurant, hotel, route, or time-window text behind.

## Travel Content Standard

- Write actionable travel plans, not generic descriptions.
- A day plan must include route, timing, stops, why each stop matters, skip conditions, backup choices, food, lodging, budget, and risk notes when relevant.
- Prefer one complete Baidu Maps route at the top of each day. Use start + up to 5 waypoints + destination; avoid isolated map dots when the user needs a full-day navigation plan.
- When a restaurant is selected, record the exact restaurant name, Baidu distance/time from the relevant lodging or route node, recommended dishes, budget, and fallback.
- When a scenic stop is selected, record the exact navigation name, realistic stay duration, photo/play purpose, crowd/parking/weather caveats, and skip rule.
- Do not invent POIs, distances, opening details, or social-media consensus. Mark uncertainty clearly.

## Research Workflow

- Use Xiaohongshu for qualitative travel strategy: what people actually do, what is worth skipping, what time of day works, what food is praised or criticized.
- Open multiple focused Xiaohongshu notes and comments for each decision. Capture the note titles and extract consensus plus disagreements.
- Use Baidu Maps for factual route and POI verification. Xiaohongshu is not enough for coordinates, distance, or routing.
- Prefer user-supplied Baidu shortlinks or complete `/dir/` URLs. If absent, search the exact POI in Baidu Maps and verify it is in the expected city/town.
- If a route appears as a straight line, goes through the wrong gate, reaches the destination before waypoints, or forces a backtrack, rebuild it with proper waypoints.
- Compare candidate restaurants and stops against the actual lodging or current route, not against a vague town center.

## Verification

After travel data edits, run:

```powershell
python -m json.tool data\trip.json > $null
rg -n "old phrase" data\trip.json content plans
$env:PYTHONPATH='.'; pytest -q
```

Then check the rendered pages:

- `/day/dayX`
- `/itinerary`
- `/bookings?day_id=dayX` when restaurants, hotels, tickets, or reservations changed

If HTTP output is correct but the browser still shows stale content, tell the user to hard refresh with `Ctrl+F5` or provide a cache-busting URL.
