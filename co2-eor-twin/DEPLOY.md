# Deploying CO2-EOR Digital Twin to Your Workspace

## Prerequisites

- Databricks CLI installed and configured
- A Databricks workspace with **Apps** enabled

## Quick Deploy

### 1. Clone the repo

```bash
git clone https://github.com/Reishin-DB/co2-eor-twin.git
cd co2-eor-twin
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
databricks apps create co2-eor-twin --description "CO2-EOR Digital Twin" --profile=YOUR-PROFILE
databricks apps deploy co2-eor-twin --source-code-path /Workspace/Users/<your-email>/co2-eor-twin --profile=YOUR-PROFILE
```

### 4. Open the app

The deploy command prints the app URL.
