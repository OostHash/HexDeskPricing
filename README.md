# HexDeskPricing

Price data for [HexDesk](https://github.com/OostHash/HexDesk).

A scheduled GitHub Action copies the daily price data from
[relics.run](https://relics.run) twice a day, so HexDesk users download it from
here instead of each hitting relics.run themselves.

| File | Contents | Source |
| --- | --- | --- |
| `price_history_latest.json` | Median sell price per tradeable item, newest day available | relics.run, derived from warframe.market |
| `items.json` | Item names and warframe.market slugs | relics.run |
| `ducat_exceptions.json` | Prime parts whose ducat value does not follow the standard rarity formula | Maintained by hand in this repo |
| `meta.json` | Which day the prices are from and when they were last updated | Written by the workflow |

## How the update works

`scripts/update.py` downloads the newest files and checks that they are valid
and complete before replacing anything. If relics.run is down or returns broken
data, the last good copy stays published and the workflow run fails, which
sends a notification.

Run it by hand from the **Actions** tab (*Update prices* → *Run workflow*), or
locally:

```bash
python3 scripts/update.py
```

GitHub disables scheduled workflows in repositories without activity for 60
days. The daily data commits count as activity, but if the workflow is ever
disabled, re-enable it from the Actions tab.

## Editing ducat exceptions

Edit `ducat_exceptions.json` and commit. Keys are lowercase full item and part
names, values are the ducat amount. HexDesk picks up the change on its next
catalogue refresh, without a new release.

## Credits

Price data comes from [relics.run](https://relics.run), which aggregates
[warframe.market](https://warframe.market) statistics. This repository is not
affiliated with either, or with Digital Extremes Ltd.
