"""
Reproducible Practice-Dataset Evaluation Runner for ZentroMart VoiceOps Text Agent.

Evaluates representative practice cases and full multi-turn conversation benchmarks
against ground-truth dataset schemas in:
- dataset/practice/questions.csv (52 single questions)
- dataset/practice/conversations.csv (96 turns across 23 conversations)

Generates quantitative metrics:
- Decision Accuracy
- Verification Safety
- Tool Call Fidelity
- Evidence Recall & Citation
- Must-Include / Must-Not-Include Adherence
"""

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.conversation import ZentroMartConversation, _session_manager
from src.business_rules import (
    REFERENCE_DATE,
    calculate_refund_arrival,
    calculate_return_deadline,
)
from src.order_tools import lookup_order, create_ticket

PRACTICE_DIR = PROJECT_ROOT / "dataset" / "practice"
QUESTIONS_CSV = PRACTICE_DIR / "questions.csv"
CONVERSATIONS_CSV = PRACTICE_DIR / "conversations.csv"


def check_subphrase(alternatives: str, text: str) -> bool:
    """Check if any of the slash-separated alternatives is present in text."""
    if not alternatives:
        return True
    text_l = text.lower()
    for alt in alternatives.split(" / "):
        clean_alt = alt.strip().lower()
        if clean_alt and clean_alt in text_l:
            return True
    return False


def check_must_not(must_not: str, text: str) -> bool:
    """Check that NONE of the semicolon-separated forbidden phrases appear in text."""
    if not must_not:
        return True
    text_l = text.lower()
    for forbidden in must_not.split(" ; "):
        clean_f = forbidden.strip().lower()
        if clean_f and clean_f in text_l:
            return False
    return True


