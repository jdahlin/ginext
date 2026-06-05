# GitLab Agent Setup

This note describes the simplest way to run Codex-driven project work from
GitLab issues and merge requests without paying for GitLab Duo Agent Platform or
other GitLab AI seats. The goal is to keep costs limited to the existing agent
provider account/API usage and normal GitLab runner or host compute.

## Scope

Build a small GitLab webhook bot, not a platform.

The bot should support:

- starting work from issue or merge request comments;
- pushing an agent branch;
- opening or updating a draft merge request;
- posting status back to GitLab;
- pausing for clarification through GitLab comments;
- resuming from the existing branch after a user answer.

The first version should not support automatic merge, parallel task routing,
multi-agent delegation, or broad project management automation.

## Components

Use four small pieces:

- GitLab bot identity: a bot user, project access token, or group access token.
- Webhook receiver: a small service that receives GitLab issue, merge request,
  and note events.
- Worker runner: a local clone/worktree runner that invokes Codex in a
  non-interactive mode.
- State store: SQLite is enough for task status, branch names, and transcripts.

The bot token should be able to read the repository, push branches, create merge
requests, and comment on issues/MRs. It should not be allowed to merge.

## Suggested Stack

Python is sufficient:

- `fastapi`
- `uvicorn`
- `python-gitlab`
- `sqlite3`
- subprocess calls to `git` and `codex`

Keep `glab` available on the host if it makes MR and comment operations simpler,
but do not require it for the core path if the REST API is already used.

## GitLab Webhooks

Configure project or group webhooks for:

- issue events;
- merge request events;
- note/comment events.

The first MVP can listen only to note/comment events and only act when a comment
contains an explicit bot command.

Example commands:

```text
@codex implement
@codex review
@codex address review
@codex continue
@codex answer: preserve PyGObject compatibility and add a regression test
```

## Minimal Task Flow

For an issue comment like:

```text
@codex implement
```

The bot should:

1. Verify the webhook signature/token.
2. Fetch the issue body, title, labels, and recent comments.
3. Clone or fetch the project into a temporary worktree.
4. Create a branch like `codex/issue-123-short-title`.
5. Run Codex with the issue context and project rules.
6. If Codex changed files, commit and push the branch.
7. Open a draft merge request linked to the issue.
8. Comment on the issue with the MR link, summary, and tests run.

For an MR review command, the bot should instead check out the MR source branch
and include unresolved review discussions in the Codex prompt.

## Clarification Workflow

Agent clarification is supported by treating "needs input" as a durable task
state, not as a failed run.

Codex should be instructed to emit a machine-detectable marker when it is
blocked:

```text
AGENT_NEEDS_INPUT:
1. Should this preserve PyGObject compatibility?
2. Should the regression test live under pygobject or ginext?
```

When the wrapper sees `AGENT_NEEDS_INPUT:`, it should:

1. Stop the run without committing speculative changes.
2. Post the questions as a GitLab comment.
3. Add a label such as `agent:needs-input`.
4. Store the transcript, branch, and pending question comment ID in SQLite.

When the user replies:

```text
@codex answer: preserve PyGObject compatibility and put the regression under
pygobject.
```

The bot should:

1. Load the prior task state.
2. Check out the same branch.
3. Remove `agent:needs-input` and add `agent:working`.
4. Run Codex with the original issue/MR context, prior transcript summary, and
   the new answer.
5. Continue the normal branch/MR update flow.

Prefer stateless resume by transcript over keeping long-running Codex processes
alive. Branches, comments, and SQLite state are the durable record.

## State Store

A minimal SQLite task record:

```sql
CREATE TABLE agent_tasks (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL,
  issue_iid INTEGER,
  merge_request_iid INTEGER,
  branch TEXT NOT NULL,
  status TEXT NOT NULL,
  transcript TEXT,
  pending_question_note_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

Useful statuses:

- `working`
- `needs_input`
- `ready`
- `failed`

Use GitLab labels with matching names where possible:

- `agent:working`
- `agent:needs-input`
- `agent:ready`
- `agent:failed`

## Prompt Template

The wrapper should pass Codex a prompt shaped like:

```text
You are working in a GitLab-driven coding workflow.

Project: {project_path}
Issue: #{issue_iid} {title}

Issue body:
{description}

Recent comments:
{comments}

Rules:
- Make the requested code changes.
- Add focused tests when appropriate.
- Commit changes to the current branch.
- Do not merge.
- If blocked, stop and output exactly:

AGENT_NEEDS_INPUT:
<questions>

- Otherwise output:

AGENT_DONE:
<summary>
<tests run>
```

For MR review work, include:

- MR title and description;
- changed files or diff summary;
- unresolved review discussions;
- recent CI failures and job logs if available.

## Safety Rules

Keep the first implementation conservative:

- require explicit `@codex` commands;
- ignore comments from the bot itself;
- allow only one active run per issue/MR;
- require protected branch and approval rules for merging;
- never run automatic merge;
- restrict the bot token to the smallest practical scope;
- run each task in a fresh worktree;
- cap runtime and output size;
- post failure summaries back to GitLab.


## Deployment Model

Yes, deploy the bot through GitLab while still running it locally in a container.
Keep the runtime simple:

- GitLab CI builds the bot container image.
- GitLab Container Registry stores the image.
- A local host pulls and runs the image with Docker Compose.
- GitLab webhooks reach the local host through either a reverse proxy, VPN, or a
  temporary tunnel such as ngrok/cloudflared during early testing.

This keeps GitLab as the delivery mechanism without requiring GitLab Duo or a
hosted agent platform.

## Local Container Runtime

A minimal `compose.yaml` for the bot host should look like this:

```yaml
services:
  gitlab-agent-bot:
    image: registry.gitlab.com/example/group/project/gitlab-agent-bot:latest
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
      - ./work:/work
      - ~/.codex:/home/bot/.codex:ro
    environment:
      GITLAB_URL: https://gitlab.com
      GITLAB_TOKEN_FILE: /run/secrets/gitlab_token
      GITLAB_WEBHOOK_SECRET_FILE: /run/secrets/webhook_secret
      AGENT_DATA_DIR: /data
      AGENT_WORK_DIR: /work
    secrets:
      - gitlab_token
      - webhook_secret

secrets:
  gitlab_token:
    file: ./secrets/gitlab_token
  webhook_secret:
    file: ./secrets/webhook_secret
```

Use persistent host directories for:

- `/data`: SQLite database and task metadata;
- `/work`: temporary clones/worktrees;
- Codex configuration or credentials, mounted read-only if needed.

Do not bake provider credentials or GitLab tokens into the image.

## GitLab CI Image Build

The project can build and publish the bot image with a small `.gitlab-ci.yml`
job:

```yaml
stages:
  - build

build-agent-bot:
  stage: build
  image: docker:27
  services:
    - docker:27-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
  script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
    - docker build -t "$CI_REGISTRY_IMAGE/gitlab-agent-bot:$CI_COMMIT_SHA" -t "$CI_REGISTRY_IMAGE/gitlab-agent-bot:latest" agent-bot
    - docker push "$CI_REGISTRY_IMAGE/gitlab-agent-bot:$CI_COMMIT_SHA"
    - docker push "$CI_REGISTRY_IMAGE/gitlab-agent-bot:latest"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

For the MVP, manual deployment is enough:

```sh
docker login registry.gitlab.com
docker compose pull
docker compose up -d
```

Later, add a deploy job that SSHes into the local host and runs those commands,
but keep that separate from the first working version.

## Webhook Exposure

For early testing, expose the local container with a tunnel:

```sh
ngrok http 8080
```

or:

```sh
cloudflared tunnel --url http://localhost:8080
```

Use the tunnel URL as the GitLab webhook URL. Configure a shared webhook secret
and verify the `X-Gitlab-Token` header before doing any work.

For long-term use, prefer one of:

- a reverse proxy with TLS on a host you control;
- Tailscale/WireGuard plus a small public relay;
- a cloud VM that only runs the webhook receiver and dispatches jobs to the
  local worker.

## Deployment Boundaries

GitLab should deploy the bot image, but the bot itself should create work
branches and merge requests in the target repositories. Keep these concerns
separate:

- CI pipeline: build and publish the bot image.
- Local container: receive webhooks and run Codex jobs.
- GitLab bot token: push branches, create MRs, and comment.
- Human reviewers: approve and merge.

The bot should never update itself in response to ordinary `@codex` commands.
Only normal GitLab CI on the bot repository should publish new bot images.

## MVP Checklist

Start with the smallest useful loop:

1. Create a GitLab bot token.
2. Implement a webhook endpoint for note events.
3. Parse `@codex implement`.
4. Fetch issue context.
5. Clone/fetch the repository.
6. Create a `codex/issue-*` branch.
7. Run Codex non-interactively.
8. Push the branch.
9. Open a draft MR.
10. Post the MR link back to the issue.

Then add:

- clarification/resume;
- `@codex address review`;
- CI failure context;
- labels;
- retry handling;
- stale-task cleanup.
