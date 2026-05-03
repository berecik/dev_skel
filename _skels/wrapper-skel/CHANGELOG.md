# Changelog

All notable changes to `wrapper-skel` will be documented in this file.

## [0.1.0] - 2026-05-02

### Added

- Initial release. The wrapper-skel template lays down the project
  basement (shared `.env`, `_shared/`, dispatch scripts, dev/prod
  helpers, `dev_skel.project.yml`) without requiring a service.
- Service skels (`go-skel`, `python-fastapi-skel`, etc.) can be
  overlaid into a wrapper-only project with the existing
  `make gen-<skel> NAME=<existing-wrapper>` flow.
