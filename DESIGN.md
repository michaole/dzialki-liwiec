---
name: Działki nad Liwcem
description: A dense, sortable price list of land plots on the lower Liwiec, where price leads and changes are pinned on fluorescent market cards.
colors:
  ground: "#e6e9e4"
  surface: "#f6f7f3"
  row-hover: "#eef0ea"
  rule: "#cfd4cc"
  rule-strong: "#b3b9b0"
  ink: "#14171a"
  ink-2: "#464d52"
  ink-3: "#5d656b"
  paper-on-ink: "#f1f3ee"
  muted-on-ink: "#b7bdb6"
  field-white: "#ffffff"
  kraft: "#b88a5a"
  kraft-ink: "#3d2a17"
  kraft-pale: "#e9dccb"
  kraft-board: "#ece3d6"
  kraft-rule: "#d3c3ad"
  lime: "#c8f000"
  lime-ink: "#1c2400"
  orange: "#ff6b1a"
  orange-ink: "#2b0f00"
  drop-text: "#b23c00"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.005em"
  price:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.45rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.01em"
    fontFeature: "tnum, lnum"
  number:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 800
    lineHeight: 1
    fontFeature: "tnum"
  tag:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "0.03em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.45
  meta:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, sans-serif"
    fontSize: "0.78rem"
    fontWeight: 400
    lineHeight: 1.3
rounded:
  tag: "2px"
  md: "6px"
  pill: "999px"
spacing:
  s1: "4px"
  s2: "8px"
  s3: "12px"
  s4: "16px"
  s5: "24px"
  s6: "32px"
components:
  tag-new:
    backgroundColor: "{colors.lime}"
    textColor: "{colors.lime-ink}"
    typography: "{typography.tag}"
    rounded: "{rounded.tag}"
    padding: "3px 8px 2px"
  tag-cheaper:
    backgroundColor: "{colors.orange}"
    textColor: "{colors.orange-ink}"
    typography: "{typography.tag}"
    rounded: "{rounded.tag}"
    padding: "3px 8px 2px"
  tag-gone:
    backgroundColor: "{colors.kraft-pale}"
    textColor: "{colors.kraft-ink}"
    typography: "{typography.tag}"
    rounded: "{rounded.tag}"
    padding: "3px 8px 2px"
  tag-row:
    padding: "2px 6px 1px"
  header-bar:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper-on-ink}"
    typography: "{typography.display}"
    padding: "12px 24px"
  filter-board:
    backgroundColor: "{colors.kraft-board}"
    textColor: "{colors.ink-2}"
    padding: "16px 24px"
  input-field:
    backgroundColor: "{colors.field-white}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    height: "34px"
    padding: "0 10px"
  input-unit:
    backgroundColor: "{colors.kraft-pale}"
    textColor: "{colors.ink-2}"
    padding: "0 9px"
  chip:
    backgroundColor: "{colors.field-white}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    height: "34px"
    padding: "0 11px"
  chip-checked:
    textColor: "{colors.ink}"
  button-quiet:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    height: "34px"
    padding: "0 12px"
  button-quiet-hover:
    textColor: "{colors.ink}"
  icon-button:
    textColor: "{colors.ink-3}"
    rounded: "{rounded.md}"
    size: "30px"
  icon-button-hover:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
  table-header:
    backgroundColor: "{colors.kraft-board}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "10px 12px 8px"
  table-row:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "9px 12px"
  table-row-hover:
    backgroundColor: "{colors.row-hover}"
  detail-row:
    backgroundColor: "{colors.kraft-board}"
    padding: "16px 12px 16px 52px"
---

# Design System: Działki nad Liwcem

## Overview

**Creative North Star: "The Market Stall Price Board"**

A trader's stall at a country market: concrete-grey ground, a black felt-tip header, kraft cardboard for the chrome you handle (filters, column heads, opened rows), and fluorescent card tags stuck on, slightly askew, wherever something has changed. Price is the loudest thing on every row. Everything that is not a price, a number or a change tag speaks in a quiet system sans.

