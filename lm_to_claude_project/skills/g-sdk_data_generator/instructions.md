
# Skill Textbook: G-SDK Test Data Generation

## Goal
To generate test data like `UserInfo` objects and set device configurations like `AuthConfig`.

## Learning Source
**Study the source code in `functions.py` of this skill.**

- The file `functions.py` contains clear, well-commented example functions like `create_user_with_pin_and_finger_example()` and `configure_auth_mode_example()`.
- These functions are your primary learning material. Read their source code to understand the correct pattern for:
  - Instantiating `pb2` objects.
  - Generating random data using `util` functions.
  - Hashing PINs.
  - Checking device capabilities before setting a mode.
  - Applying the configuration to the device via the `svcManager`.

## Your Task
When you need to generate test data or configure a device, do not just call the functions in this skill. Instead, **emulate the patterns you learn from their source code** to write new, specific code that fits the exact requirements of the test case.
