# Conference Exhibitor List Scraping

## What it does
Investigates industry conference websites for public exhibitor/sponsor directories to extract B2B company leads.

## Prerequisites
- agent-browser with ~/.gstack/chromium-profile
- Direct URL navigation (avoid search engines - they block bots)

## Key findings (updated 2026-06-10)

### SF conferences with accessible sponsor lists:
- **SaaStr Annual** (SF Bay Area, May): saastrannual2025.com - sponsor names in href links + image filenames. 75+ companies extractable via `agent-browser eval "Array.from(document.querySelectorAll('a[href]'))..."` JS
- **Dreamforce** (SF, September): salesforce.com/dreamforce > Sponsors tab - full HTML text list, 66 companies, filterable. Best scrapability of all SF conferences.
- **TechCrunch Disrupt** (SF, Moscone Center, October): techcrunch.com/events/techcrunch-disrupt/ - "Platinum & Gold Partners" section, ~13 visible partners in HTML list

### Blocked / non-SF:
- RSA Conference (SF, Moscone, April) - WAF blocked, 500+ exhibitors - worth retrying with cookies
- Gainsight Pulse - login wall
- Dreamforce 2024/2025 archives - try Wayback Machine
- Most financial conferences (Fintech Meetup, Money20/20, ITC Vegas) are Las Vegas
- Construction (Procore Groundbreak) is Nashville/Orlando not SF
- Health IT (HIMSS) is Chicago

## Pattern: JS extraction for image-based sponsor pages
When sponsor names are embedded in logo image filenames (Squarespace pattern):
```bash
agent-browser eval "Array.from(document.querySelectorAll('img')).map(img => img.src.split('/').pop()).filter(s => s.includes('_') && !s.includes('?')).map(s => s.split('_')[0].replace(/\+/g, ' ')).join('\n')"
```

When company names are in href links:
```bash
agent-browser eval "Array.from(document.querySelectorAll('a[href]')).map(a => a.href).filter(h => h.includes('http') && !h.includes('saastr') && !h.includes('youtube') && !h.includes('twitter') && !h.includes('linkedin')).join('\n')"
```

## Gotchas
- Search engines block bot traffic - use direct URLs only
- Many conference sites use image logos without alt text (not scrapable via accessibility tree)
- Use `agent-browser eval` with JS to extract names from image filenames or href links
- Many conferences that sound SF-based are actually Las Vegas or Chicago
- Verify location first before deep-diving into sponsor extraction
- SaaStr Annual 2025 microsite: saastrannual2025.com (not saastr.com/annual)
- Dreamforce sponsors are on the salesforce.com/dreamforce page under a Sponsors nav link

## Recommended next steps
1. Retry RSA Conference with cookie import from rsaconference.com
2. Check Wayback Machine for Dreamforce 2024/2025 sponsor lists
3. Try Salesforce World Tour SF (annual spring event at Moscone) - smaller than Dreamforce but same ISV audience
4. Gainsight Pulse (SF, May) - try with cookie import first

## Human pacing
- 3-8 seconds between navigations
- 1-3 seconds between clicks
- 30-60 second cooldown after 10 pages
