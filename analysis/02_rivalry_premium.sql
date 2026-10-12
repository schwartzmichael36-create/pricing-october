-- Q2 · The rivalry premium
-- Question: was Yankees–Red Sox priced above the other three Wild Card hosts at the same
--           hours-to-game?
--
-- New idea here: a SELF-JOIN. The same table appears twice (a and b). Row a is a Yankees capture;
-- row b is any other Wild Card Game 1 capture taken in the same hour. We average b's prices and
-- divide a's by that. Same-hour matching is what makes it fair: we compare like with like.

SELECT substr(a.captured_at, 1, 13)                       AS hour_utc,
       ROUND(a.hours_to_game, 1)                          AS nyy_hours_to_game,
       a.get_in_price                                     AS nyy_get_in,
       ROUND(AVG(b.get_in_price))                         AS others_get_in,
       ROUND(a.get_in_price / AVG(b.get_in_price), 2)     AS get_in_ratio,
       a.median_price                                     AS nyy_median,
       ROUND(AVG(b.median_price))                         AS others_median,
       ROUND(a.median_price / AVG(b.median_price), 2)     AS median_ratio
FROM   resale a
JOIN   resale b
  ON   substr(b.captured_at, 1, 13) = substr(a.captured_at, 1, 13)   -- same UTC hour
 AND   b.round = 'WC' AND b.game_no = 1
 AND   b.home_team <> a.home_team
WHERE  a.round = 'WC' AND a.game_no = 1
  AND  a.home_team = 'New York Yankees'
GROUP  BY a.captured_at
ORDER  BY a.captured_at;

-- ANSWER (2026-10-12): Yankees–Red Sox Game 1 traded at 2.3× the other Wild Card hosts' get-in
-- 32 hours out and 3.4× at 9 hours out; median 1.9× → 2.5×. The gap WIDENED into first pitch:
-- the other three hosts cut prices to clear, New York didn't have to.