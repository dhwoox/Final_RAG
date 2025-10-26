
# This file serves as a textbook example for the LLM.
# The agent will load this entire file's source code and provide it to the LLM for study.

from test import util

def verify_event_example(svcManager, targetID, user_id):
    """
    This function is a clear, readable example of how to use the EventMonitor
    to verify that a specific event has occurred.
    """
    # The event code should be determined by the LLM based on the test case context
    # and the information in event_codes.json.
    # For this example, we will use 0x1302 (Fingerprint + PIN Success).
    expected_event_code = 4866 # 0x1302
    
    print(f"--- Monitoring for event {hex(expected_event_code)} ---")

    # The EventMonitor is used with a `with` statement.
    with util.EventMonitor(
        svcManager=svcManager,
        masterID=targetID,
        eventCode=expected_event_code,
        userID=user_id, # Filter for events from this specific user
        quiet=True
    ) as monitor:
        
        # =====================================================================
        # The action that is expected to trigger the event goes here.
        # The LLM must generate this part based on the test scenario.
        # Example for 0x1302:
        # print("Action: Simulating fingerprint and PIN authentication...")
        # svcManager.detectFingerprint(targetID, finger_template)
        # svcManager.enterKey(targetID, plain_pin)
        # =====================================================================
        
        print("Action performed. Waiting for event...")

        # The caught() method waits for the event for a specified timeout.
        event_caught = monitor.caught(timeout=5.0)

        # Assert that the event was indeed caught.
        if not event_caught:
            # In a real unittest, this would be self.fail() or an assertion error.
            print(f"FAIL: Event {hex(expected_event_code)} was not caught.")
        else:
            print(f"SUCCESS: Event {hex(expected_event_code)} was caught.")
            # Further assertions can be made on the event details.
            # print(f"Event details: {monitor.description}")

    return event_caught