The system is dense on purpose. It is one sortable table, not a grid of photo cards and not a row of KPI tiles. Columns have fixed widths and never move; filters only hide rows. Colour carries state, not decoration: lime means new, orange means cheaper, kraft means gone, and the days-on-market ramp runs one fixed fresh-to-stale scale. Motion is limited to a single "stick" moment when the change tags land after data loads, and a straighten-up when a header tag is hovered or pressed.

The UI language is Polish and the setting is a laptop at a desk; on narrow screens rows fold into two-line blocks but keep the same vocabulary.

**Key Characteristics:**
- Concrete ground, ink header, kraft chrome, fluorescent state cards.
- Heavy condensed face (Barlow Condensed 800) for prices, numbers, tags and the site name only; system sans for everything else.
- Tabular figures everywhere; numeric columns right-aligned tight to the column edge.
- Fixed-width columns that never shift.
- One fluorescent accent per live state, never as decoration.

## Colors

A cool, nearly neutral concrete-and-ink base, warmed by kraft board, with two fluorescent card colours that only ever mean a change.

### Primary
- **Fluorescent Lime** (lime): the NOWE (new) card tag, the filled starred-favourite icon, text selection, and the outer halo of the focus ring. On lime, text is always **Lime Ink** (lime-ink).
- **Fluorescent Orange** (orange): the TAŃSZE (cheaper) card tag, which carries the price drop and the struck-through old price. On orange, text is always **Orange Ink** (orange-ink).

### Secondary
- **Kraft** (kraft): the outline of the ZNIKNĘŁO (gone) tag and the 31–90 day step of the days-on-market ramp.
- **Kraft Board** (kraft-board): the filter row, the sticky table header, and opened detail rows; the "handled cardboard" surface. Divided by **Kraft Rule** (kraft-rule).
- **Pale Kraft** (kraft-pale): the gone tag fill and the unit suffix boxes (zł, m²) on numeric inputs. Text on kraft is **Kraft Ink** (kraft-ink).
- **Drop Red-Orange** (drop-text): the readable text form of orange, used for downward price steps in price history where fluorescent orange would fail contrast as text.

### Neutral
- **Concrete Ground** (ground): page background; also the hover wash behind icon buttons.
- **Table Paper** (surface): the table body. **Row Hover** (row-hover) washes a hovered row.
- **Rule** (rule) and **Strong Rule** (rule-strong): row dividers and the table frame; input, chip and unit borders, link underlines at rest.
- **Felt-Tip Ink** (ink): primary text, the header bar fill, the inner focus outline, checked chip borders.
- **Ink 2** (ink-2) and **Ink 3** (ink-3): secondary text (labels, column heads, smaller numbers) and tertiary text (section names, sources, units, missing values, gone rows).
- **Paper on Ink** (paper-on-ink) and **Muted on Ink** (muted-on-ink): the site name and the meta line inside the black header.
- **Field White** (field-white): input, textarea and chip fills.

### Days-on-market ramp
One fixed scale, assigned in script, never re-tuned per view: up to 7 days `#a9cc00` (fresh lime-green), up to 30 days `#7d9a3a` (olive), up to 90 days `#b88a5a` (kraft), beyond 90 days `#9aa0a6` (stale grey). Bar width maps 0–90 days to 4–100%.

### Named Rules
**The One Card Per State Rule.** Lime means new, orange means cheaper, kraft means gone. A fluorescent colour never appears without a change behind it, and is never used as decoration, a section accent or a button fill.

**The Ink-On-Fluo Rule.** Text on lime or orange is always its dedicated near-black ink (lime-ink, orange-ink), never white and never the plain ink.

## Typography

**Display / Numeric Font:** Barlow Condensed 600/800 (self-hosted woff2, latin + latin-ext; fallback Arial Narrow, sans-serif)
**Body Font:** system-ui stack (-apple-system, Segoe UI, Roboto, Helvetica Neue)

**Character:** A heavy condensed poster face, like a hand-lettered price card, sitting on a neutral system sans that stays out of the way. The condensed face is reserved for things you read as figures.

