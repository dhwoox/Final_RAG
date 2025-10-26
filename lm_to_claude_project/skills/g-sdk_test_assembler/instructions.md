# Skill Textbook: G-SDK Test Script Assembly

## Goal
To assemble all generated code snippets into a final, complete, and runnable `unittest` script.

## Learning Source
**Study the template provided by the `get_test_script_template()` function in `functions.py` of this skill.**

- This function returns a string that serves as the skeleton for the final test file.
- It contains placeholders like `{class_name}`, `{docstring}`, and `<<<LLM_INSERT_...>>>`.

## Your Task

Your final step is to act as an assembler.

1.  Call `get_test_script_template()` to get the skeleton of the test script.
2.  **Fill in the placeholders** in the template string with the information and code you have generated in the previous steps.
3.  You must follow the 7-phase workflow from `01_WORKFLOW_GUIDE.md` when filling in the template.
    - Determine the necessary `pb2` imports and add them.
    - Fill in the capability checks.
    - Insert the data preparation code.
    - Insert the auth setup code.
    - Insert the execution and verification code (the `EventMonitor` block).
4.  The final, filled-in string is the complete test script. Return this as your final answer.