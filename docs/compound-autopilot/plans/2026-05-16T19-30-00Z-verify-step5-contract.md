# Plan: Verify Step 5 Rebalance Contract

**Goal:** Ensure `step5-rebalance` correctly adheres to the contract: local IDs in `1..N`, no `0`.

**Current Behavior:** Unverified via automated tests for this specific constraint.

**Contract Surfaces:**
- `local_id` in CSV output must be $\ge 1$.
- No `local_id == 0` present in the rebalanced file.

**Risks:**
- Regression if logic changes to use 0-based indexing.
- Incorrectly counting or skipping items during batch processing.

**Implementation Units:**
- **Tier 0: Test Case Creation**
    - Create a new test file `tests/test_step5_contract.py`.
    - The test should generate a dummy input CSV with valid levels.
    - Run `classificator step5-rebalance` (mocked or minimal).
    - Check output for presence of any `0` in `local_id`.
    - Status: completed.

**Expected Files:**
- `tests/test_step5_contract.py`

**Verification Command:**
`PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'`
