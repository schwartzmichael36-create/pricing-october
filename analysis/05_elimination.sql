-- Q5 · Elimination games vs. the rest
-- Originally this slot was "primary vs resale gap". Ticketmaster removed prices from its public
-- API in March 2025, so the club-side number isn't available; the gap question moves to the
-- memo's limits section. In its place: the most useful split the results table gives us.
--
-- Question: at the same hours-to-game, are games where the HOME team can be eliminated priced
--           differently from games where it can't?
--
-- The home team faces elimination when its series losses before the game equal the number
-- needed to lose the series (1 in a best-of-3, 2 in a best-of-5, 3 in a best-of-7).

WITH g AS (
    SELECT round, home_team, game_no, hours_to_game, get_in_price, median_price, listing_count,
           CASE WHEN (round = 'WC'  AND home_l_before = 1)
                  OR (round = 'DS'  AND home_l_before = 2)
                  OR (round = 'LCS' AND home_l_before = 3)
                  OR (round = 'WS'  AND home_l_before = 3) THEN 1 ELSE 0 END AS home_faces_elimination,
           CASE WHEN (round = 'WC'  AND home_w_before = 1)
                  OR (round = 'DS'  AND home_w_before = 2)
                  OR (round = 'LCS' AND home_w_before = 3)
                  OR (round = 'WS'  AND home_w_before = 3) THEN 1 ELSE 0 END AS home_can_clinch
    FROM   game_results
    WHERE  bucket = 'mlb_postseason' AND series IS NOT NULL AND opponent_tbd = 0
      AND  hours_to_game BETWEEN 0 AND 48
)
SELECT round,
       CASE WHEN home_faces_elimination = 1 THEN 'home faces elimination'
            WHEN home_can_clinch = 1        THEN 'home can clinch'
            ELSE 'neither' END                            AS situation,
       CASE WHEN hours_to_game > 24 THEN '24-48h'
            WHEN hours_to_game > 6  THEN '6-24h'
            ELSE '0-6h' END                               AS bucket,
       COUNT(DISTINCT home_team || game_no)               AS games,
       COUNT(*)                                           AS captures,
       ROUND(AVG(get_in_price))                           AS avg_get_in,
       ROUND(AVG(median_price))                           AS avg_median,
       ROUND(AVG(listing_count))                          AS avg_listings
FROM   g
GROUP  BY round, situation, bucket
ORDER  BY round, situation,
          CASE bucket WHEN '24-48h' THEN 0 WHEN '6-24h' THEN 1 ELSE 2 END;

-- ANSWER (2026-10-12): Division Series, 6–24h out: home can clinch → median $528; home faces
-- elimination → $236; neither → $223. Elimination games are priced like ordinary games, NOT at a
-- discount; the clincher is the premium product (+130%). Caveat: both DS clinch games were the
-- White Sox at home (first playoff games there in years), so clinch and Chicago are confounded;
-- the LCS will add clincher games in other markets to separate them.