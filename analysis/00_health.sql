-- Q0 · Is the pipeline healthy?
-- Question: how many captures does each game have, and did we get the milestones we planned
--           (72, 48, 24, 12, 6, 3, 1 hours before first pitch)?
--
-- How to read it:
--   SELECT   the columns we want to see
--   FROM     the `resale` view (one row per game per capture, with hours_to_game precomputed)
--   WHERE    only MLB postseason games (the Giants/Jets rows are a side project)
--   GROUP BY one output row per game
--   ORDER BY soonest first pitch first
--
-- GROUP_CONCAT glues the hours-to-game of every capture into one string so we can eyeball
-- the milestone coverage without a chart.

SELECT title                                              AS game,
       substr(start_utc, 1, 16)                           AS first_pitch_utc,
       COUNT(*)                                           AS captures,
       GROUP_CONCAT(CAST(ROUND(hours_to_game) AS INT), ' ') AS at_hours_before
FROM   resale
WHERE  bucket = 'mlb_postseason'
GROUP  BY title, start_utc
ORDER  BY start_utc;

-- ANSWER (2026-10-12): 68 postseason games captured, 635 captures. Wild Card games have 20–50
-- captures each (the Sep 30 overspend); every Division Series game has its 7 milestones.
-- The LCS placeholders ("TBD at …") have 1–2 captures each, which is expected: they only get
-- captured once they are inside 72 hours.
