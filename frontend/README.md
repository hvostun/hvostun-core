# Future user frontend

`frontend/` is an inactive React/Vite template reserved for a future
user-facing Hvostun interface.

It is intentionally outside the current admin MVP:

- it is not built or served by FastAPI;
- it is not included in Docker Compose or the backend image;
- backend does not enable CORS for it;
- its generated client and template routes are not guaranteed to match the
  current API;
- frontend checks are not part of the current release process.

The active UI is the Jinja + Bootstrap admin in `backend/app/admin`.

When work on the user interface starts, define its API and authorization
contract first. Only then enable CORS for explicit origins, regenerate the
OpenAPI client, add a separate frontend service/build, and introduce frontend
tests and deployment checks.
