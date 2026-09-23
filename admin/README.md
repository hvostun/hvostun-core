# Hvostun — Admin UI

The admin UI is built with [Vite](https://vitejs.dev/), [React](https://react.dev/), [TypeScript](https://www.typescriptlang.org/), [TanStack Query](https://tanstack.com/query), [TanStack Router](https://tanstack.com/router), [Tailwind CSS](https://tailwindcss.com/), and [shadcn/ui](https://ui.shadcn.com/).

The user-facing service UI will live in `web/`, not here.

## Requirements

- [Bun](https://bun.sh/)

## Quick Start

From the project root, install the dependencies and start the admin development server:

```bash
bun install
bun run dev
```

Then open <http://localhost:5173/> in your browser.

Run `uv run bash scripts/prestart.sh` and `uv run fastapi dev` from the `backend` directory, with PostgreSQL running in Docker Compose. See [../development.md](../development.md) for the complete setup.

To serve the admin UI with FastAPI, run `bun run build` from the `admin` directory and open `http://localhost:8000`.

Check `admin/package.json` to see the other available commands.

## Generate Client

### Automatically

* From the project root, run the script:

```bash
bash ./scripts/generate-client.sh
```

* Commit the changes.

### Manually

* Make sure the backend is running.

* Download the OpenAPI JSON file from `http://localhost:8000/api/v1/openapi.json` and copy it to a new file `openapi.json` at the root of the `admin` directory.

* To generate the admin client, run:

```bash
bun run generate-client
```

* Commit the changes.

Regenerate the client whenever backend changes affect the OpenAPI schema.

## Using a Remote API

By default, the built admin UI uses the same origin as the FastAPI app. If you want to use a remote API while running the Vite development server, you can set the environment variable `VITE_API_URL` to the URL of the remote API. For example, you can set it in the `admin/.env` file:

```env
VITE_API_URL=https://my-domain.example.com
```

Then, when you run the admin UI, it will use that URL as the base URL for the API.

## Code Structure

* `admin/src` - The main admin UI code.
* `admin/public` - Static assets.
* `admin/src/client` - The generated OpenAPI client.
* `admin/src/components` - Components, including shadcn/ui in `admin/src/components/ui`.
* `admin/src/hooks` - Custom hooks.
* `admin/src/lib` - Shared utilities.
* `admin/src/routes` - Routes and pages.
