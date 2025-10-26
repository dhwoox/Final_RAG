# Skill: G-SDK Test Planner

## Description
This skill analyzes a natural language test requirement in a two-step process to generate a structured test plan. The plan includes necessary G-SDK categories and a list of relevant APIs from `manager.py`.

## Usage

### Step 1: Get Categories
- Call `get_categories(query)` with a simple, descriptive query about the test goal.
- This function returns a JSON formatted list of relevant G-SDK categories.

**Example Call**:
`get_categories(query="fingerprint and PIN authentication test")`

**Example Output**:
`["auth", "event", "finger", "user"]`

### Step 2: Get APIs for Categories
- Take the JSON list from Step 1 and pass it to `get_apis_for_categories(categories_json)`.
- This function returns a JSON object where each category is mapped to a list of suggested APIs.

**Example Call**:
`get_apis_for_categories(categories_json='["auth", "event", "finger", "user"]')`

**Example Output**:
```json
{
  "auth": [
    "getAuthConfig",
    "isExtendedAuthSupported",
    "setAuthConfig"
  ],
  "event": [
    "getEventDescription",
    "getImageLog",
    "getImageLogFilter",
    "getJobCodeLog",
    "getLog",
    "getTNALog",
    "monitorLog",
    "setImageLogFilter",
    "subscribeLog"
  ],
  "finger": [
    "detectFingerprint",
    "getFingerprintConfig",
    "isFingerInputSupported",
    "scanFingerprint",
    "setFingerprintConfig",
    "verifyFingerprint"
  ],
  "user": [
    "enrollUsers",
    "getCards",
    "getUserStatistic",
    "getUsers",
    "hashPIN",
    "removeUsers",
    "updateUsers"
  ]
}
```