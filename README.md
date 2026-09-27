# FAYOUM SCAN RIS

Central LAN/server edition for Fayoum Scan RIS.

Current development: Phase 5.

- Central server database
- LAN multi-device access
- Patients and appointments
- Contract/payment price plans
- Excel price-plan import/export
- Users and audit log
- Backup/restore
- Windows x64 build via GitHub Actions

> Development repository. Keep production backups outside the repository.


## Phase 5 Beta status
- Windows x64 portable server build via GitHub Actions
- Central SQLite LAN database with automatic schema upgrades
- Patients, appointments and workflow statuses
- Entity price plans with native XLSX import/export
- Paid / remaining / payment method tracking
- Financial dashboard and printable daily report
- Users, configurable permissions and server-side enforcement
- Audit log, backup and integrity-checked restore
- REV.7 migration page
- Patient history lookup by phone
- Live connection status and 15-second refresh

### Beta gate
Do not merge to main until the latest Windows x64 workflow is green and smoke tests cover login, patient create/edit, appointment workflow, pricing, XLSX, backup/restore and permissions.
