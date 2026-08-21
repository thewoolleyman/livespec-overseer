# Third-party notices

This project vendors the following third-party libraries into
`overseer/_vendor/`. Each library's `LICENSE` file is preserved alongside
its source at `overseer/_vendor/<name>/LICENSE`.

The `.claude-plugin/overseer/` carrier is a byte-identical mirror of the
runtime package, so it carries the same vendored tree under
`.claude-plugin/overseer/_vendor/` for its disjoint plugin execution context.

---

## `returns`

- **Upstream:** dry-python/returns (https://github.com/dry-python/returns)
- **License:** BSD-3-Clause
- **Verbatim license file:** `overseer/_vendor/returns/LICENSE`

ROP primitives: `Result`, `IOResult`, `bind`, `map`, `Success`, `Failure`.

---

## `typing_extensions`

- **Upstream:** python/typing_extensions
  (https://github.com/python/typing_extensions)
- **License:** Python Software Foundation License (PSF-2.0)
- **Verbatim license file:** `overseer/_vendor/typing_extensions/LICENSE`

Python typing-system backports. Vendored full upstream verbatim at tag
`4.12.2` because core `returns` modules import `typing_extensions` at
module load.
