# Deploying BOP Guardian to Your Workspace

## Prerequisites

- Databricks CLI installed (`databricks --version`)
- A Databricks workspace with **Apps** and **Foundation Model APIs** enabled
- A CLI profile configured for your workspace (`databricks configure --profile my-workspace`)

## Quick Deploy

### 1. Clone the repo

```bash
git clone https://github.com/databricks-industry-solutions/bop-guardian.git
cd bop-guardian
```

### 2. Update `databricks.yml` targets

Edit the `targets` section in `databricks.yml` to point to your workspace:

```yaml
targets:
  dev:
    mode: development
    default: true
    workspace:
      host: https://YOUR-WORKSPACE.cloud.databricks.com
      profile: YOUR-PROFILE
```

### 3. Deploy

```bash
# Upload source to workspace
databricks workspace import-dir ./app /Workspace/Users/<your-email>/bop-guardian/app --overwrite --profile=YOUR-PROFILE

# Upload app config
databricks workspace delete /Workspace/Users/<your-email>/bop-guardian/app.yaml --profile=YOUR-PROFILE 2>/dev/null
databricks workspace import /Workspace/Users/<your-email>/bop-guardian/app.yaml --file ./app.yaml --profile=YOUR-PROFILE

# Create and deploy the app
databricks apps create bop-guardian --description "BOP Guardian — Offshore BOP Monitoring Command Center" --profile=YOUR-PROFILE
databricks apps deploy bop-guardian --source-code-path /Workspace/Users/<your-email>/bop-guardian --profile=YOUR-PROFILE
```

### 4. Open the app

The deploy command prints the app URL. The app will:
- Auto-create the Lakebase database on first startup
- Connect to Foundation Model API for the Guardian Advisor chat
- Fall back to rule-based responses if FMAPI is unavailable

## Customization

Override resource names via `databricks.yml` variables:

```bash
databricks bundle deploy -t dev \
  --var="lakebase_instance=my-bop-db" \
  --var="lakebase_database=my_bop_app" \
  --var="llm_model=databricks-meta-llama-3-3-70b-instruct"
```
