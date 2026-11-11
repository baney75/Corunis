# Select models in Corunis

> **Status: planned, not released.** Corunis has no release yet, so there is nothing to install today. These steps are the target behavior. Each one becomes true only when its test in [TESTING.md](https://github.com/baney75/Corunis/blob/main/TESTING.md) passes, and [SUPPORTED.md](https://github.com/baney75/Corunis/blob/main/SUPPORTED.md) is the source of truth for what works now. An agent must check SUPPORTED.md first and tell the person plainly if a step isn't supported yet.

You pick models inside Corunis. Fonsviva downloads, stores and serves them.

## Steps

1. In Corunis, open **Settings → Models**. It lists models on your connected machines that passed Corunis's tests on that hardware (see [BENCHMARKS](https://github.com/baney75/Corunis/blob/main/BENCHMARKS.md)).
2. Pick one for each task, or choose **Install** on a recommended model. Corunis asks Fonsviva to download it and shows progress.

## Check

- `fonsviva models list --app corunis` shows the selected models as `in use by corunis`.
- Corunis shows the model as ready. Models without a passing result for this hardware are marked "not tested here" and are not used for real work.
