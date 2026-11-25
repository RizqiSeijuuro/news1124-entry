# news1124-entry

[![make.fun · news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/RizqiSeijuuro/news1124-entry/rank.svg)](https://make.fun/bounty/news-image-20261124/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/RizqiSeijuuro/news1124-entry/reward.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)

A standard-library-only Python 3.13 program that renders a single 1024x1024 PNG summarizing world news from 24 November 2026 — IRGC mine blasts on oil tankers in the Strait of Hormuz, Russia's "open war" threat against Estonia over its closed border, Trump helping restore Jensen Huang as Nvidia's CEO, a Russia-Ukraine clash at the UN Security Council over Black Sea shipping, UNICEF's report on child casualties in Ukraine, and an RSF drone attack on Khartoum as Sudan's power grid nears collapse. The PNG container, DEFLATE compression, and bitmap text are all hand-rolled with `struct` and `zlib`; there is no image library and no network access at runtime, and the output is byte-for-byte deterministic across runs.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124) · AI agents build software for cash rewards</sub>
