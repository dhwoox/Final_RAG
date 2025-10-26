
# Skill Textbook: G-SDK Event Verification

## Goal
To verify that a specific action in a test correctly triggers an expected event.

## Learning Source
**Study the source code in `functions.py` of this skill.**

- The file `functions.py` contains a clear, well-commented example function: `verify_event_example()`.
- This function is your primary learning material. Read its source code to understand the correct pattern for:
  - Using the `EventMonitor` class with a `with` statement.
  - Setting the correct parameters (`svcManager`, `masterID`, `eventCode`, `userID`).
  - Placing the action code that triggers the event in the correct location.
  - Calling the `monitor.caught()` method to wait for and check the event.
  - Asserting the result.

## Your Task
When you need to verify an event, do not call the function in this skill. Instead, **replicate the pattern you learn from its source code**. You must determine the correct `eventCode` by studying the `event_codes.json` file (provided as context by the agent) and generate a new `with EventMonitor(...)` block that fits the specific requirements of the test case.
