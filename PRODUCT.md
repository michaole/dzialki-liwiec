# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static site: plain HTML/CSS/JS, no build step. The nightly GitHub Actions
job scrapes the portals, writes the data file and publishes the site to
GitHub Pages. No server, no live re-scraping from the UI.

## What it is

A personal watch-list of land plots (działki budowlane i rekreacyjne) for
sale in a handful of villages on the lower Liwiec river (dolny bieg + ujście
do Bugu), aggregated nightly from Otodom, OLX, Gratka and Adresowo and
filtered to the places in `miejscowosci_liwiec.csv`.

## User and situation

One person (the owner), on a laptop, doing sit-down research while looking
for a plot to buy. A nightly email announces new listings; the site is where
they are reviewed and compared.

## What decides a closer look

1. **Freshness** — what is new since the last visit, how long a plot has
   been on the market, and which listings disappeared (possibly sold).
2. **Price** — total price, price per m², and price drops over time.

Location (village, river section) and area are context, not the primary
sort.

## Durable facts and constraints

- Language of the UI: Polish.
- Listing IDs (`olx_…`, `gratka_…`, `adresowo_…`, bare Otodom ids) and
  `data/seen_ids.json` drive the email digest and must stay stable.
- Data is public portal listings; every listing links out to its source.
- The places list is curated by hand and may change.
- Favourites are personal to the owner's browser.

The earlier Streamlit app was retired once the static site went live
(October 2026); the site is the only UI.
