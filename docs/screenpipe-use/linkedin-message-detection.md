# "Did user complete this action?" → checked ui_events only → use ground-truth-first investigation

## Rule

**When determining whether an action was completed (message sent, form submitted, task finished), never conclude from the user's click alone. The user's click might be unlabeled. Instead, find a CONFIRMED instance of the action completing, study what that looks like across ALL data tables, build a detection pattern, then apply it to the uncertain cases.**

This is the "ground truth first" methodology. It applies to any platform, not just LinkedIn.

## The methodology: go deeper every time

### Step 1 — Don't conclude from one table

`ui_events` captures clicks, but ~98% of `AXGroup` and ~57% of `AXImage` clicks have no `element_name`. A "Send" button click often shows up as an unlabeled `AXButton` at some (x, y) coordinate. Finding no "Send" click does NOT mean the user didn't send.

**Before concluding something didn't happen, ask: did I check every table?**

| Table | What it captures | When it's the best source |
|-------|-----------------|--------------------------|
| `ui_events` | Clicks, typed text, key presses, clipboard, app switches | User intent, typed content, navigation flow |
| `frames.accessibility_text` | Full accessibility tree of the screen at capture time | Platform confirmation UI (toasts, dialogs, status changes) |
| `frames.full_text` | OCR of the screen (tab titles, rendered text) | Content visible on screen that accessibility misses |
| `elements` | UI element tree with bounds, roles, text | Resolving unlabeled clicks via coordinate matching |
| `*_fts` | Full-text search indexes | Finding needles across large time ranges |

### Step 2 — Find a confirmed case (ground truth)

When you need to detect whether action X happened, first find ONE case where you KNOW it happened. Then study what that case looks like across every table.

**Example from this session:**

Problem: "Did Nossa send LinkedIn DMs?"
- I KNEW the Tennison Chan message was sent (visible in `ui_events.element_name`: `"Options for the message from Nossa: Hi Tennison..."`)
- So I studied what the Tennison send looked like in `frames.accessibility_text`
- Found: `"Unable to edit message. Please try again."` — a toast that proves a message was sent and delivered
- That pattern became the detection template for every other DM

**The process:**
1. Identify ONE confirmed positive case
2. Query ALL tables for that timestamp ± a few seconds
3. Document every signal that appears (toasts, dialogs, state changes, counts)
4. Build SQL templates from those signals
5. Run the templates across the full time range to find all matches

### Step 3 — Search for the platform's confirmation UI, not the user's action

Every platform shows confirmation after an action completes:
- LinkedIn: `"Your invitation to connect was sent"`, `"1 Message"` count
- Gmail: `"Message envoyé"` / `"Message sent"` toast
- Reddit: post appears in feed
- WhatsApp: `"Sent to [Name], Delivered"` label on the message

These confirmations live in `frames.accessibility_text` — the richest data source for completion detection. The user's click is the INPUT. The platform's confirmation is the OUTPUT. Always search for the output.

```sql
-- Generic pattern: search frames for platform confirmation text
SELECT f.id, f.timestamp, f.window_name,
       SUBSTR(f.accessibility_text, 
              INSTR(f.accessibility_text, '<confirmation text>'), 200)
FROM frames f
WHERE f.accessibility_text LIKE '%<confirmation text>%'
ORDER BY f.timestamp ASC;
```

### Step 4 — Track state changes over time

Some signals only make sense as before/after comparisons:
- Profile showed `"Connect"` button → later showed `"Message [Name]"` → connection was accepted
- Profile showed no message count → later showed `"1 Message"` → a DM was sent
- Dialog showed `"Add a note?"` → next frame showed `"Sending"` → next showed `"sent"` → completed

Query the same page at different timestamps to detect transitions:

```sql
-- Track state changes for a specific page/person
SELECT f.timestamp,
       CASE 
         WHEN f.accessibility_text LIKE '%state_A%' THEN 'BEFORE'
         WHEN f.accessibility_text LIKE '%state_B%' THEN 'AFTER'
       END as status
FROM frames f
WHERE f.window_name LIKE '%[target]%'
ORDER BY f.timestamp ASC;
```

### Step 5 — When no definitive signal exists, build inference chains

Screenpipe captures frames on triggers (click, visual_change, idle). If the user acts between triggers, no frame captures the result. In that case, chain behavioral signals:

**High-intent pattern (likely completed):**
compose activity → typing → no Discard/Cancel → immediate navigation to next target

**Abandoned pattern (not completed):**
compose activity → Discard/Cancel click
compose activity → long pause → same page → no further action

**Cross-app corroboration:**
drafting in Claude + copy-paste to target app + compose activity = prepared, high-effort outreach → very likely sent

### Step 6 — Challenge every "not found" before reporting

Before telling the user something didn't happen:
1. ❌ Did I only check `ui_events`? → check `frames` too
2. ❌ Did I search for the user's click? → search for the platform's confirmation instead
3. ❌ Did I only check one time window? → the action might have happened later (midnight messaging spree)
4. ❌ Did I assume the action happened on the expected page? → it might have happened from a different window (messaging overlay on wrong profile's page)
5. ❌ Did I check for behavioral completion patterns? → compose + no discard + navigate away

Only report "not done" when ALL of these come back empty.

## What happened

Session on 2026-05-13. User asked to identify 6 things done yesterday and 6 things missed.

**First pass (shallow):** Checked `ui_events` for Send/Connect clicks. Found nothing for most LinkedIn DMs. Reported "Thomas Fox outreach NOT COMPLETED" and "Hannes message NEVER SENT."

**User challenged:** "did you do a deep enough research?"

**Second pass:** Went to `frames.accessibility_text`. Found connection request toasts (`"invitation to connect was sent"`), message options menus (`"Options for the message from Nossa"`), dialog state machines, and "1 Message" counts. Confirmed 15+ connection requests and several DMs that were invisible in `ui_events`.

**User challenged again:** "I actually sent ALL these DMs."

**Third pass:** Discovered the gap — some DMs had no definitive signal because Screenpipe didn't capture a frame between the send and navigation. Built the inference chain: heavy compose + no Discard + next target = likely sent.

**The meta-lesson:** Each challenge forced a deeper layer. The methodology is: always have another table to check, always find a confirmed case to calibrate against, always search for the platform's output (not the user's input), and never report "not done" until every data source is exhausted.
