const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, AlignmentType, LevelFormat, BorderStyle, ShadingType, PageBreak,
} = require("docx");

const NAVY = "0B1F3A", GOLD = "C9962B", GREY = "6B7684";

const p = (text, opts = {}) => new Paragraph({
  spacing: { after: 80 }, ...opts.para,
  children: [new TextRun({ text, size: 21, font: "Calibri", ...opts.run })],
});
const rich = (runs, para = {}) => new Paragraph({
  spacing: { after: 80 }, ...para,
  children: runs.map(r => new TextRun({ size: 21, font: "Calibri", ...r })),
});
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 120 }, children: [new TextRun({ text: t, color: NAVY, font: "Calibri" })] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 200, after: 60 }, children: [new TextRun({ text: t, color: GOLD, font: "Calibri" })] });
const bullet = t => new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 40 }, children: [new TextRun({ text: t, size: 21, font: "Calibri" })] });
const bullets = arr => arr.map(bullet);
const small = t => p(t, { run: { size: 18, color: GREY, italics: true } });

function table(header, rows, widths) {
  const total = widths.reduce((a, b) => a + b, 0);
  const cell = (t, i, head) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, fill: NAVY, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({ children: [new TextRun({ text: t, size: 19, font: "Calibri", bold: head, color: head ? "FFFFFF" : undefined })] })],
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, i, true)) }),
           ...rows.map(r => new TableRow({ children: r.map((t, i) => cell(t, i, false)) }))],
  });
}

const entry = (date, blocks) => {
  const out = [h1(date)];
  for (const [title, body] of blocks) {
    out.push(h2(title));
    if (Array.isArray(body)) out.push(...bullets(body));
    else if (typeof body === "string") out.push(p(body));
    else out.push(body);
  }
  return out;
};

