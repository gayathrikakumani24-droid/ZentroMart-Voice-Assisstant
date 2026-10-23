"""
Test Suite for Verified Order Status and Delivery Information.

Validates the 12 backend requirements from Prompt 9:
1. Valid order verification followed by a delivery-status query.
2. Successful lookup returning the actual status in the response.
3. A follow-up question that uses the previously verified order.
4. A delivered order (e.g. 46637226 -> delivered on 2026-10-12).
5. A shipped or other non-delivered order (e.g. 69520867 -> shipped).
6. A query requesting a field that does not exist (courier driver phone / live GPS).
7. An invalid order ID (fails verification).
8. An incorrect verification value (triggers retry / refusal).
9. A missing verification value (prompts for verification).
10. A new session attempting to access another session's verified order (session isolation).
11. Session reset clearing the relevant order context.
12. The FastAPI response preserving the required status information (order_status field).
"""

import unittest
from fastapi.testclient import TestClient
from api.main import app
from src.conversation import ZentroMartConversation, _session_manager


class TestVerifiedOrderStatus(unittest.TestCase):

    def setUp(self):
        _session_manager._sessions.clear()
        self.client = TestClient(app)

    # 1. Valid order verification followed by a delivery-status query
    # 2. Successful lookup returning the actual status in the response
    # 3. A follow-up question that uses the previously verified order
    # 4. A delivered order
    def test_01_delivered_order_status_workflow(self):
        agent = ZentroMartConversation("test_delivered_workflow")
        # Turn 1: Provide order ID
        t1 = agent.respond("I need help with order 46637226.")
        self.assertEqual(t1["decision"], "clarify")
        self.assertFalse(agent.is_verified)
        self.assertIn("IDV-2", t1["sources"])

        # Turn 2: Provide valid pincode
        t2 = agent.respond("My delivery pincode is 122002.")
        self.assertEqual(t2["decision"], "answer")
        self.assertTrue(agent.is_verified)
        self.assertEqual(agent.session.order_id, "46637226")
        self.assertEqual(t2["order_status"], "delivered")

        # Turn 3: Follow-up on delivery status without repeating order ID
        t3 = agent.respond("What is the status of delivery?")
        self.assertEqual(t3["decision"], "answer")
        ans3 = t3["answer"].lower()
        self.assertIn("delivered", ans3)
        self.assertIn("46637226", ans3)
        self.assertTrue(any(d in ans3 for d in ["12 october", "2026-10-12", "12"]))
        self.assertEqual(t3["order_status"], "delivered")

        # Turn 4: Another follow-up on payment method
        t4 = agent.respond("What payment method did I use?")
        self.assertEqual(t4["decision"], "answer")
        ans4 = t4["answer"].lower()
        self.assertIn("cod", ans4)

    # 5. Shipped or other non-delivered order from real dataset
    def test_02_shipped_order_status(self):
        agent = ZentroMartConversation("test_shipped_workflow")
        # Order 69520867 is shipped with promised date 2026-10-23, pincode 160017
        agent.respond("Order number is 69520867.")
        agent.respond("160017")
        self.assertTrue(agent.is_verified)

        res = agent.respond("Where is my order and when will it arrive?")
        self.assertEqual(res["decision"], "answer")
        ans_l = res["answer"].lower()
        self.assertIn("shipped", ans_l)
        self.assertIn("69520867", ans_l)
        self.assertTrue(any(d in ans_l for d in ["23 october", "2026-10-23", "soon", "promised"]))
        self.assertEqual(res["order_status"], "shipped")

    # 6. Query requesting a field that does not exist in the record
    def test_03_query_nonexistent_field(self):
        agent = ZentroMartConversation("test_missing_field")
        agent.respond("46637226")
        agent.respond("122002")
        self.assertTrue(agent.is_verified)

        res = agent.respond("Can you give me the delivery driver's phone number and live GPS location?")
        self.assertEqual(res["decision"], "answer")
        ans_l = res["answer"].lower()
        self.assertTrue(any(w in ans_l for w in ["not available", "apologize", "sorry", "cannot"]))
        # Does not fabricate driver contact, but references the actual status
        self.assertIn("delivered", ans_l)
        self.assertFalse("98765" in ans_l)

    # 7. Invalid order ID
    def test_04_invalid_order_id(self):
        agent = ZentroMartConversation("test_invalid_order")
        # 99999999 does not exist
        res1 = agent.respond("Order is 99999999.")
        self.assertEqual(res1["decision"], "clarify")

        res2 = agent.respond("Pincode is 123456.")
        self.assertFalse(agent.is_verified)
        self.assertEqual(res2["decision"], "clarify")
        self.assertIn("IDV-3", res2["sources"])

    # 8. Incorrect verification value
    def test_05_incorrect_verification_value(self):
        agent = ZentroMartConversation("test_incorrect_verification")
        agent.respond("Order number 46637226.")
        # Attempt 1: wrong pincode
        r1 = agent.respond("000000")
        self.assertFalse(agent.is_verified)
        self.assertEqual(r1["decision"], "clarify")

        # Attempt 2: wrong pincode again -> refusal
        r2 = agent.respond("000000")
        self.assertFalse(agent.is_verified)
        self.assertEqual(r2["decision"], "refuse")
        self.assertIn("IDV-3", r2["sources"])

    # 9. Missing verification value
    def test_06_missing_verification_value(self):
        agent = ZentroMartConversation("test_missing_verification")
        res = agent.respond("Can you track my order 46637226 right now?")
        self.assertEqual(res["decision"], "clarify")
        self.assertFalse(agent.is_verified)
        ans_l = res["answer"].lower()
        self.assertTrue(any(w in ans_l for w in ["last 4", "pincode", "verify", "security"]))
        # Protected delivery date/status must NOT be disclosed yet
        self.assertNotIn("2026-10-12", ans_l)

    # 10. A new session attempting to access another session's verified order
    def test_07_session_isolation_verified_order(self):
        sess_a = ZentroMartConversation("sess_verified_A")
        sess_b = ZentroMartConversation("sess_unverified_B")

        # Verify order in Session A
        sess_a.respond("46637226")
        sess_a.respond("122002")
        self.assertTrue(sess_a.is_verified)

        # Session B asks about delivery status without verifying
        res_b = sess_b.respond("What is the status of delivery?")
        self.assertFalse(sess_b.is_verified)
        self.assertIsNone(sess_b.order_id)
        # Session B must NOT receive order 46637226's status
        self.assertNotEqual(res_b.get("order_status"), "delivered")
        self.assertNotIn("46637226", res_b.get("answer", ""))

    # 11. Session reset clearing the relevant order context
    def test_08_session_reset_clears_order_context(self):
        agent = ZentroMartConversation("sess_to_reset")
        agent.respond("46637226")
        agent.respond("122002")
        self.assertTrue(agent.is_verified)
        self.assertEqual(agent.order_id, "46637226")

        # Reset session
        reset_res = agent.respond("reset")
        self.assertFalse(agent.is_verified)
        self.assertIsNone(agent.order_id)
        self.assertIsNone(agent.session.verified_order)

        # Follow-up after reset requires order ID and verification anew
        follow_res = agent.respond("What is the delivery status?")
        self.assertFalse(agent.is_verified)
        self.assertNotIn("46637226", follow_res["answer"])

    # Switching order ID resets verification
    def test_09_order_switching_resets_verification(self):
        agent = ZentroMartConversation("sess_switch_order")
        agent.respond("46637226")
        agent.respond("122002")
        self.assertTrue(agent.is_verified)

        # Now mention a different order 69520867
        switch_res = agent.respond("Now check order 69520867.")
        self.assertEqual(agent.order_id, "69520867")
        self.assertFalse(agent.is_verified)
        self.assertEqual(switch_res["decision"], "clarify")

    # 12. FastAPI response preserving the required status information
    def test_10_fastapi_endpoint_order_status(self):
        # Create session
        sess_id = self.client.post("/sessions").json()["session_id"]

        # Step 1: Send order ID
        r1 = self.client.post("/chat", json={"session_id": sess_id, "message": "My order is 46637226."})
        self.assertEqual(r1.status_code, 200)
        self.assertFalse(r1.json()["is_verified"])

        # Step 2: Send pincode
        r2 = self.client.post("/chat", json={"session_id": sess_id, "message": "Pincode is 122002."})
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertTrue(d2["is_verified"])
        self.assertEqual(d2["order_status"], "delivered")

        # Step 3: Ask delivery status
        r3 = self.client.post("/chat", json={"session_id": sess_id, "message": "What is the status of delivery?"})
        self.assertEqual(r3.status_code, 200)
        d3 = r3.json()
        self.assertTrue(d3["is_verified"])
        self.assertEqual(d3["order_status"], "delivered")
        self.assertIn("delivered", d3["answer"].lower())
        self.assertIn("46637226", d3["answer"])


if __name__ == "__main__":
    unittest.main()
