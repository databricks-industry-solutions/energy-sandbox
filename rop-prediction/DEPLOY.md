# Deploying ROP Prediction to Your Workspace

## Prerequisites

- Databricks CLI installed and configured
- A Databricks workspace with **Apps** enabled

## Quick Deploy

### 1. Clone the repo

```bash
git clone https://github.com/Reishin-DB/rop-prediction.git
cd rop-prediction
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
databricks apps create rop-prediction --description "ROP Prediction" --profile=YOUR-PROFILE
databricks apps deploy rop-prediction --source-code-path /Workspace/Users/<your-email>/rop-prediction --profile=YOUR-PROFILE
```

### 4. Open the app

The deploy command prints the app URL.
The app will auto-create the Lakebase database on first startup.
