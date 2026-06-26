# Postman onboarding for this repository

This repository is already set up as a local Postman workspace.

## What Postman will use here

Postman stores API artifacts in the `postman/` folder:

- `postman/collections/` — your collections and requests
- `postman/environments/` — your environments
- `postman/globals/workspace.globals.yaml` — workspace-level variables
- `postman/mocks/` — local mock servers
- `postman/flows/` — flows
- `postman/specs/` — API specifications

Right now this repo has the Postman structure, but no collections or environments yet.

## What this app exposes

From the code and docs, the backend API has three main HTTP endpoints:

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/tickets` | Create a ticket and analyze sentiment |
| GET | `/tickets` | List saved tickets |

Backend implementation is in `backend/app/main.py`.

## Useful base URLs

You can call this app in two common ways:

1. **Backend directly**
   - Base URL: `http://localhost:8000`
   - Best for direct API testing

2. **Through the frontend proxy**
   - Base URL: `http://localhost:3000/api`
   - Best for testing the same route shape the browser uses

## Recommended first Postman setup

Create one collection named **Ticket Analyzer** with these requests:

1. **Health Check**
   - `GET {{baseUrl}}/health`

2. **Create Ticket**
   - `POST {{baseUrl}}/tickets`
   - Header: `Content-Type: application/json`
   - Body:

```json
{
  "title": "Lab VM issue",
  "message": "My lab VM is not opening before the deadline.",
  "category": "lab"
}
```

3. **List Tickets**
   - `GET {{baseUrl}}/tickets`

## Recommended environment

Create an environment such as **local** with:

- `baseUrl = http://localhost:8000`

You can later switch it to `http://localhost:3000/api` if you want to test through Nginx.

## Suggested beginner workflow in Postman

1. Start the app with Docker Compose.
2. Create the `local` environment with `baseUrl`.
3. Create the **Health Check** request and send it.
4. Create **Create Ticket** and send a sample JSON body.
5. Create **List Tickets** and confirm the saved ticket appears.
6. Group all three requests into the **Ticket Analyzer** collection.

## Good first tests to add

### Health Check test

```javascript
pm.test("status is 200", function () {
  pm.response.to.have.status(200);
});

pm.test("health response is ok", function () {
  const data = pm.response.json();
  pm.expect(data.status).to.eql("ok");
});
```

### Create Ticket test

```javascript
pm.test("status is 201", function () {
  pm.response.to.have.status(201);
});

pm.test("ticket has sentiment fields", function () {
  const data = pm.response.json();
  pm.expect(data).to.have.property("sentiment");
  pm.expect(data).to.have.property("confidence");
});
```

## Where these endpoints come from

- Request code pattern in the frontend: `frontend/src/api.js`
- API handlers: `backend/app/main.py`
- Full architecture notes: `ARCHITECTURE.md`
- Project quick start: `README.md`

## Next things Postman can help with

After the basics, you can use Postman here to:

- add tests for ticket creation and history
- create examples for positive and negative tickets
- run the whole collection in sequence
- create a mock for the backend if the app is offline
- document the API for teammates directly in the repo