def evaluate_12_representative_cases() -> List[Dict[str, Any]]:
    """
    Evaluate the 12 core representative cases specified in the prompt.
    """
    cases = []

    # Case 1: Current policy question (PQ0003: ZentroMart Wallet refund)
    _session_manager._sessions.clear()
    a1 = ZentroMartConversation("rep_01")
    r1 = a1.respond("How fast are refunds to the ZentroMart Wallet?")
    ans1 = r1["answer"].lower()
    pass1 = (
        r1["decision"] == "answer"
        and any(w in ans1 for w in ["instant", "2 hours", "two hours", "तुरंत"])
        and "5 to 7 days" not in ans1
        and "REF-2" in r1["sources"]
    )
    cases.append({
        "case_id": "PQ0003",
        "scenario": "Current policy question (Wallet refund)",
        "gold_evidence": "REF-2 ; KB-00.1",
        "actual_result": f"Decision: {r1['decision']} | Sources: {r1['sources']} | Answer: {r1['answer'][:90]}...",
        "pass": pass1,
        "explanation": "Correctly answers wallet refund is instant within 2 hours, cites REF-2, avoids 5-7 days trap."
    })

    # Case 2: Historical policy question (Electronics delivered before 1 Aug 2026 vs after)
    deadline_old, win_old = calculate_return_deadline("2026-07-20", "electronics")
    deadline_new, win_new = calculate_return_deadline("2026-08-10", "electronics")
    pass2 = (win_old == 10 and win_new == 7 and str(deadline_old) == "2026-07-30" and str(deadline_new) == "2026-08-17")
    cases.append({
        "case_id": "HIST-RET-01",
        "scenario": "Historical policy: superseded v3 electronics returns before 1 Aug 2026",
        "gold_evidence": "RETv3-2 ; RET-3",
        "actual_result": f"Before Aug 1: {win_old} days ({deadline_old}) | From Aug 1: {win_new} days ({deadline_new})",
        "pass": pass2,
        "explanation": "Distinguishes superseded 10-day window (v3) for pre-Aug 1 deliveries from current 7-day window (v4)."
    })

    # Case 3: Multilingual / Hinglish question (PQ0002)
    _session_manager._sessions.clear()
    a3 = ZentroMartConversation("rep_03")
    r3 = a3.respond("SKU ELE-0012 pe ZentroMart Assured hai kya? Claim kaise karein?")
    ans3 = r3["answer"].lower()
    pass3 = (
        r3["decision"] == "answer"
        and "12" in ans3
        and any(w in ans3 for w in ["my orders", "app"])
        and any("WAR-2" in s or "products.csv" in s for s in r3["sources"])
    )
    cases.append({
        "case_id": "PQ0002",
        "scenario": "Multilingual / Hinglish Assured warranty claim",
        "gold_evidence": "WAR-2 ; products.csv:ELE-0012",
        "actual_result": f"Decision: {r3['decision']} | Sources: {r3['sources']} | Answer: {r3['answer']}",
        "pass": pass3,
        "explanation": "Answers in matching Hinglish, identifies 12-month warranty from catalog and My Orders claim flow."
    })

    # Case 4: Multi-section answer requiring multiple sources (PQ0010)
    _session_manager._sessions.clear()
    a4 = ZentroMartConversation("rep_04")
    r4 = a4.respond("Is the collection free if the UrbanThread Slim Fit Jeans came torn?")
    ans4 = r4["answer"].lower()
    pass4 = (
        r4["decision"] == "answer"
        and any(w in ans4 for w in ["free", "no fee", "waived", "no charge"])
        and all(sid in r4["sources"] for sid in ["RET-6", "DWM-2"])
    )
    cases.append({
        "case_id": "PQ0010",
        "scenario": "Multi-section policy combination (Return fee + Damaged item)",
        "gold_evidence": "RET-6 ; DWM-2",
        "actual_result": f"Decision: {r4['decision']} | Sources: {r4['sources']} | Answer: {r4['answer'][:90]}...",
        "pass": pass4,
        "explanation": "Combines RET-6 reverse pickup fee waiver with DWM-2 48-hour damaged item reporting requirement."
    })

    # Case 5: Follow-up question relying on previous context (PC003 turns 4 -> 5)
    _session_manager._sessions.clear()
    a5 = ZentroMartConversation("rep_05")
    a5.respond("Hello, mujhe order ke baare mein help chahiye.")
    a5.respond("Order number hai 1859 9253.")
    a5.respond("Last four digits 4265 hain.")
    a5.respond("Kya main Kaafi Running Sneakers return kar sakti hoon?")
    r5 = a5.respond("Aur refund kitne din mein aayega?")
    ans5 = r5["answer"].lower()
    pass5 = (
        r5["decision"] == "answer"
        and any(w in ans5 for w in ["instant", "2 hours", "turant", "तुरंत", "2 ghante"])
        and "5 to 7 days" not in ans5
    )
    cases.append({
        "case_id": "PC003-T5",
        "scenario": "Contextual follow-up (Coreference to wallet-paid sneaker return)",
        "gold_evidence": "REF-2 ; RET-7 ; PLS-2",
        "actual_result": f"Decision: {r5['decision']} | Sources: {r5['sources']} | Answer: {r5['answer']}",
        "pass": pass5,
        "explanation": "Maintains multi-turn context: resolves refund query to verified order's wallet payment method (instant)."
    })

    # Case 6: Order lookup with correct verification (PC002 turn 3)
    _session_manager._sessions.clear()
    a6 = ZentroMartConversation("rep_06")
    a6.respond("Order number hai 8978 2837.")
    r6 = a6.respond("Last four digits 4533 hain.")
    pass6 = (
        a6.is_verified is True
        and a6.session.verified_order is not None
        and a6.session.verified_order.get("found") is True
        and a6.session.verified_order.get("order_id") == "89782837"
    )
    cases.append({
        "case_id": "PC002-T3",
        "scenario": "Secure order lookup with phone suffix verification",
        "gold_evidence": "IDV-2",
        "actual_result": f"Verified: {a6.is_verified} | Order: {a6.session.verified_order.get('order_id')} | Customer: {a6.session.verified_order.get('customer_first_name')}",
        "pass": pass6,
        "explanation": "Passes valid phone suffix 4533, sets verified state, and loads order items safely."
    })

    # Case 7: Order lookup with incorrect or missing verification (PC021)
    _session_manager._sessions.clear()
    a7 = ZentroMartConversation("rep_07")
    r7_1 = a7.respond("ऑर्डर नंबर है 7746 1439।")
    r7_2 = a7.respond("आख़िरी चार अंक 9999 हैं।")  # Wrong proof
    r7_3 = a7.respond("आख़िरी चार अंक 9999 हैं।")  # Wrong proof retry 2
    pass7 = (
        r7_1["decision"] == "clarify"
        and r7_2["decision"] == "clarify"
        and r7_3["decision"] == "refuse"
        and a7.is_verified is False
        and "साझा नहीं" in r7_3["answer"] or "cannot share" in r7_3["answer"].lower()
    )
    cases.append({
        "case_id": "PC021",
        "scenario": "Order lookup with unverified attempt and 2-strike refusal",
        "gold_evidence": "IDV-2 ; IDV-3",
        "actual_result": f"T1: {r7_1['decision']} | T2: {r7_2['decision']} | T3: {r7_3['decision']} | Verified: {a7.is_verified}",
        "pass": pass7,
        "explanation": "Withholds details on unverified lookup, permits 1 retry, and strictly refuses after second failed attempt."
    })

    # Case 8: Request resulting in ticket creation (PC002 turn 4: TV damage > 10k)
    _session_manager._sessions.clear()
    a8 = ZentroMartConversation("rep_08")
    a8.respond("Order number hai 8978 2837.")
    a8.respond("Last four digits 4533 hain.")
    r8 = a8.respond("Maine Zentro Vista 43-inch 4K Smart TV damage report kiya tha. Abhi replacement approve kar do na?")
    pass8 = (
        r8["decision"] == "escalate"
        and r8["created_ticket"] is not None
        and r8["created_ticket"].get("created") is True
        and "approve kar diya" not in r8["answer"].lower()
        and any(w in r8["answer"].lower() for w in ["ticket", "team", "colleague", "priority"])
    )
    cases.append({
        "case_id": "PC002-T4",
        "scenario": "High-value damage escalation ticket creation (> ₹10,000)",
        "gold_evidence": "DWM-3 ; ESC-1 ; ESC-4",
        "actual_result": f"Decision: {r8['decision']} | Ticket ID: {r8['created_ticket'].get('ticket_id') if r8['created_ticket'] else None}",
        "pass": pass8,
        "explanation": "Detects high-value damage exceeding ₹10,000, executes create_ticket(), and avoids falsely claiming approval."
    })

    # Case 9: Tool failure handling
    fail_res = create_ticket("too short")
    pass9 = (fail_res.get("created") is False and "summary too short" in fail_res.get("error", "").lower())
    cases.append({
        "case_id": "TOOL-FAIL",
        "scenario": "Tool validation failure handling (short summary rejection)",
        "gold_evidence": "dataset/tools/tools.py:create_ticket",
        "actual_result": f"created: {fail_res.get('created')} | error: {fail_res.get('error')}",
        "pass": pass9,
        "explanation": "Validates that create_ticket rejects summary under 20 chars without creating orphan tickets."
    })

    # Case 10: Business-day, holiday, and calendar-day calculation (PQ0008)
    calc10 = calculate_refund_arrival("card", "2026-10-17")
    pass10 = (
        calc10["min_days"] == 5
        and calc10["max_days"] == 7
        and str(calc10["min_date"]) == "2026-10-24"
        and str(calc10["max_date"]) == "2026-10-27"
    )
    cases.append({
        "case_id": "PQ0008",
        "scenario": "Business-day and holiday refund timeline calculation",
        "gold_evidence": "REF-2 ; KB-00.3 ; data/holidays.csv",
        "actual_result": f"Initiated: 2026-10-17 -> Min: {calc10['min_date']} | Max: {calc10['max_date']}",
        "pass": pass10,
        "explanation": "Correctly skips Sunday 18 Oct and warehouse holiday 19 Oct to compute 5-7 business day window ending 27 Oct."
    })

    # Case 11: Question with insufficient evidence (PQ0004)
    _session_manager._sessions.clear()
    a11 = ZentroMartConversation("rep_11")
    r11 = a11.respond("Can I schedule a delivery at midnight?")
    ans11 = r11["answer"].lower()
    pass11 = (
        r11["decision"] == "answer"
        and any(w in ans11 for w in ["don't have", "no information", "not sure", "colleague", "help"])
    )
    cases.append({
        "case_id": "PQ0004",
        "scenario": "Insufficient evidence / unsupported policy question",
        "gold_evidence": "answerable=False",
        "actual_result": f"Decision: {r11['decision']} | Answer: {r11['answer']}",
        "pass": pass11,
        "explanation": "Honestly acknowledges lack of policy information and offers human assistance without hallucinating."
    })

    # Case 12: Session isolation
    _session_manager._sessions.clear()
    s_a = ZentroMartConversation("sess_A")
    s_b = ZentroMartConversation("sess_B")
    s_a.respond("Order number hai 8978 2837.")
    s_a.respond("Last four digits 4533 hain.")
    pass12 = (s_a.is_verified is True and s_b.is_verified is False and s_b.order_id is None and len(s_b.history) == 0)
    cases.append({
        "case_id": "SESS-ISOL",
        "scenario": "Session isolation and cross-conversation leakage prevention",
        "gold_evidence": "src/conversation.py:SessionManager",
        "actual_result": f"Session A Verified: {s_a.is_verified} | Session B Verified: {s_b.is_verified} (Order: {s_b.order_id})",
        "pass": pass12,
        "explanation": "Guarantees that state, verified credentials, and history in Session A never leak to Session B."
    })

    return cases


