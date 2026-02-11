# Changelog

All notable changes to Memorable are documented in this file.

## 0.1.0 - 2026-02-11

Initial release candidate with core local-memory workflow and reliability hardening.

### Added

- End-to-end smoke test covering core API flow (`tests/test_e2e_smoke.py`)
- Import/export/reset data integrity tests, including rollback-on-failure coverage (`tests/test_data_integrity.py`)
- Installer integration tests for fresh install and idempotent hook merge behavior (`tests/test_install_script.py`)
- Daemon reliability signals in `/api/status`:
  - enabled/running/pid
  - note/transcript recency
  - lag metrics and issue/action codes
- Dashboard and Settings daemon health UI indicators and recovery actions
- Memory effectiveness panel in Memories/Episodic view
- Session drilldown from effectiveness rows into note filtering
- One-click reset for Session Notes filters

### Changed

- Clarified seed workflow with explicit Draft vs Deployed state
- Improved first-run setup guidance for daemon enablement and first note capture
- Unified memory IA labels and helper copy in UI/README
- Improved empty/error states in Memories and Settings with guided next actions
- Updated installer hook merge logic to replace stale Memorable paths from prior installs

### Fixed

- Hardened POST body/content validation to avoid 500s on malformed types
- Rejected negative `Content-Length` in HTTP/API body handlers
- Clamped negative notes pagination inputs (`offset`, `limit`)
- Excluded internal artifacts (`.anchored`, `.cache-*`) from status file counts
- Multiple endpoint/schema resiliency fixes from bug sweep tickets
- Added strict schema/type/range validation for `POST /api/settings` payloads
- Anchor processor now enforces canonical config schema/path (`~/.memorable/data/config.json` with `llm_provider`)
- Added regression tests to prevent external font/CDN requests in the local UI
