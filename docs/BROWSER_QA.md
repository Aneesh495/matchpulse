# Browser diagnostic observations

Executed on the local Go/Python/SQLite service on 2026-11-11 using the real TypeScript application. No production route was replaced with mock data. The authored fixture is explicitly synthetic throughout the UI.

| Journey | Observed result |
| --- | --- |
| Finish replay | Full time, 1 to 0, v37, 23 rated appearances, one unused player unrated |
| Advance after match | Separate EUR 19 million fictional permanent sale, EUR 2 million add-ons separate |
| Keeper inspection | +0.2100 contribution reason from save-1 |
| Prior version v28 | Provisional score 1 to 0 |
| Corrected version v30 | Score 0 to 0 and visible VAR reason |
| Role revision | Adam Vale CM after the authored tactical correction |
| Compare two players | Comparison selection and individual contributions visible |
| Empty search | Explicit no-matching-players state |
| Ticker search | Leo Marin conditional estimate differs from observed transaction |
| Keyboard inspect and Escape | Dialog closes; focus returns to a button for demo-p9 |
| Reload and reconnect | Saved final state and stream sequence retained |
| Desktop 1440 by 1000 | Scoreboard, metrics, player table and schematic pitch verified |
| Mobile 390 by 844 | Document scrollWidth 390, no page overflow, responsive scoreboard verified |
| Initial constrained view | A clipped scoreboard was found and corrected before final capture |
| Async drawer close | A focus race was found; stale requests now abort and cannot rerender a closed dialog |

Screenshots: [desktop match](screenshots/match-desktop.png), [desktop ticker](screenshots/ticker-desktop.png), [player evidence](screenshots/player-evidence.png), [mobile match](screenshots/match-mobile.png). These observations do not establish full assistive-technology accessibility, actual live freshness, or production hosting. API teardown, oversized input, cross-origin rejection, CSV contents and actual worker restart are separately exercised by the Go integration tests.
