---
name: travel-plan-consistency
description: Maintain consistency across this Flask travel itinerary project when Codex edits trip plans, daily routes, scenic strategies, restaurants, hotels, supplies, bookings, or preparation checklists. Use when updating data/trip.json, content/day*.md, plans/day*.md, rendered itinerary pages, or any travel-plan text that must not leave stale versions visible in the website.
---

# Travel Plan Consistency

Use this skill whenever a travel-plan change touches an itinerary day, route, POI, restaurant, lodging, map link, supply checklist, booking, or preparation item.

## Source Surfaces

Treat these files as separate visible surfaces that can drift:

- `data/trip.json`: primary website data and API source.
- `content/dayX.md`: supplemental day detail rendered near the bottom of day pages.
- `plans/dayX.md`: planning notes used for maintenance and future edits.
- `templates/*.html` and `static/app.js`: UI visibility and persistence behavior.
- API records in `bookings`, `expenses`, and `supplies`: operational state shown on booking/supply pages.

When the user changes a day-level plan, update every relevant surface in the same turn. Do not update only `data/trip.json` if matching `content/dayX.md` or `plans/dayX.md` still describes the old route.

## Editing Workflow

1. Read current state before writing:
   - Use `travel-api-ops` for itinerary/bookings/supplies API operations when practical.
   - Read `data/trip.json`, `content/dayX.md`, and `plans/dayX.md` for affected days.
   - Search for the old route, old restaurant, old hotel, old time window, and any stale phrase the user mentions.

2. Apply the change consistently:
   - Update the day title, route, summary, next action, risks, timeline, food, scenic rules, lodging, budget, and map links as needed.
   - Update matching booking or supply records if the change affects reservations or preparation status.
   - Update `content/dayX.md` and `plans/dayX.md` so supplemental text does not contradict the website.
   - If the user expects to see the change on `/itinerary`, ensure the template renders the changed field there.

3. Verify stale text is gone:
   - Run `rg` for every old phrase the user saw.
   - Check both `/` and `/day/dayX`; `/itinerary` only shows summary-level fields unless the template exposes more.
   - If a browser shows old content but HTTP output is new, tell the user to hard refresh and provide a cache-busting URL.

## Validation Commands

Run JSON validation after every data edit:

```powershell
python -m json.tool data\trip.json > $null
```

Use the bundled verifier for website and stale-text checks:

```powershell
python .agents\skills\travel-plan-consistency\scripts\verify_travel_update.py `
  --base-url http://127.0.0.1:5000 `
  --stale "13:10-13:40" `
  --stale "午饭与物资采购" `
  --expect "/day/day1::新天润午餐 + 街区采购"
```

For affected days, also check:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/day/day1
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5000/itinerary
```

## Final Response Rule

When reporting completion, state exactly which visible surfaces were updated and which checks passed. If content is present in HTTP output but not in the user's browser, say it is likely stale browser DOM/cache and give a hard-refresh or cache-busting URL.
