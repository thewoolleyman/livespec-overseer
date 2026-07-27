# Changelog

## [0.13.3](https://github.com/thewoolleyman/livespec-overseer/compare/v0.13.2...v0.13.3) (2026-07-27)


### Bug Fixes

* have release-please update uv.lock so it stops drifting behind pyproject ([5e4e091](https://github.com/thewoolleyman/livespec-overseer/commit/5e4e0916b0c2d9e8b8c54a389391daff1cf6f529))
* make the run_daemon double keyword-only, matching the function it stands in for ([c3f26d0](https://github.com/thewoolleyman/livespec-overseer/commit/c3f26d0efd64da988dbd7a7692ced655b9608c6c))
* **release:** carry the version literal in JSON so release-please rewrites no .py ([f8bb400](https://github.com/thewoolleyman/livespec-overseer/commit/f8bb40013f36b97e0746b309a3a8644edd76d3f5))


### Refactoring

* bring every file in the package under the 200 LLOC soft ceiling ([65a18c1](https://github.com/thewoolleyman/livespec-overseer/commit/65a18c161c7d297b3e12d2fbcbf3912ff07f563f))

## [0.13.2](https://github.com/thewoolleyman/livespec-overseer/compare/v0.13.1...v0.13.2) (2026-07-26)


### Refactoring

* convert the seams this repo owns to keyword-only Protocols ([1918f36](https://github.com/thewoolleyman/livespec-overseer/commit/1918f361d9d5767b7ce96d0562bf9546eec1ff0d))
* declare the annotated __all__ on every overseer module ([5312cfa](https://github.com/thewoolleyman/livespec-overseer/commit/5312cfa01d156e41926fccf3d8b1300b4505c27d))
* extract the evaluation group's collaborators from Supervisor ([d053f70](https://github.com/thewoolleyman/livespec-overseer/commit/d053f703e9a3797ba3bdc512e9df080173075932))
* make the production surface keyword-only ([80423ca](https://github.com/thewoolleyman/livespec-overseer/commit/80423cacd640dc573eab4122aba4ae1af488236f))
* make the test surface keyword-only ([a5b8dda](https://github.com/thewoolleyman/livespec-overseer/commit/a5b8ddab74dd8aa000ec0cf5c6200916efe9d370))
* make the tmux surface and its double keyword-only ([58f053e](https://github.com/thewoolleyman/livespec-overseer/commit/58f053ecbe28ba03da2b2f4c4fa9162403717d7b))
* move the decision cascade out, extracting only the R1 leg ([42ef479](https://github.com/thewoolleyman/livespec-overseer/commit/42ef4798ac79463e570823213a2bbc1c0e07a00f))
* split test_claude_sessions.py back under the 250 LLOC hard ceiling ([a88a39e](https://github.com/thewoolleyman/livespec-overseer/commit/a88a39e8a2d72730239b367daf5e3c90eb4b9547))

## [0.13.1](https://github.com/thewoolleyman/livespec-overseer/compare/v0.13.0...v0.13.1) (2026-07-26)


### Refactoring

* extract the launch, recovery and lifecycle groups ([6c1a9ee](https://github.com/thewoolleyman/livespec-overseer/commit/6c1a9ee013ca8d06484a27d54b9620b35a88e3d2))
* extract the table-rendering group into _supervisor_render ([80e6cf6](https://github.com/thewoolleyman/livespec-overseer/commit/80e6cf6c6c0d00ab407a11ae12b1e7612e7d4c2b))
* extract the watch-set + discovery group, rehome resolve_watch ([e83853a](https://github.com/thewoolleyman/livespec-overseer/commit/e83853a1d1a0e460b4d58b1f8ef7cec6fb899a92))
* make supervisor.py a facade over five private collaborators ([f279533](https://github.com/thewoolleyman/livespec-overseer/commit/f2795339adda800bc71ad75e98989fe30ffb13c3))
* publicise Supervisor's shared state and diagnostics surface ([b5d0cfe](https://github.com/thewoolleyman/livespec-overseer/commit/b5d0cfe1ba9160ffad1aca3f223dcc92fcf7129e))
* **tests:** take NoSupervisorPaneTmux off inheritance, and give its test teeth ([2e7bcdc](https://github.com/thewoolleyman/livespec-overseer/commit/2e7bcdc2197ab9087a7d4366a4735e4a72f270ca))

## [0.13.0](https://github.com/thewoolleyman/livespec-overseer/compare/v0.12.4...v0.13.0) (2026-07-26)


### Features

* **ci:** fan out published releases to the fleet manifest's adopters ([0b6c4d3](https://github.com/thewoolleyman/livespec-overseer/commit/0b6c4d3abdd007143d0689b6992e750a1ac03474))


### Bug Fixes

* **ci:** treat unauthorized adopter delivery as a precondition, not a failure ([3329bca](https://github.com/thewoolleyman/livespec-overseer/commit/3329bca5898245c8658fce1cf3ec51a26c4d80ce))


### Refactoring

* split registry into core, store, discovery and stamps modules ([522b8ad](https://github.com/thewoolleyman/livespec-overseer/commit/522b8ad6dca8058b5342b394343e90e74e69582d))
* **tests:** extract the supervisor beside-test doubles and builders ([74a0536](https://github.com/thewoolleyman/livespec-overseer/commit/74a0536c9ce094fe1b79d3ed374b34d30c7eec81))
* **tests:** split test_registry into store, resilience, discovery, injection ([b258e7b](https://github.com/thewoolleyman/livespec-overseer/commit/b258e7b0e0a5d3f1fca58b6df0700e18cc21dcd3))
* **tests:** split test_signals at the process-identity banner ([3922897](https://github.com/thewoolleyman/livespec-overseer/commit/39228972648bc24dfb244a01f52f6f101dc0b8da))
* **tests:** split test_supervisor into 24 topic modules ([394df70](https://github.com/thewoolleyman/livespec-overseer/commit/394df70b55f768543fe2993f8ef9f79b3293bf3c))

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
