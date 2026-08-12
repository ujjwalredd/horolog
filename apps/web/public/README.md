# Vendored public assets

`hero-landscape.jpg` — the landing page's hero background. Self-hosted
rather than hotlinked, same reasoning as `app/fonts/README.md`: a build
that reaches out to a third-party host at request time (or build time) is
one outage away from a broken page, and Unsplash rate-limits/blocks
scraper-shaped traffic. Originally `https://unsplash.com/photos/xdWEK9jm5cQ`
(Unsplash License — free to use, attribution appreciated but not required).
Downloaded at 1600px wide; re-run
`curl -sL -A "Mozilla/5.0" "<unsplash-url>?q=80&w=1600&auto=format&fit=crop" -o hero-landscape.jpg`
against a different photo to swap it.

`screenshots/*.png` — real captures of the app (`npm run seed:demo`'s
sample week), used by the landing page's "Screens" section. Copied from
`docs/screenshots/`, which `README.md` also embeds directly — re-capture
there and re-copy here if the UI changes enough to make them stale.
