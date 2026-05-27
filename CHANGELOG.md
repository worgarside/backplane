# CHANGELOG

<!-- version list -->

## v0.4.0 (2026-05-27)

### Bug Fixes

- Use explicit LOCAL_TIMEZONE setting instead of system timezone
  ([#19](https://github.com/worgarside/backplane/pull/19),
  [`d23c7f8`](https://github.com/worgarside/backplane/commit/d23c7f87cee001d47a17b94a6828797bd2c9e97e))

### Chores

- **deps**: Bump idna from 3.13 to 3.15 ([#22](https://github.com/worgarside/backplane/pull/22),
  [`4032f19`](https://github.com/worgarside/backplane/commit/4032f19dfd33c5ffeae3494b8e7ea9122cc2bf0d))

- **deps**: Bump pydantic-ai from 1.97.0 to 1.99.0
  ([#26](https://github.com/worgarside/backplane/pull/26),
  [`e02a867`](https://github.com/worgarside/backplane/commit/e02a867de29f0c42970961f768b10651bf753a4d))

### Code Style

- Fixes from prek hooks
  ([`7c447d2`](https://github.com/worgarside/backplane/commit/7c447d2fd0067689271473eb5c52d7c28ff8456f))

### Continuous Integration

- Prek autoupdate ([#29](https://github.com/worgarside/backplane/pull/29),
  [`a564d74`](https://github.com/worgarside/backplane/commit/a564d74cd17bd300dca39c47821f248c74b247a2))

- Prek autoupdate ([#20](https://github.com/worgarside/backplane/pull/20),
  [`790d264`](https://github.com/worgarside/backplane/commit/790d2646b2882209491828ed44566ce205b2462f))

### Features

- Add due dates to Kanban cards ([#23](https://github.com/worgarside/backplane/pull/23),
  [`b5c4454`](https://github.com/worgarside/backplane/commit/b5c44546112bcfb12060ac1c443bced1df721c7e))

- Add helper utilities ([#21](https://github.com/worgarside/backplane/pull/21),
  [`2c5514b`](https://github.com/worgarside/backplane/commit/2c5514b2113bb549f7cdd0c6ced023ce79c4e5e4))

- Dynamic startup notification title ([#18](https://github.com/worgarside/backplane/pull/18),
  [`0c0deda`](https://github.com/worgarside/backplane/commit/0c0dedac8ab112394ca8080b15b70f21978bf096))

- Introduce custom exception handling ([#25](https://github.com/worgarside/backplane/pull/25),
  [`bbd5d4c`](https://github.com/worgarside/backplane/commit/bbd5d4c5c8064fb86216ed16d07daddd80b25a4d))

- Support task creation from voice input ([#28](https://github.com/worgarside/backplane/pull/28),
  [`95041ba`](https://github.com/worgarside/backplane/commit/95041ba1d424148ac03bcd42a12e822df18c8983))

### Refactoring

- Use atomic writes for markdown files ([#24](https://github.com/worgarside/backplane/pull/24),
  [`bff7ac9`](https://github.com/worgarside/backplane/commit/bff7ac929f1d1a1d027df19ad30ff825ae15381b))


## v0.3.0 (2026-05-17)

### Chores

- Add logging for server and obsidian functions
  ([#16](https://github.com/worgarside/backplane/pull/16),
  [`25c0cb8`](https://github.com/worgarside/backplane/commit/25c0cb8f3792f44fa6cd37b972bcf481cf3ba5e3))

### Features

- Integrate Home Assistant for MCP auto-reload
  ([#15](https://github.com/worgarside/backplane/pull/15),
  [`b6f6206`](https://github.com/worgarside/backplane/commit/b6f62061fca260748ad9fb6d7d4dc137a5d7a683))

### Performance Improvements

- Enhance event loop with uvloop ([#17](https://github.com/worgarside/backplane/pull/17),
  [`d33f88f`](https://github.com/worgarside/backplane/commit/d33f88fb22bd9efd6268245f2202e3b065a08243))


## v0.2.1 (2026-05-17)

### Continuous Integration

- Add build command for package updates ([#14](https://github.com/worgarside/backplane/pull/14),
  [`d54f4a7`](https://github.com/worgarside/backplane/commit/d54f4a7733b711ebe45d3c8a06e7137ea41494ce))

- Change deploy env ([#13](https://github.com/worgarside/backplane/pull/13),
  [`b0e3df8`](https://github.com/worgarside/backplane/commit/b0e3df81a3266b462652df65286bd3a49ba22bec))


## v0.2.0 (2026-05-17)

### Bug Fixes

- Replace UTC timezone with local timezone ([#9](https://github.com/worgarside/backplane/pull/9),
  [`1b1ddfa`](https://github.com/worgarside/backplane/commit/1b1ddfa0e7ca272178ca0df8da3a7abfb5056be4))

### Continuous Integration

- Add automated deployment step to CI workflow
  ([#11](https://github.com/worgarside/backplane/pull/11),
  [`258669c`](https://github.com/worgarside/backplane/commit/258669c2a00f39790e627bcb3a8882bbebb6cea8))

- Exclude init file from release triggers ([#6](https://github.com/worgarside/backplane/pull/6),
  [`c9372d5`](https://github.com/worgarside/backplane/commit/c9372d5b22ef8973772a8cf0c98de302c1f9f81d))

- Exclude main branch from PR workflow ([#12](https://github.com/worgarside/backplane/pull/12),
  [`5d48531`](https://github.com/worgarside/backplane/commit/5d48531b7e558b076a7bccb3bdc6e12c395929f9))

- Prek autoupdate ([#8](https://github.com/worgarside/backplane/pull/8),
  [`e376591`](https://github.com/worgarside/backplane/commit/e3765914a04c911a6f4bdce5947056857c8f3479))

### Features

- Add idea recording to Obsidian ([#7](https://github.com/worgarside/backplane/pull/7),
  [`aa5ca9d`](https://github.com/worgarside/backplane/commit/aa5ca9dca26d4a0817f5ab003ae0be0cfeb7c09b))


## v0.1.0 (2026-05-16)

- Initial Release
