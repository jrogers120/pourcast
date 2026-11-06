# Pourcast Nashville

Nashville's 7-day bar forecast: game watches, trivia, karaoke and happy hours.

## How it works

- `data/bars.json`: every bar (name, neighborhood, teams it hosts).
- `data/events.json`: one-time events (`date` + `time`) and weekly ones (`days`, 0 = Sunday, + `time`). Times are Central, 24-hour.
- `data/awards.json`: Bar of the Month (`{"month": "YYYY-MM", "barId", "why"}`) and Bartender of the Week (`{"week": "<Monday YYYY-MM-DD>", "name", "barId", "why"}`) winners. They show on `/vote/` and as a badge on the bar's page.
- `config.json`: site name, web address, contact, and AdSense IDs.
- `build.py`: turns the data into the site in `public/`. No extra packages: `python3 build.py`.
- `.github/workflows/deploy.yml`: rebuilds and publishes to GitHub Pages on every push and every morning.

## Pages it makes

- `/`: 7-day forecast
- `/tonight/<type>/`: college football, NFL, trivia, karaoke, live music, happy hour, special events
- `/watch/<team>/`: "Where to watch <team> in Nashville"
- `/bars/<bar>/` and `/areas/<neighborhood>/`
- `/vote/`: write-in voting for Bar of the Month and Bartender of the Week. Votes arrive by email to `contact_email` until `vote_form_action` in `config.json` is set to a form endpoint (e.g. Formspree), then they post there.
- `/about/`, `/submit/`, `/privacy/`, `sitemap.xml`, `robots.txt`, `ads.txt`

## Turning on ads

1. Point a domain you own (e.g. pourcast.com) at GitHub Pages and set `custom_domain`, `base_url`, and `base_path: ""` in `config.json`.
2. Apply for Google AdSense with that domain.
3. Once approved, put your `ca-pub-...` ID in `adsense_client` and an ad unit ID in `adsense_slot`. The build adds the AdSense script, ad slots and `ads.txt`.