### Hierarchy
- **Display** (800, 1.75rem, line-height 1): the site name in the ink header. The only "heading" in the UI.
- **Price** (800, 1.45rem, line-height 1, tabular + lining figures): the total price on every row. The largest type on screen.
- **Number** (800, 1.05rem, tabular, in Ink 2): PLN/m² and area. Unit suffixes drop to the system sans at 600, 0.8rem, Ink 3.
- **Tag** (800, 0.95rem, uppercase, 0.03em tracking): header change tags; row tags shrink to 0.8rem.
- **Body** (400, 15px, line-height 1.45, tabular figures on): listing titles (500), village names (600), everything else.
- **Label** (600, 0.75rem, Ink 2): filter labels, column heads, detail labels. Sentence case, no tracking.
- **Meta** (400, 0.78–0.85rem, Ink 3): river section, source, summary, footer, note previews.

### Named Rules
**The Figures-Are-Condensed Rule.** Barlow Condensed is for prices, numbers, change tags and the site name. Labels, titles, notes and controls stay in the system sans.

**The Tabular Rule.** Figures are tabular across the whole page; numeric columns and their headers are right-aligned so digits line up down the column.

## Layout

Full-width, three horizontal bands: the ink header bar, the kraft filter row (a wrapping flex row aligned to the bottom of each field), and the list band holding a one-line summary and the table. Side padding is 24px (s5) on desktop and 16px (s4) under 860px.

The table uses fixed layout with fixed column widths: star 44px, change 132px, village 140px, price 136px, PLN/m² 84px, area 104px, days on market 124px, note 150px; the listing title takes the remainder. The header row is sticky. Rows are 9px/12px padded and divided by a 1px rule.

Spacing runs on a 4px base: 4 / 8 / 12 / 16 / 24 / 32. Control height is 34px throughout the filter row.

Under 860px the header stacks, the table head is hidden, and each row becomes a four-row grid: star, village and price on top; note button and title; change tag, PLN/m² and area; then the days-on-market bar (max 220px). The detail row collapses to one column.

**The Columns Never Move Rule.** Column widths are fixed; filtering, sorting and opening a detail row never shift a column. Filters hide rows, they do not reflow the table.

## Elevation & Depth

Flat by default. Surfaces separate by tone (ground, table paper, kraft board, ink header) and 1px rules, not shadows. The single exception is the fluorescent card tag, which carries a small soft paper shadow so it reads as a card stuck onto the board.

### Shadow Vocabulary
- **Card shadow** (`box-shadow: 0 1px 1px rgba(20,23,26,.18), 0 3px 6px -2px rgba(20,23,26,.28)`): new and cheaper tags only. The gone tag is flat with a kraft outline.
- **Stick lift** (`box-shadow: 0 6px 12px -2px rgba(20,23,26,.3)`): the starting frame of the tag entrance animation only.

### Named Rules
**The Only Cards Cast Shadows Rule.** Shadows belong to the fluorescent tags. Tables, filters, inputs and buttons stay flat.

## Shapes

Gently rounded utilitarian chrome (6px) for the table frame, inputs, quiet buttons and icon buttons; fully rounded pills for portal chips and toggles; near-square cards (2px) for tags. Tags are rotated a degree or two (new −2.5°, cheaper +1.5°, gone −1°) so they look hand-stuck. Numeric inputs fuse with their unit box into one rounded shape. Sort direction is a small clip-path triangle, not an icon glyph. Icons are 18px line SVGs (1.8 stroke, round caps).

## Components

