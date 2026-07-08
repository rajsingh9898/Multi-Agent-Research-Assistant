# Frontend E2E Manual Test Guide
## Multi-Agent Research Assistant

### SETUP
1. Start backend: `uvicorn main:app --reload`
2. Start frontend: `npm run dev`
3. Open: `http://localhost:3000`
4. Open DevTools: Network tab + Console tab

---

### TEST A: Complete Happy Path

**Step 1: Landing Page**
- [ ] Page loads without errors in console
- [ ] "Sign in with Google" button visible
- [ ] Feature cards visible below form
- [ ] No broken images or layouts

**Step 2: Authentication**
- [ ] Click "Sign in with Google"
- [ ] Google popup appears
- [ ] Select your account
- [ ] After login:
  - [ ] Your name/avatar in navbar
  - [ ] Research form appears
  - [ ] Toast: "Welcome back, {name}!" or custom greeting

**Step 3: Research Input**
- [ ] Click on topic textarea
- [ ] Type: "Impact of AI on Healthcare"
- [ ] Character counter shows: 33/500
- [ ] Click "Quick" depth card
  - [ ] Card highlights green/blue
  - [ ] Shows "3 questions, ~25 seconds"
- [ ] Language remains "English" (default)
- [ ] Click "Generate Report" button
  - [ ] Button shows spinner + "Starting..."
  - [ ] Toast: "Research started!"

**Step 4: Research Progress Page**
- [ ] Redirected to `/research/{report_id}`
- [ ] "Researching..." in tab title
- [ ] Report ID visible in header (on desktop)
- [ ] WS Status: green dot "Live"
- [ ] Timer counting up
- [ ] 6 agent cards all "Waiting" initially
- [ ] After 1-2 seconds:
  - [ ] Orchestrator card → blue + pulsing
  - [ ] Activity log shows events
- [ ] As each agent completes:
  - [ ] Card turns green with ✅
  - [ ] Progress bar advances
- [ ] Thinking logs: click toggle to expand
  - [ ] Shows agent reasoning steps
- [ ] After all done:
  - [ ] Progress bar = 100% (green)
  - [ ] "Research Complete!" banner appears
  - [ ] Redirect to `/report/{id}`

**Step 5: Report Page**
- [ ] Loading skeleton shown briefly
- [ ] Report loads with all sections:
  - [ ] Title visible in header
  - [ ] Date and stats in header
  - [ ] Executive Summary visible
  - [ ] Key Findings (3+ items)
  - [ ] Detailed Analysis
  - [ ] Limitations
  - [ ] Conclusion
  - [ ] Sources list
- [ ] Sidebar visible (desktop):
  - [ ] Confidence score with circle gauge
  - [ ] Report stats (words, sources, etc)
  - [ ] Follow-up questions (5 items)
- [ ] Test actions:
  - [ ] Click "Download PDF"
    - [ ] Loading toast appears
    - [ ] PDF opens in new tab
    - [ ] Success toast: "PDF ready!"
  - [ ] Click "Share"
    - [ ] Toast: "Link copied!"
    - [ ] Paste link - should work
  - [ ] Click a follow-up question
    - [ ] Redirected to home
    - [ ] Textarea pre-filled with question

**Step 6: History Page**
- [ ] Click "History" in navbar
- [ ] Page loads with your report
- [ ] Report card shows:
  - [ ] Green status dot
  - [ ] Topic text
  - [ ] Date
  - [ ] Confidence bar
  - [ ] "View Report" + "PDF" buttons
- [ ] Test search: type topic keyword
  - [ ] Card filters correctly
- [ ] Test status filter: click "Done"
  - [ ] Only done reports shown
- [ ] Test delete:
  - [ ] Click trash icon
  - [ ] Delete modal appears
  - [ ] Shows report topic in modal
  - [ ] Click "Cancel" → modal closes
  - [ ] Click trash again → "Delete Report"
    - [ ] Toast: "Report deleted!"
    - [ ] Card animates out
    - [ ] History updates

**Step 7: Mobile Testing**
- [ ] Open DevTools → Toggle device toolbar
- [ ] Select iPhone 12 (390px)
- [ ] Test each page:
  - [ ] Home: form fits, depth cards visible
  - [ ] Research: 2-column agent grid
  - [ ] Report: 1-column, sidebar below
  - [ ] History: 1-column cards

---

### TEST B: Auth Guard Testing

**Step 1: Logged Out Protection**
- [ ] Click Sign Out
- [ ] Try to visit: `localhost:3000/history`
  - [ ] Should redirect to `/`
- [ ] Try: `localhost:3000/report/anyid`
  - [ ] Should redirect to `/`
- [ ] Try: `localhost:3000/research/anyid`
  - [ ] Should redirect to `/`

---

### TEST C: Error Handling

**Step 1: API Error Simulation**
- [ ] Stop backend (Ctrl+C in terminal)
- [ ] Try to start research from frontend
- [ ] Expected: Error toast appears
  "Failed to start research" or connection loss banner is displayed.
- [ ] Restart backend

**Step 2: Invalid Report ID**
- [ ] Visit: `localhost:3000/report/fakeid999`
- [ ] Expected: Error state shown
  "Report not found"
- [ ] "Go Home" button visible

---

### WHAT TO CHECK IN DEVTOOLS

**Network Tab:**
- [ ] `POST /api/research/start`:
  - [ ] `Authorization: Bearer eyJ...` in headers
  - [ ] Response: `{report_id: "..."}`
  - [ ] Status: 200
- [ ] WebSocket `/ws/research/{id}`:
  - [ ] Messages tab shows events
  - [ ] Events have correct structure
- [ ] `GET /api/research/{id}`:
  - [ ] Returns full report data

**Console Tab:**
- [ ] No red errors during normal flow
- [ ] No "Cannot read property of undefined"
- [ ] No uncaught promise rejections

---

### RECORDING YOUR RESULTS

After testing, fill in the following template:

Topic: Impact of AI on Healthcare
- [ ] Login: PASS/FAIL
- [ ] Research start: PASS/FAIL
- [ ] Live page WS: PASS/FAIL
- [ ] Report loads: PASS/FAIL
- [ ] PDF download: PASS/FAIL
- [ ] History shows: PASS/FAIL

Topic: Climate change solutions 2025
- [ ] Login: PASS/FAIL
- [ ] Research start: PASS/FAIL
- [ ] Live page WS: PASS/FAIL
- [ ] Report loads: PASS/FAIL
- [ ] PDF download: PASS/FAIL
- [ ] History shows: PASS/FAIL

Topic: Future of electric vehicles
- [ ] Login: PASS/FAIL
- [ ] Research start: PASS/FAIL
- [ ] Live page WS: PASS/FAIL
- [ ] Report loads: PASS/FAIL
- [ ] PDF download: PASS/FAIL
- [ ] History shows: PASS/FAIL

Topic: Blockchain in finance
- [ ] Login: PASS/FAIL
- [ ] Research start: PASS/FAIL
- [ ] Live page WS: PASS/FAIL
- [ ] Report loads: PASS/FAIL
- [ ] PDF download: PASS/FAIL
- [ ] History shows: PASS/FAIL

Topic: Space exploration 2025
- [ ] Login: PASS/FAIL
- [ ] Research start: PASS/FAIL
- [ ] Live page WS: PASS/FAIL
- [ ] Report loads: PASS/FAIL
- [ ] PDF download: PASS/FAIL
- [ ] History shows: PASS/FAIL