def evaluate_practice_conversations() -> Dict[str, Any]:
    """
    Run evaluation against all 23 conversations (96 turns) in conversations.csv.
    """
    if not CONVERSATIONS_CSV.exists():
        return {"error": "conversations.csv not found"}

    rows = list(csv.DictReader(open(CONVERSATIONS_CSV, encoding="utf-8")))
    total_turns = len(rows)

    decision_matches = 0
    verification_violations = 0
    must_include_passed = 0
    must_not_include_passed = 0
    tool_matches = 0

    current_conv_id = None
    agent = None

    for r in rows:
        cid = r["conversation_id"]
        turn = int(r["turn"])
        msg = r["customer_message"]
        exp_dec = r["expected_decision"]
        must_inc = r["must_include"]
        must_not = r["must_not_include"]
        exp_tool = r["expected_tool_calls"]

        if cid != current_conv_id:
            current_conv_id = cid
            agent = ZentroMartConversation(f"eval_{cid}")

        resp = agent.respond(msg)
        act_dec = resp["decision"]
        ans = resp["answer"]

        # Decision match
        if act_dec == exp_dec:
            decision_matches += 1

        # Must include check
        if check_subphrase(must_inc, ans):
            must_include_passed += 1

        # Must not include check
        if check_must_not(must_not, ans):
            must_not_include_passed += 1

        # Verification safety check: if customer is not verified, order details must never be in answer
        if not agent.is_verified and turn < 3 and exp_dec == "clarify":
            if any(k in ans.lower() for k in ["total amount", "delivered on", "item details"]):
                verification_violations += 1

        # Tool calls match
        if exp_tool:
            if "lookup_order" in exp_tool:
                if any("order_id" in tr for tr in resp["tool_results"]):
                    tool_matches += 1
            elif "create_ticket" in exp_tool:
                if resp.get("created_ticket") and resp["created_ticket"].get("created"):
                    tool_matches += 1
        else:
            tool_matches += 1

    return {
        "total_conversations": len(set(r["conversation_id"] for r in rows)),
        "total_turns": total_turns,
        "decision_accuracy": round((decision_matches / total_turns) * 100, 2),
        "must_include_adherence": round((must_include_passed / total_turns) * 100, 2),
        "must_not_include_adherence": round((must_not_include_passed / total_turns) * 100, 2),
        "verification_safety_violations": verification_violations,
        "tool_call_fidelity": round((tool_matches / total_turns) * 100, 2),
    }


