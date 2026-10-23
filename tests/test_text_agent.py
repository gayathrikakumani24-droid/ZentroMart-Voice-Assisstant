"""
Unit and integration tests for ZentroMart VoiceOps Text Agent.

Covers the 12 representative evaluation scenarios:
1. Current-policy question (PQ0003: wallet refund)
2. Historical-policy question (superseded v3 returns before 1 Aug 2026)
3. Multilingual / Hinglish question (PQ0002: SKU Assured warranty)
4. Multi-section answer requiring multiple sources (PQ0010: RET-6 + DWM-2)
5. Follow-up question relying on previous context (PC003 turns 4 -> 5)
6. Order lookup with correct verification (PC002 turn 3: 89782837 + 4533)
7. Order lookup with incorrect or missing verification (PC021: unverified + retry + refusal)
8. Request that results in ticket creation (PC002 turn 4: TV damage > 10k)
9. Tool failure or ticket-creation failure handling
10. Business-day, holiday, and calendar-day calculations (PQ0008: card refund from 17 Oct)
11. Question with insufficient evidence (PQ0004: midnight delivery / PQ0009: student discount)
12. Session isolation (Session A must not leak into Session B)
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from src.business_rules import (
    REFERENCE_DATE,
    add_business_days,
    calculate_refund_arrival,
    calculate_return_deadline,
    is_business_day,
    lookup_product,
)
from src.conversation import ZentroMartConversation, ConversationSession, _session_manager
from src.order_tools import lookup_order, create_ticket
from src.llm_agent import GroqLLMWrapper, extract_cited_sources, format_all_evidence


class TestTextAgent(unittest.TestCase):

    def setUp(self):
        # Clear sessions before each test
        _session_manager._sessions.clear()

    # 1. Current policy question
    def test_01_current_policy_question(self):
        agent = ZentroMartConversation("test_sess_01")
        res = agent.respond("How fast are refunds to the ZentroMart Wallet?")
        self.assertEqual(res["decision"], "answer")
        ans_lower = res["answer"].lower()
        self.assertTrue(any(w in ans_lower for w in ["instant", "2 hours", "two hours", "तुरंत"]))
        self.assertFalse("5 to 7 days" in ans_lower)
        self.assertIn("REF-2", res["sources"])

    # 2. Historical policy question involving superseded return policy
    def test_02_historical_policy_question(self):
        # Delivered before 1 August 2026: Electronics window is 10 days under v3 (POL-RET-v3)
        deadline_old, window_old = calculate_return_deadline("2026-07-20", "electronics")
        self.assertEqual(window_old, 10)
        self.assertEqual(deadline_old, date(2026, 7, 30))

        # Delivered after 1 August 2026: Electronics window is 7 days under v4 (POL-RET)
        deadline_new, window_new = calculate_return_deadline("2026-08-10", "electronics")
        self.assertEqual(window_new, 7)
        self.assertEqual(deadline_new, date(2026, 8, 17))

    # 3. Multilingual / Hinglish question
    def test_03_multilingual_hinglish_question(self):
        agent = ZentroMartConversation("test_sess_03")
        res = agent.respond("SKU ELE-0012 pe ZentroMart Assured hai kya? Claim kaise karein?")
        self.assertEqual(res["decision"], "answer")
        ans_lower = res["answer"].lower()
        self.assertTrue("12" in ans_lower)
        self.assertTrue(any(w in ans_lower for w in ["my orders", "app"]))
        self.assertTrue(any("WAR-2" in s or "products.csv" in s for s in res["sources"]))

    # 4. Multi-section answer requiring more than one source
    def test_04_multisection_answer(self):
        # Return fee waived for damaged goods: RET-6 + DWM-2
        agent = ZentroMartConversation("test_sess_04")
        res = agent.respond("Is the collection free if the UrbanThread Slim Fit Jeans came torn?")
        self.assertEqual(res["decision"], "answer")
        ans_lower = res["answer"].lower()
        self.assertTrue(any(w in ans_lower for w in ["free", "no fee", "waived", "no charge", "नहीं"]))

    # 5. Follow-up question relying on previous context
    def test_05_followup_question_with_context(self):
        agent = ZentroMartConversation("test_sess_05")
        # Turn 1: Greeting
        agent.respond("Hello, mujhe order ke baare mein help chahiye.")
        # Turn 2: Order ID
        agent.respond("Order number hai 1859 9253.")
        # Turn 3: Verification
        agent.respond("Last four digits 4265 hain.")
        self.assertTrue(agent.is_verified)
        # Turn 4: Return question
        res4 = agent.respond("Kya main Kaafi Running Sneakers return kar sakti hoon?")
        self.assertEqual(res4["decision"], "answer")
        self.assertTrue(any(d in res4["answer"] for d in ["2026-10-27", "27 October 2026", "27 अक्टूबर"]))
        # Turn 5: Follow-up on refund timeline (wallet payment in order)
        res5 = agent.respond("Aur refund kitne din mein aayega?")
        self.assertEqual(res5["decision"], "answer")
        ans_lower = res5["answer"].lower()
        self.assertTrue(any(w in ans_lower for w in ["instant", "2 hours", "turant", "तुरंत", "2 ghante"]))

    # 6. Order lookup with correct verification
    def test_06_order_lookup_verified(self):
        agent = ZentroMartConversation("test_sess_06")
        # Step 1: Order provided
        res1 = agent.respond("Order number hai 8978 2837.")
        self.assertEqual(res1["decision"], "clarify")
        self.assertFalse(agent.is_verified)
        self.assertTrue(any(w in res1["answer"].lower() for w in ["last 4", "pincode", "आख़िरी", "पिनकोड"]))
        # Step 2: Proof provided
        res2 = agent.respond("Last four digits 4533 hain.")
        self.assertEqual(res2["decision"], "answer")
        self.assertTrue(agent.is_verified)
        self.assertIsNotNone(agent.session.verified_order)
        self.assertEqual(agent.session.verified_order.get("order_id"), "89782837")

    # 7. Order lookup with incorrect or missing verification
    def test_07_order_lookup_unverified_and_refusal(self):
        agent = ZentroMartConversation("test_sess_07")
        # Turn 1: Order provided
        agent.respond("ऑर्डर नंबर है 7746 1439।")
        self.assertFalse(agent.is_verified)
        # Turn 2: Wrong digits (attempt 1) -> clarify retry
        res2 = agent.respond("आख़िरी चार अंक 9999 हैं।")
        self.assertEqual(res2["decision"], "clarify")
        self.assertFalse(agent.is_verified)
        self.assertTrue(any(w in res2["answer"].lower() for w in ["again", "match", "दोबारा", "मेल"]))
        # Turn 3: Wrong digits again (attempt 2) -> refuse
        res3 = agent.respond("आख़िरी चार अंक 9999 हैं।")
        self.assertEqual(res3["decision"], "refuse")
        self.assertFalse(agent.is_verified)
        self.assertTrue(any(w in res3["answer"].lower() for w in ["registered", "can't share", "cannot share", "नहीं बता", "साझा नहीं"]))

    # 8. Request that results in ticket creation
    def test_08_ticket_creation_on_damage(self):
        agent = ZentroMartConversation("test_sess_08")
        # Setup verified order
        agent.respond("Order number hai 8978 2837.")
        agent.respond("Last four digits 4533 hain.")
        self.assertTrue(agent.is_verified)
        # Turn 3: High value damaged TV
        res = agent.respond("Maine Zentro Vista 43-inch 4K Smart TV damage report kiya tha. Abhi replacement approve kar do na?")
        self.assertEqual(res["decision"], "escalate")
        self.assertIsNotNone(res["created_ticket"])
        self.assertTrue(res["created_ticket"].get("created"))
        ans_lower = res["answer"].lower()
        self.assertTrue(any(w in ans_lower for w in ["ticket", "team", "colleague", "priority"]))
        self.assertFalse("approve kar diya" in ans_lower)

    # 9. Tool failure or ticket creation failure handling
    def test_09_ticket_creation_failure_handling(self):
        # If create_ticket tool fails (e.g. summary too short or system error)
        result = create_ticket("short")
        self.assertFalse(result.get("created"))
        self.assertIn("summary too short", result.get("error", "").lower())

    # 10. Business-day, holiday, and calendar-day calculations
    def test_10_business_day_and_holiday_calculations(self):
        # 2026-10-17 is Saturday. Sunday (18 Oct) skipped. Warehouse Holiday (19 Oct) skipped.
        # Next business days:
        # Day 1: 20 Oct (Tue)
        # Day 2: 21 Oct (Wed)
        # Day 3: 22 Oct (Thu)
        # Day 4: 23 Oct (Fri)
        # Day 5: 24 Oct (Sat)
        # 25 Oct is Sunday (skipped)
        # Day 6: 26 Oct (Mon)
        # Day 7: 27 Oct (Tue)
        calc = calculate_refund_arrival("card", "2026-10-17")
        self.assertEqual(calc["min_days"], 5)
        self.assertEqual(calc["max_days"], 7)
        self.assertEqual(calc["min_date"], date(2026, 10, 24))
        self.assertEqual(calc["max_date"], date(2026, 10, 27))
        self.assertEqual(calc["max_date_str"], "2026-10-27")

        # Calendar day calculation for Festive return (PC004)
        deadline, window = calculate_return_deadline("2026-10-14", "fashion", "2026-10-06")
        self.assertEqual(window, 30)
        self.assertEqual(deadline, date(2026, 11, 13))

    # 11. Question with insufficient evidence
    def test_11_insufficient_evidence(self):
        agent = ZentroMartConversation("test_sess_11")
        res = agent.respond("Can I schedule a delivery at midnight?")
        self.assertEqual(res["decision"], "answer")
        ans_lower = res["answer"].lower()
        self.assertTrue(any(w in ans_lower for w in ["don't have", "no information", "not sure", "colleague", "help"]))

    # 12. Session isolation
    def test_12_session_isolation(self):
        sess_a = ZentroMartConversation("sess_A")
        sess_b = ZentroMartConversation("sess_B")

        # Session A gets verified
        sess_a.respond("Order number hai 8978 2837.")
        sess_a.respond("Last four digits 4533 hain.")
        self.assertTrue(sess_a.is_verified)
        self.assertEqual(sess_a.order_id, "89782837")

        # Session B must remain completely unverified and empty
        self.assertFalse(sess_b.is_verified)
        self.assertIsNone(sess_b.order_id)
        self.assertEqual(len(sess_b.history), 0)


if __name__ == "__main__":
    unittest.main()
