# Add a cloud provider

> **Status: planned, not released.** UniCerebrum has no release yet, so there is nothing to install today. These steps are the target behavior. Each one becomes true only when its test in [TESTING.md](https://github.com/baney75/UniCerebrum/blob/main/TESTING.md) passes, and [SUPPORTED.md](https://github.com/baney75/UniCerebrum/blob/main/SUPPORTED.md) is the source of truth for what works now. An agent must check SUPPORTED.md first and tell the person plainly if a step isn't supported yet.

UniCerebrum has no cloud settings. Cloud providers such as RunPod are added and turned on **only in Fonsviva**, for personal use only. Follow [Fonsviva: add a cloud provider](https://baney75.github.io/Fonsviva/setup/add-cloud-provider) and the [vetted provider list](https://baney75.github.io/Fonsviva/providers).

## What this means for UniCerebrum

UniCerebrum jobs use the `unicerebrum` profile, which Fonsviva always blocks from cloud (FERPA). There is no cloud option and no override.

## Check

- UniCerebrum's job view labels every job with where it ran.
- UniCerebrum never asks for a provider key.