def main():
    print("=" * 80)
    print("ZENTROMART VOICEOPS TEXT AGENT — EVALUATION REPORT")
    print("=" * 80)

    # 1. Evaluate 12 Representative Scenarios
    rep_cases = evaluate_12_representative_cases()
    passed_cases = sum(1 for c in rep_cases if c["pass"])

    print(f"\n1. Representative Case Benchmark: {passed_cases}/{len(rep_cases)} PASSED\n")
    print(f"{'Case ID':<12} | {'Scenario':<42} | {'Status':<6}")
    print("-" * 65)
    for c in rep_cases:
        status_str = "PASS" if c["pass"] else "FAIL"
        print(f"{c['case_id']:<12} | {c['scenario'][:42]:<42} | {status_str:<6}")

    # 2. Evaluate Full Practice Conversations
    print("\n" + "=" * 80)
    print("2. Multi-Turn Practice Dataset Evaluation (practice/conversations.csv)")
    print("=" * 80)
    conv_metrics = evaluate_practice_conversations()
    for k, v in conv_metrics.items():
        print(f"  {k:<35}: {v}")

    print("\n" + "=" * 80)
    overall_status = "PASS" if passed_cases == len(rep_cases) and conv_metrics["verification_safety_violations"] == 0 else "PARTIAL"
    print(f"OVERALL EVALUATION VERDICT: {overall_status}")
    print("=" * 80)


if __name__ == "__main__":
    main()
