# Action: producthunt-engage-products

Upvote and comment on Product Hunt products to warm up account / engage with community.

## Prerequisites

- `agent-browser` installed
- Chrome Profile 3 (nossa.iyamu1@gmail.com) has an active PH session as "Nossa Iyamu"

## Steps

### 1. Open PH with real Chrome profile

```bash
agent-browser close
agent-browser --profile "Profile 3" --headed --args "--disable-blink-features=AutomationControlled" open "https://www.producthunt.com"
```

### 2. Navigate to a product page

```bash
agent-browser navigate "https://www.producthunt.com/posts/<product-slug>"
```

### 3. Find upvote button and comment textbox

```bash
agent-browser snapshot | grep -i "upvote.*point\|textbox.*ref=e" | grep -v "Search\|Look for"
```

The main product upvote is in the `complementary` (sidebar) section: `button "Upvote • NNN points"`.
The comment textbox has placeholder "What do you think? …".

### 4. Upvote

```bash
agent-browser click <upvote-ref>
```

Verify: button text changes from "Upvote • N" to "Upvoted • N+1".

### 5. Type and submit comment

```bash
agent-browser click <textbox-ref>
agent-browser type <textbox-ref> "your comment here"
```

### 6. Submit comment (GOTCHA: needs two clicks)

The PH comment editor uses a two-stage submit:
- First click on "Comment" button opens/confirms the editor
- Second click on "Comment" button (new ref!) actually posts

```bash
agent-browser snapshot | grep "button.*Comment\b"
# → button "Comment" [ref=eXXX]
agent-browser click eXXX
sleep 2
agent-browser snapshot | grep "button.*Comment\b"
# → button "Comment" [ref=eYYY]  (different ref!)
agent-browser click eYYY
```

**Better pattern:** Focus textbox first, then click Comment:
```bash
agent-browser click <textbox-ref>
sleep 1
agent-browser click <comment-button-ref>
sleep 3
```

### 7. Verify comment posted

```bash
agent-browser snapshot | grep "your-comment-keyword"
```

The posted comment appears as a `StaticText` under a `Nossa Iyamu` button element.

## Gotchas

- Comment button ref changes after first click — always re-snapshot to get new ref
- Use `type` not `fill` for the comment textbox (it's a contenteditable, not a React input)
- The homepage product cards are clickable but may need `navigate` to the direct URL instead
- Some products have multiple launches — clicking from homepage goes to the right one, direct URL may go to an old launch