const children = [
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: "PRICING OCTOBER", size: 20, bold: true, color: GOLD, font: "Calibri", characterSpacing: 60 })] }),
  new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text: "Project Journal", size: 48, bold: true, color: NAVY, font: "Calibri" })] }),
  p("Michael Schwartz · Auburn University, Business Analytics ’28 · Fall 2026", { run: { color: GREY } }),
  new Paragraph({ spacing: { after: 200 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: GOLD, space: 4 } }, children: [] }),

  h2("What this project is"),
  p("An hourly record of the ticket market for every 2026 MLB postseason game, built to answer one question: how does the market price uncertainty, such as games that may never be played, series that can end early, and matchups that change overnight? It is my hero portfolio project for Summer 2027 sports business-analytics internships."),
  p("Deliverables by Nov 2: a public GitHub repo, a SQL analysis, a regression, a Tableau Public dashboard, and a one-page memo written for a VP of Ticketing."),

  h2("The stack"),
  table(["Tool", "What it does", "Cost"], [
    ["SeatGeek API", "Lists every postseason game: title, UTC start time, TBD flags, when a listing is pulled", "free"],
    ["Ticketmaster Discovery API", "The clubs’ own listings: on-sale / off-sale / cancelled status, sale windows", "free"],
    ["tickets.dev", "The actual prices: every resale listing (section, row, price, fees) plus get-in, median, listing count", "$50/mo, cancel ~Nov 1"],
    ["Python (scrape.py, capture.py, build_db.py)", "Collects from the three sources, paces the credit budget, builds the database", "—"],
    ["GitHub (repo pricing-october)", "Stores the code and every hour’s data; the commit history is the audit trail", "free"],
    ["GitHub Actions", "Runs the Python every hour on GitHub’s servers, no laptop needed", "free"],
    ["cron-job.org", "The reliable hourly alarm clock that tells GitHub Actions to run", "free"],
    ["SQLite (data/pricing.db)", "The database I write SQL against, rebuilt from the CSVs any time", "free"],
    ["Tableau Public (from Oct 16)", "The dashboard", "free"],
    ["Claude Code", "Built the pipeline and blueprint with me; project lives in ~/Desktop/Pricing-October", "—"],
  ], [2600, 5200, 1560]),
  p(""),
  rich([{ text: "How it flows: ", bold: true }, { text: "cron-job.org → GitHub Actions → Python pulls SeatGeek + Ticketmaster + tickets.dev → appends to CSVs → commits to the repo. On my laptop: git pull, python3 build_db.py, then SQL." }]),

  h2("Who does what"),
  table(["Me", "Claude"], [
    ["Green check in the Actions tab each morning", "Watch for failed runs and fix them"],
    ["Results after each game (or tell Claude the score)", "Code changes and pushes"],
    ["Paper bracket and schedule", "Queries with me, then the model, dashboard, memo edits"],
    ["SQL learning; the sessions on the day-by-day plan", "Keep the project memory current"],
    ["Cancel tickets.dev after the World Series", "Daily update and the one interesting thing in the data"],
  ], [4680, 4680]),
  small("Neither of us collects the data. That runs itself."),

  new Paragraph({ children: [new PageBreak()] }),

  ...entry("Sat Sep 27 · Decision and blueprint", [
    ["What I did", [
      "Chose the project. Started from a Hawks price tracker, considered a Giants/Dart-injury angle, rejected it because there was no pre-injury baseline. Chose the MLB postseason: a clean question (how does the market price games that might not be played?), a natural deadline (World Series), and a league-wide design so no single elimination can kill it.",
      "Wrote the 15-page blueprint: question, architecture, bracket, schedule, data dictionary, seven analysis questions, the regression, SQL in learning order, dashboard spec, memo skeleton, outreach messages, skills matrix, day-by-day plan, risks.",
      "Built the first version of the pipeline: scrape.py (collector), build_db.py (SQLite loader), hourly GitHub Actions workflow.",
    ]],
  ]),

  ...entry("Sun Sep 28 · Keys, prices, and going live", [
    ["What I did", [
      "Set the project up as its own workspace: ~/Desktop/Pricing-October, git repo, CLAUDE.md, project memory.",
      "Created API keys: SeatGeek client ID, Ticketmaster Discovery consumer key.",
      "Discovery: neither free API returns prices anymore. SeatGeek’s stats object is empty for every event; Ticketmaster removed priceRanges in March 2025. Decided not to scrape marketplaces directly.",
      "Fix: tickets.dev, a commercial listings API, $50/month for 1,000 captures. Tested on their sandbox, then live. Wrote capture.py with a budget.",
      "First live capture, Yankees–Red Sox Wild Card Game 1, ~30 hours out: 1,954 listings, 10,636 tickets, get-in $120, median $241, top listing $6,702.",
      "First full pass: 31 games, 33,018 listings, zero failures. Early observation: the Yankees’ “if necessary” Game 3 had more listings and a higher median than Game 1, the opposite of the discount I expected.",
      "Created the public GitHub repo pricing-october, added secrets, pushed (lesson: a classic token needs repo and workflow scopes to push a workflow file, and never paste a token into chat). Ran the workflow by hand: green in 15 seconds.",
    ]],
    ["Status at end of day", "Pipeline live and unattended. 2 full snapshots of 135 listed games, 32 resale captures, ~35,000 listings in the repo."],
  ]),

  ...entry("Tue Sep 29 · First pitch day", [
    ["What I did", [
      "Morning check: 4 overnight runs, all green, zero failed captures. Yankees–Red Sox get-in rose from $120 to $136 while 500 listings sold; Braves get-in fell to $18.",
      "Problem 1: GitHub’s scheduler only ran every 4–6 hours, not hourly. Fix: an outside clock (cron-job.org) pokes GitHub every hour.",
      "Problem 2: one run spent the whole day’s credits at once. Fix: each run may only spend its share of the day.",
      "Fixed hours-to-game (was off by the ballpark’s time zone; now uses UTC start times).",
      "Made the data files safe against column changes (new columns go to a versioned file; the loader merges them).",
      "One run failed at the push step; hardened it to rebase and retry. Set up a laptop token so code fixes push without touching GitHub.",
    ]],
    ["Dataset at end of day", "~1,200 game snapshots, 76+ captures, ~74,000 individual listings, growing hourly."],
  ]),

  ...entry("Wed Sep 30 · Wild Card Game 2s", [
    ["What happened", [
      "Morning check found the pipeline ran all 24 hours (good) but spent 390 credits instead of 44 (bad). Two causes, both mine: the capture step was reading an old file version, and four triggers an hour were queueing runs that couldn’t see each other’s spending.",
      "Fixed by noon: every reader merges all file versions, each run pulls the latest data before starting, one trigger per hour, and a flaky API no longer kills a run. Daily budget re-set to fit what was left.",
      "Silver lining: the four Game 2s got captured every ~20 minutes into first pitch. Densest price data of the month.",
      "Started results.csv with the four Game 1 results: Yankees 9–0, White Sox 6–3 (only road winner), Braves 5–3, Padres 8–0.",
    ]],
    ["Status", "Credits: 529 of 1,000 left. Data: ~470 captures, ~625,000 individual listings. All runs green since the fix."],
    ["Lesson", "When a pipeline runs unattended, the budget check is the most important line of code in it. Test it under the conditions it will actually run in (queued runs, new file versions), not just once by hand."],
  ]),

  ...entry("Thu Oct 1 · Wild Card Game 3 day", [
    ["What happened", [
      "Morning check: 29 of 29 runs green since yesterday’s fixes. Budget held at 30 captures overnight.",
      "Logged the four Game 2 results: Yankees 9–2 (sweep), White Sox 7–3 (road sweep), Padres 4–1 (sweep), Phillies 4–3 (forced Game 3 in Atlanta).",
      "Logged the three Game 3s that weren’t needed, marked played = 0. These rows are what turn a price log into a study.",
      "Two tweaks: pacing was spending the whole budget by 3 am ET, so the per-run minimum dropped; added 8 credits to cover the Braves–Phillies Game 3 into first pitch.",
    ]],
    ["First real finding", "The Yankees’ “if necessary” Game 3 never sold at a discount. It held ~3,000 listings at a $116 get-in and ~$285 median, higher than Game 1 at the same point ($241). Sellers priced it as a possible elimination game. After the sweep, Ticketmaster marked it cancelled and every listing vanished overnight. I expected a discount; the data shows a premium."],
    ["Status", "Credits ~491 left. ~500 captures, 650,000+ listings, 11 rows in results.csv. Advancing: Yankees, White Sox, Padres, plus the Braves/Phillies winner."],
  ]),

  ...entry("Sat Oct 3 · Division Series Game 1s", [
    ["What happened", [
      "Caught up after two days away (Copenhagen). Nothing was missed: 47 of 47 runs green, 40 straight hours of snapshots.",
      "Wild Card round closed out in results.csv (12 rows). Braves beat the Phillies in Game 3. Advancing: Yankees, White Sox, Padres, Braves.",
      "Fixed a design flaw in how credits get spent. The daily budget reset at 8 pm ET and was gone by morning, leaving nothing for the hours before first pitch. The collector now captures every game at fixed points: 72, 48, 24, 12, 6, 3 and 1 hour before first pitch. Every game gets the same seven-point price curve. Added a billing-cycle guard so an overspend can’t happen again.",
    ]],
    ["What the data says", [
      "The Braves’ Game 3 was a $38 get-in while it was only a “maybe.” Once the Phillies forced it, it hit $75 four hours before first pitch, median up from $92 to $156, listings cut by more than half. Certainty roughly doubled the price in under a day.",
      "Two sides of the “if necessary” story now: Yankees’ Game 3 carried a premium, Braves’ carried a discount that vanished when the game became real.",
      "Division Series openers: Yankees at Rays is the priciest ticket of the round ($172 get-in, $318 median).",
    ]],
    ["Status", "540 captures, 702,657 listings. About 460 credits left, renewing Oct 28."],
  ]),

  ...entry("Mon Oct 5 · ALDS Game 2s", [
    ["What happened", [
      "Check-in: 63 of 63 runs green since Saturday, no gaps.",
      "The new milestone scheduler works: every game is captured at about 72, 48, 24, 12, 6, 3 and 1 hour before first pitch. Spending dropped to ~17 credits a day.",
      "Logged six Division Series results (results.csv at 18 rows). Rays lead Yankees 1–0, White Sox lead Guardians 1–0, Brewers lead Padres 2–0, Dodgers–Braves tied 1–1.",
    ]],
    ["What the data says", [
      "Losing Game 1 hits the price of the next game. Guardians’ Game 2 median fell from $278 to $146 in two days. Yankees at Rays Game 2: $324 to $173.",
      "Padres’ Game 3 became an elimination game (down 0–2) and got cheaper: $317 to $254.",
      "Priciest ticket of the postseason so far: Guardians at White Sox Game 3 in Chicago, $319 get-in, $685 median.",
    ]],
    ["Status", "581 captures, 734,854 listings. 419 credits left, renewing Oct 28."],
    ["This week: SQL", table(["Day", "Do", "Time"], [
      ["Tue", "SQLBolt lessons 1–6 (SELECT, WHERE, filtering, sorting)", "~1 h"],
      ["Wed", "SQLBolt lessons 7–12 (JOINs, NULLs, expressions, GROUP BY)", "~1.5 h"],
      ["Thu", "SQLBolt 13–18 (skim), then Kaggle Intro to SQL lessons 1–3", "~1.5 h"],
      ["Fri", "First real session: health check and the price-decay curve on the Wild Card data", "~1 h"],
    ], [1200, 6760, 1400])],
  ]),

  ...entry("Tue Oct 6 · ALDS Game 3 eve", [
    ["What happened", [
      "Check-in: 27 of 28 runs green. The one red run and two failed captures were tickets.dev reporting “capture capacity saturated” (a 429). Failed captures aren’t charged, and the scheduler re-tried them on the next pass, so no data gap. Added a short retry so it stops showing as red.",
      "Logged the ALDS Game 2s (results.csv at 20 rows): Rays beat Yankees 5–2 to lead 2–0; White Sox beat Guardians 4–3 to lead 2–0. Both the Yankees and the Guardians face elimination tomorrow.",
      "SQL: SQLBolt lessons 1–6.",
    ]],
    ["What to watch", "Yankee Stadium Game 3 is now an elimination game. Before Game 2 it sat at ~1,620 listings, $124 get-in, $267 median. The 24-hour and 12-hour captures will show whether New York prices an elimination game up (last chance to see them) or down (nobody wants to watch them lose). The Padres’ Game 3 went down in the same situation. If the Yankees go the other way, that is a market-size story for the memo."],
    ["Status", "595 captures, 750,529 listings. 405 credits left, renewing Oct 28."],
    ["Tomorrow", [
      "SQLBolt lessons 7–12, about 1.5 hours. Lesson 12 (GROUP BY with aggregates) is where the project’s queries live.",
      "ALDS Game 3s: Yankees at home facing elimination, 7 pm ET; Guardians at White Sox.",
    ]],
  ]),
];

const doc = new Document({
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  styles: { default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 30, bold: true, color: NAVY, font: "Calibri" }, paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, color: GOLD, font: "Calibri", allCaps: true }, paragraph: { spacing: { before: 200, after: 60 }, outlineLevel: 1 } },
    ] },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1296, bottom: 1296, left: 1440, right: 1440 } } }, children }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(process.argv[2], buf); console.log("wrote", process.argv[2], buf.length, "bytes"); });
