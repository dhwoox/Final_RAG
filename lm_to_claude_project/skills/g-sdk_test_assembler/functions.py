# This file serves as a textbook example for the LLM.
# It provides a template for the final unittest script structure.

def get_test_script_template() -> str:
    """
    Returns a string template for a complete G-SDK unittest file.
    The LLM will fill in the placeholders in this template.
    """
    template = """\
# Standard library imports
import unittest
import time

# Local application/library specific imports
# The LLM must determine the necessary pb2 imports based on the test case.
from test import testCOMMONR
from test import util
# import user_pb2
# import auth_pb2
# import finger_pb2

# <<<LLM_INSERT_IMPORTS>>>

class {class_name}(testCOMMONR.TestCOMMONR):
    """
    {docstring}
    """

    def {test_name}(self):
        """
        {docstring}
        """
        # The LLM should assemble the code here following the 7-phase workflow
        # from 01_WORKFLOW_GUIDE.md.

        # Phase 4: Device Capability Verification
        # <<<LLM_INSERT_CAPABILITY_CHECKS>>>

        # Phase 3: Test Data Preparation
        print("--- Preparing Test Data ---")
        # <<<LLM_INSERT_DATA_PREPARATION_CODE>>>
        print("--- Test Data Prepared ---")

        # Phase 5: Authentication Mode Setup
        print("--- Setting Auth Mode ---")
        # <<<LLM_INSERT_AUTH_SETUP_CODE>>>
        print("--- Auth Mode Set ---")

        # Phase 6 & 7: Test Execution and Verification
        print("--- Executing Test and Verifying Event ---")
        # <<<LLM_INSERT_EXECUTION_AND_VERIFICATION_CODE>>>
        print("--- Test Finished ---")

if __name__ == '__main__':
    unittest.main()

"""
    return template