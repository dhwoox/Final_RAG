
# Skill: G-SDK Test Case Retriever

## Description
This skill retrieves detailed information for a specific G-SDK test case from a local ChromaDB vectorstore. It takes a test case identifier string and returns the full details of the test case, which can then be used to plan and generate automation code.

## Usage
- Call `get_test_case_details(test_case_id)` with a string identifying the test case, such as "COMMONR-30 step 4".
- The function will parse the ID, query the database, and return a JSON string containing the test case content and metadata.

## Example

### Example Call
`get_test_case_details(test_case_id="COMMONR-30 step 4")`

### Example Output (JSON String)
```json
[
  {
    "content": "Master 디바이스에서 지문+PIN 복합 인증 테스트... (후략)",
    "metadata": {
      "issue_key": "COMMONR-30",
      "step_index": "4",
      "number": null
    }
  }
]
```
