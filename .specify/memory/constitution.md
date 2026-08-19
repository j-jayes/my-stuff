<!--
Sync Impact Report
- Version change: (none) → 1.0.0
- Modified principles: none (initial ratification)
- Added sections: Core Principles (I–V), Technology & Cost Constraints,
  Development Workflow, Governance
- Removed sections: none
- Follow-up TODOs: none
-->

# My Stuff Constitution

## Core Principles

### I. Single User, No Ceremony

The application serves exactly one person on their own devices. Multi-tenancy, role-based
access control, sharing, invitations, and per-user data partitioning MUST NOT be built. A
single shared password gating a signed session cookie is the whole authentication story.
Rationale: every abstraction added for hypothetical other users is code that must be written,
tested, and maintained for a user base of one.

### II. Capture Must Be Frictionless On A Phone

Every data-entry path MUST be usable one-handed on a phone browser while standing in a room.
Adding an item MUST require no more than: open app → capture photo or paste link → confirm a
pre-filled form → save. Touch targets MUST be at least 44px. Desktop layouts are a widened
mobile layout, never a separate design. Rationale: an inventory app that is tedious on a phone
never gets filled in, and an empty inventory has zero value.

### III. AI Suggests, The User Decides

Model-extracted metadata MUST land in an editable form field, never directly in the database.
Every AI-populated field MUST be visibly marked as a suggestion and MUST be editable and
clearable before save. An AI call failing MUST degrade to a blank manual form, never block a
save. Rationale: wrong data written silently is worse than no data, and the user is always the
authority on their own possessions.

### IV. Test-First For Logic, Hands-On For Everything Else

Any non-trivial logic — schema constraints, scrapers, extraction parsing, canvas coordinate
persistence — MUST be covered by a test that was seen failing before the implementation
existed. UI and integration work MUST additionally be exercised by hand or by a browser
automation run against a real running instance before it is called done. Passing unit tests
alone are never sufficient evidence that a change works. Rationale: this repo's standing rule
is "execute before you claim"; a server that will not boot passes every unit test.

### V. Minimum Code That Does The Job

No feature beyond what the spec asks for. No abstraction for a single call site. No
configurability that was not requested. No error handling for scenarios that cannot occur.
When a change touches a file, unrelated code, comments, and formatting in that file MUST be
left alone. Rationale: this is a personal project maintained in spare time; every line is a
line someone has to re-read months later.

## Technology & Cost Constraints

Running cost at rest MUST be approximately zero, and cost is a design constraint of equal
standing to features.

- **Hosting**: One Cloud Run service, scale-to-zero, `max-instances=1`. No always-on VM, no
  load balancer, no Kubernetes.
- **Database**: SQLite, single file, replicated continuously to Google Cloud Storage via
  Litestream. Because `max-instances=1`, there is exactly one writer; any change that would
  introduce a second concurrent writer MUST be rejected.
- **Object storage**: Google Cloud Storage for item photos and receipts. Image bytes MUST NOT
  be stored in the database.
- **AI**: Gemini Flash-Lite class models via Vertex AI, called with a response schema so
  output is structured. Authentication is Application Default Credentials — API keys MUST NOT
  be committed or embedded.
- **Stack**: Python + FastAPI backend, Vite + React frontend, built into static assets served
  by the same FastAPI process. One deployable artifact, no CORS layer.
- **Secrets**: Secret Manager only. Secrets MUST NOT appear in the repository, in `.env` files
  that are committed, or in container images.

## Development Workflow

- **Reproducible local environment (NON-NEGOTIABLE)**: the backend MUST be developed against a
  project-local `.venv` managed by `uv`, and the full application MUST be runnable locally with
  a single `docker compose up`. The compose stack MUST use the same Dockerfile as the deployed
  image, so that "works locally" and "works on Cloud Run" mean the same thing.
- Deployment MUST be a single command against source, with no manual console steps. Any GCP
  resource the app depends on MUST be creatable from a scripted, re-runnable command.
- Specs, plans, and tasks live under `specs/` and are authored through the Spec Kit workflow
  before implementation begins.
- Work is committed in small, reviewed increments. Code is read by its author before it is
  proposed, and evidence of it running is included.

## Governance

This constitution supersedes ad-hoc preference during implementation. When a spec, plan, or
task conflicts with a principle here, the principle wins and the conflicting artifact is
amended.

- **Amendment procedure**: amendments are made by editing this file, recording the change in a
  Sync Impact Report comment at its head, and committing it separately from feature work.
- **Versioning policy**: semantic versioning. MAJOR for removing or redefining a principle in a
  backward-incompatible way, MINOR for adding a principle or materially expanding guidance,
  PATCH for clarifications and wording.
- **Compliance review**: every plan produced by `/speckit-plan` MUST state how it satisfies the
  Technology & Cost Constraints, and any deviation MUST be justified in writing in that plan or
  else abandoned.

**Version**: 1.0.0 | **Ratified**: 2026-08-19 | **Last Amended**: 2026-08-19
