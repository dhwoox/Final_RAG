# This file serves as a textbook example for the LLM.
# The agent will load this entire file's source code and provide it to the LLM for study.

import user_pb2
from test import util

def create_user_with_pin_and_finger_example(svcManager):
    """
    This function is a clear, readable example of how to generate a user
    with a fingerprint and a PIN. The LLM will read this source code
    to learn the correct pattern.
    """

    # 1. Create a random ID, checking for device capabilities.
    # This pattern is learned from 03_TEST_DATA_GUIDE.md.
    user_id = util.randomNumericUserID()
    # if capability.alphanumericIDSupported:
    #     user_id = util.randomAlphanumericUserID()

    # 2. Create a random PIN.
    plain_pin = util.generateRandomPIN()

    # 3. Instantiate the UserInfo object.
    new_user = user_pb2.UserInfo()
    new_user.hdr.ID = user_id

    # 4. Hash the PIN and assign it. The svcManager is required for this.
    new_user.PIN = svcManager.hashPIN(plain_pin)

    # 5. Assign a fingerprint template. 
    # The LLM must understand that this template data needs to come from a real source,
    # as explained in the guides. This is a placeholder.
    finger_template = b'\x01\x02\x03\x04\x05\x06\x07\x08' # Placeholder
    finger = user_pb2.FingerData(index=0, templates=[finger_template])
    new_user.fingers.append(finger)
    new_user.hdr.numOfFinger = 1

    # 6. Return the user object and the plain pin for later use in authentication.
    return new_user, plain_pin

def configure_auth_mode_example(svcManager, targetID, capability):
    """
    This function shows the pattern for setting an authentication mode,
    as described in 02_REFERENCE_GUIDE.md. The LLM will study this pattern.
    """
    import auth_pb2
    import time

    # Get the current configuration.
    auth_conf = svcManager.getAuthConfig(targetID)
    auth_conf.authSchedules.clear()

    # Decide the mode based on device capability.
    if capability.extendedFingerprintPINSupported:
        mode = auth_pb2.AUTH_EXT_MODE_FINGERPRINT_PIN
    else:
        mode = auth_pb2.AUTH_MODE_BIOMETRIC_PIN
    
    # Append the new schedule.
    auth_conf.authSchedules.append(
        auth_pb2.AuthSchedule(mode=mode, scheduleID=1) # Schedule 1 is 'Always'
    )
    
    # Apply the configuration.
    svcManager.setAuthConfig(targetID, auth_conf)
    time.sleep(0.5) # Wait for the setting to be applied.

    print("Authentication mode for 'Fingerprint + PIN' has been set.")