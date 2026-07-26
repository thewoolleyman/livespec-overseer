# Changelog

## [0.12.4](https://github.com/thewoolleyman/livespec-overseer/compare/v0.12.3...v0.12.4) (2026-07-26)


### Bug Fixes

* **overseer:** delete the loop-iteration broad catch; let a tick bug crash ([878fc6e](https://github.com/thewoolleyman/livespec-overseer/commit/878fc6e2aafc55f9730cd0fd7ef91f5d885761ea))

## [0.12.3](https://github.com/thewoolleyman/livespec-overseer/compare/v0.12.2...v0.12.3) (2026-07-26)


### Bug Fixes

* **overseer:** bound both subprocess calls with a timeout ([cee8c83](https://github.com/thewoolleyman/livespec-overseer/commit/cee8c83d87951480642493e2ebe28fc680ad9748))


### Refactoring

* **tests:** split test_codex_sessions into join and mapping halves ([46b3112](https://github.com/thewoolleyman/livespec-overseer/commit/46b3112d13f24c4cea67d84642616f1c594d94f0))
* **tests:** split test_tmuxio into reads and writes ([b3ffbb0](https://github.com/thewoolleyman/livespec-overseer/commit/b3ffbb002d1fa91501e7aa589f42e6e9e09c5fdc))

## [0.12.2](https://github.com/thewoolleyman/livespec-overseer/compare/v0.12.1...v0.12.2) (2026-07-26)


### Bug Fixes

* **supervise-plan:** the generated charter prohibits killing the acting daemon ([adff90a](https://github.com/thewoolleyman/livespec-overseer/commit/adff90ad6ecb99fb88219631e56afcae6bd5e7f8))

## [0.12.1](https://github.com/thewoolleyman/livespec-overseer/compare/v0.12.0...v0.12.1) (2026-07-26)


### Bug Fixes

* **overseer:** close six UnicodeDecodeError boundary leaks ([236209c](https://github.com/thewoolleyman/livespec-overseer/commit/236209c60ccdd76722d797236c2e6bd52612a43e))

## [0.12.0](https://github.com/thewoolleyman/livespec-overseer/compare/v0.11.0...v0.12.0) (2026-07-26)


### Features

* add supervise-plan plugin skill ([d126ccf](https://github.com/thewoolleyman/livespec-overseer/commit/d126ccff79f68c054d08b92949286387fcce7d08))
* pin public overseer entry points ([5ddcfee](https://github.com/thewoolleyman/livespec-overseer/commit/5ddcfee451eb61f4f541de8469ee08623fd71c39))
* pin supervision offer surfaces ([5d879e6](https://github.com/thewoolleyman/livespec-overseer/commit/5d879e6d63082c6b1aad35afe1f7ea75aa7c16ad))
* **plugin:** scaffold overseer operator plugin ([695518e](https://github.com/thewoolleyman/livespec-overseer/commit/695518e8077f193fa8e5551a60e12b4e5a25ff11))
* **release:** plugin.json tracks the package version (overseer-hbr.10) ([9c3d844](https://github.com/thewoolleyman/livespec-overseer/commit/9c3d8446722b5fe23bb048cf057093fdd310bcc0))
* **release:** the release-branch, readiness and tag workflows ([4b4cb2d](https://github.com/thewoolleyman/livespec-overseer/commit/4b4cb2d7cac1c6d9f64efa19d27adad1cc008ac8))
* render pinned overseer version ([6421590](https://github.com/thewoolleyman/livespec-overseer/commit/6421590400287938d91e9984cd89c00588bbdb20))


### Bug Fixes

* **overseer:** the wrap-up no longer claims a gate size that is false here ([f22e3c7](https://github.com/thewoolleyman/livespec-overseer/commit/f22e3c7113017e1e11799cd72868a25726b5ab31))
* pin malformed state alert edge trigger ([9b002e3](https://github.com/thewoolleyman/livespec-overseer/commit/9b002e3a4d788e58bac40ec12606de37c61be394))
* preserve daemon log history ([56f4220](https://github.com/thewoolleyman/livespec-overseer/commit/56f4220450af71a4ab0830616247e7ca49749bf0))
* repoint overseer-start bootstrap ([f13be76](https://github.com/thewoolleyman/livespec-overseer/commit/f13be76f63ba101e4881691f5136a61f7f047ec4))
* route ci telemetry span batch off argv ([f7e5e73](https://github.com/thewoolleyman/livespec-overseer/commit/f7e5e7312d1cbe9fed361ee808886c90bba4ef4f))
