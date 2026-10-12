-- Q4 · Series state: does last night's result move today's price?
-- Question: for every game that followed another game in the same series, compare its price
--           about 36 hours before first pitch (before the previous game ended) with ~12 hours
--           before (the morning after), split by whether the HOME team won or lost that previous game.
--
-- New idea here: joining a table to itself on a RELATIONSHIP (previous game in the same series)
-- rather than on equal keys. `prev` is the results row for game_no - 1 in the same series; its
-- winner tells us the news the market woke up to.
--
-- We use the milestone captures at 48h/24h (before) and 12h/6h (after) and average each side.

WITH prices AS (
    SELECT gr.series, gr.home_team, gr.game_no, gr.round,
           AVG(CASE WHEN gr.hours_to_game BETWEEN 20 AND 50 THEN gr.median_price END) AS before_median,
           AVG(CASE WHEN gr.hours_to_game BETWEEN  4 AND 14 THEN gr.median_price END) AS after_median,
           AVG(CASE WHEN gr.hours_to_game BETWEEN 20 AND 50 THEN gr.get_in_price END) AS before_get_in,
           AVG(CASE WHEN gr.hours_to_game BETWEEN  4 AND 14 THEN gr.get_in_price END) AS after_get_in
    FROM   game_results gr
    WHERE  gr.bucket = 'mlb_postseason' AND gr.series IS NOT NULL AND gr.opponent_tbd = 0
    GROUP  BY gr.series, gr.home_team, gr.game_no, gr.round
),
prev AS (
    SELECT r.series, r.game_no + 1 AS next_game_no, r.winner AS prev_winner, r.home AS prev_home
    FROM   results r
    WHERE  r.played = 1
)
SELECT p.round, p.series, p.home_team, p.game_no,
       CASE WHEN t.name = p.home_team THEN 'home team won previous'
            ELSE 'home team lost previous' END                          AS news,
       ROUND(p.before_median)                                           AS median_before,
       ROUND(p.after_median)                                            AS median_after,
       ROUND(100.0 * (p.after_median - p.before_median) / p.before_median, 1)   AS median_move_pct,
       ROUND(p.before_get_in)                                           AS get_in_before,
       ROUND(p.after_get_in)                                            AS get_in_after
FROM   prices p
JOIN   prev   ON prev.series = p.series AND prev.next_game_no = p.game_no
JOIN   teams t ON t.code = prev.prev_winner
WHERE  p.before_median IS NOT NULL AND p.after_median IS NOT NULL
ORDER  BY p.round, p.series, p.game_no;

-- ANSWER (2026-10-12): 16 games with a before/after pair. When the home team LOST the previous
-- game, its next home game's median fell ~26% on average (Braves DS G4 −35%, Guardians G2 −31%,
-- Astros WC G2 −31%, Padres G3 −25%, Yankees DS G3 −18%, White Sox G4 −14%). When it WON, the
-- median fell ~10% on average, and three games actually rose (Braves DS G3 +11%, Padres WC G2 +6%,
-- Guardians G5 +2%). Everything decays into first pitch; bad news makes it decay ~2.5× faster.