# Deploying LAS Well Log Viewer to Your Workspace

## Prerequisites

- Databricks CLI installed and configured
- A Databricks workspace with **Apps** enabled
- **Foundation Model APIs** enabled (pay-per-token)

## Quick Deploy

### 1. Clone the repo

```bash
git clone https://github.com/Reishin-DB/las-viewer.git
cd las-viewer
```

### 2. Update `databricks.yml` targets

Edit the `targets` section to point to your workspace:

```yaml
targets:
  dev:
    workspace:
      host: https://YOUR-WORKSPACE.cloud.databricks.com
      profile: YOUR-PROFILE
```

### 3. Deploy

```bash
databricks apps create las-viewer --description "LAS Well Log Viewer" --profile=YOUR-PROFILE
databricks apps deploy las-viewer --source-code-path /Workspace/Users/<your-email>/las-viewer --profile=YOUR-PROFILE
```

### 4. Open the app

The deploy command prints the app URL.
The app will auto-create the Lakebase database on first startup.
The Guardian AI features require Foundation Model API access.
