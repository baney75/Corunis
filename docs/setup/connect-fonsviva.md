# Connect UniCerebrum to Fonsviva

> **Status: planned, not released.** UniCerebrum has no release yet, so there is nothing to install today. These steps are the target behavior. Each one becomes true only when its test in [TESTING.md](https://github.com/baney75/UniCerebrum/blob/main/TESTING.md) passes, and [SUPPORTED.md](https://github.com/baney75/UniCerebrum/blob/main/SUPPORTED.md) is the source of truth for what works now. An agent must check SUPPORTED.md first and tell the person plainly if a step isn't supported yet.

UniCerebrum doesn't run models itself. It connects to [Fonsviva](https://baney75.github.io/Fonsviva/).

## Steps

1. Make sure Fonsviva is running: `fonsviva status`.
2. In UniCerebrum, open **Settings → Connect to Fonsviva** and choose **Connect**. UniCerebrum sends a connection request.
3. Approve it in Fonsviva's web app under **Connect**, or run `fonsviva keys approve unicerebrum`.

## Check

- `fonsviva keys list` shows `unicerebrum` as `active`.
- UniCerebrum shows "Connected to Fonsviva" with the machines and models it can use.
- Every job in UniCerebrum shows where it ran.

Fonsviva on another machine: enter its address (for example a Tailscale name) in the Connect screen instead.