### Change Tags (signature)
The fluorescent market card. Heavy condensed, uppercase, near-square, slightly askew, with a soft card shadow.
- **New:** lime fill, lime-ink text, tilt −2.5°.
- **Cheaper:** orange fill, orange-ink text, tilt +1.5°; on rows it carries the drop ("−20 000") followed by the old price struck through.
- **Gone:** pale kraft fill, kraft-ink text, 1px kraft outline, no shadow, tilt −1°.
- **Row size:** 0.8rem, 2px 6px 1px padding.
- **As header buttons:** they show counts since the last visit and act as quick filters. Hover straightens to 0° and lifts 1px (0.25s ease-out-expo); pressed straightens with a 2px paper-on-ink outline; disabled at 45% opacity, still tilted.
- **Entrance:** after data loads, row tags "stick" from −9° with a deeper shadow over 0.5s, staggered 25ms per row; only when reduced motion is not requested.

### Header Bar
Ink fill, 12px 24px padding. Site name in Display; data date in Muted on Ink at 0.8rem; the "since last visit" label plus the three change-tag buttons on the right. Focus inside the bar is a lime outline with no halo.

### Filter Row
Kraft board band with a kraft-rule bottom edge. Each field is a label (Label style) stacked 5px above its control.
- **Inputs / Selects:** 34px high, white, 1px Strong Rule border, 6px radius, 10px side padding, placeholder in Ink 3. Numeric inputs are right-aligned, 110px wide, with a pale-kraft unit box fused on the right.
- **Chips / Toggles:** 34px pills, white, Strong Rule border, Ink 2 text with a native checkbox tinted ink. Checked: ink text and ink border. Keyboard focus draws the standard focus ring on the whole pill.
- **Quiet Button** ("Wyczyść"): transparent, underlined in Strong Rule; hover darkens text and underline to ink.

### Table
Table paper inside a 1px Rule frame with 6px corners. Sticky kraft-board header with Label-style heads; sortable heads are bare buttons, the active one turns ink and shows a triangle. Rows hover to Row Hover. Gone rows recede: village, title and price drop to Ink 3 and the price is struck through with a 2px line.
- **Village cell:** village name 600, river section beneath in Meta.
- **Title cell:** 500-weight link with a 13px outbound icon, source name beneath in Meta.
- **Price / Number cells:** right-aligned condensed figures; missing values read "brak" in Ink 3 sans.
- **Days on market:** a 6px rounded bar on a Rule track, filled from the fixed ramp, with the day count right-aligned.

### Icon Buttons
30px square, transparent, Ink 3; hover to ink on Concrete Ground. The favourite star, when pressed, fills lime with an ink stroke. The note button shows an expanded state with the same ground wash.

### Detail Row
Opens under a row on kraft board, indented 52px to clear the star column. Two columns: a note textarea (white, Strong Rule border, 6px radius, saved status in Meta beneath) and the price history list, where prices are condensed 800 in ink, drops are bold Drop Red-Orange, rises are Ink 3.

### Focus
One ring everywhere: 2px ink outline at 2px offset plus a 5px lime halo, 3px radius. Inside the ink header the ring is a lime outline alone.

## Do's and Don'ts

### Do:
- **Do** make the price the largest type on every row (Barlow Condensed 800, 1.45rem), right-aligned in its fixed column.
- **Do** use lime only for new, orange only for cheaper, and kraft for gone; put lime-ink or orange-ink text on them.
- **Do** keep column widths fixed and let filters hide rows rather than reflow the table.
- **Do** keep all figures tabular and numeric columns right-aligned.
- **Do** colour days on market only from the fixed ramp (#a9cc00 / #7d9a3a / #b88a5a / #9aa0a6 at 7 / 30 / 90 / 90+ days).
- **Do** use the shared focus ring (2px ink outline + 5px lime halo) on every interactive element.
- **Do** keep chrome you handle (filters, column heads, opened rows) on kraft board, and data on table paper.

### Don't:
- **Don't** use fluorescent lime or orange as decoration, button fills or section accents.
- **Don't** put shadows on anything but the fluorescent tags.
- **Don't** set labels, titles, notes or controls in the condensed face.
- **Don't** replace the price table with photo cards or KPI tiles.
- **Don't** use fluorescent orange as text colour; use Drop Red-Orange (drop-text) for drop figures.
- **Don't** add motion beyond the tag "stick" entrance and the header-tag straighten, and always guard it with prefers-reduced-motion.
