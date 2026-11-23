# User Acceptance Testing (UAT) & Failure Analysis Report

**QA & Delivery Lead**: Abdul Qadir Satti (23K-0674, BCS-7B)  
**Execution Day**: Day 13 (per KuaiRec WBS)  
**Status**: All 5 Acceptance Test Scenarios Passed  

---

## Acceptance Test Scenario 1: Active User Recommendation & Personalization
- **Objective**: Verify that an active user with specific interest history receives relevant personalized recommendations with verifiable reason codes.
- **Test Steps**:
  1. Open `/` in browser.
  2. Select `user_1001` (History: Gaming videos `v_101`, `v_102`).
  3. Inspect Top-5 recommendations.
- **Expected Outcome**:
  - Top video is `v_119` ("Unreal Engine 5 Next-Gen Graphics Showcase") with score $> 0.80$.
  - Reason code displayed: `similar_to_recent`.
  - Machine-readable evidence: points to `v_101` with cosine similarity $0.840$.
- **Result**: **PASS**

---

## Acceptance Test Scenario 2: Zero-History Cold-Start Fallback
- **Objective**: Verify that a user with 0 interactions triggers the cold-start fallback gracefully.
- **Test Steps**:
  1. Select `user_cold_start` from profile dropdown (or click "Force Cold-Start Fallback").
  2. Send recommendation request.
- **Expected Outcome**:
  - API response returns `"fallback": true` and `"model": "popularity-v1"`.
  - Reason badge displays `cold_start`: `"Curated top-performing video for new viewers (cold-start baseline)"`.
  - Videos returned are the highest exposure/view videos from the catalog (`v_108`, `v_107`, `v_111`).
- **Result**: **PASS**

---

## Acceptance Test Scenario 3: Already-Seen Item Exclusion
- **Objective**: Verify that videos previously watched by the user are never recommended when `exclude_seen == true`.
- **Test Steps**:
  1. Select `user_1001` with `exclude_seen` checked.
  2. Inspect recommendation IDs against user's history (`v_101`, `v_102`, `v_115`).
- **Expected Outcome**: None of `v_101`, `v_102`, or `v_115` appear in the recommended list.
- **Result**: **PASS**

---

## Acceptance Test Scenario 4: Runtime Model Hot-Switching
- **Objective**: Verify that an operator or user can switch the active serving model at runtime without restarting the service.
- **Test Steps**:
  1. In the feed or on `/system`, click "Item-CF".
  2. Trigger `/api/v1/models/switch` with `model_id: "itemcf-v1"`.
  3. Verify recommendation response metadata.
- **Expected Outcome**:
  - Active model changes to `itemcf-v1`.
  - Subsequent recommendations on the feed reflect Item-CF scoring and reason codes.
- **Result**: **PASS**

---

## Acceptance Test Scenario 5: User Feedback Interaction & Persistence
- **Objective**: Verify that user feedback buttons (Play, Click, Skip, Hide) asynchronously persist to the database and update telemetry.
- **Test Steps**:
  1. Click the **Play** button on video card #1.
  2. Verify UI acknowledgment badge (`✓ Logged: play`).
  3. Navigate to `/system` and observe real-time telemetry counter.
- **Expected Outcome**:
  - Feedback event is saved to SQLite table `feedback_events`.
  - Telemetry counter increments by 1.
- **Result**: **PASS**

---

## Failure Mode Analysis & Guardrails

| Failure Mode | Risk | Built-in Guardrail in Implementation |
|---|---|---|
| **Unknown User ID** | Crash / Null Pointer | Default to cold-start popularity baseline with `"fallback": true`. |
| **Empty Catalog** | Internal Server Error | Handled gracefully with HTTP 400/500 structured error message. |
| **Backend Unreachable** | Blank screen in UI | Next.js API client catches timeout/network errors, surfaces user-friendly alert, and retry guidance. |
| **Missing Reason Evidence** | Misleading explanation | Explanation generator validates similarity threshold ($\ge 0.40$); if missing, falls back to `liked_by_similar_users` or `popular_in_training`. |
