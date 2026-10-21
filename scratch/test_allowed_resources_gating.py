import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agent.guardrails import check_site_scope
from app.tools.design_search_tools import validate_search_path
from app.database import (
    db_get_registered_sites,
    db_get_all_allowed_resources,
    db_is_path_allowed
)

def run_tests():
    print("--- 1. DATABASE RESOURCES CHECK ---")
    res = db_get_all_allowed_resources()
    print(f"Total allowed resources: {len(res)}")
    for r in res:
        print(f" - [{r['id']}] {r['name']}: {r['path']}")

    print("\n--- 2. GUARDRAILS TESTS ---")
    test_cases = [
        # Test 1: Malformed single-slash path -> MUST REJECT WITH SYNTAX ERROR (NO AUTO-FIX)
        (r"[gamuda] Tìm các file xd có chữ Break/Snack trong \172.16.44.103\design$", False, "single slash syntax error"),
        
        # Test 2: Valid allowed resource path -> MUST PASS via Allowed Resources
        (r"Tìm các file xd có chữ Break/Snack trong \\172.16.44.103\design$", True, "allowed resource match"),
        
        # Test 3: Path outside allowed resources -> MUST REJECT (Not in allowed resources)
        (r"Tìm file trong \\192.168.1.50\fake$", False, "unauthorized path"),
        
        # Test 4: Registered project query (no path) -> MUST PASS via Registered Project
        (r"[SIS Vạn Phúc] Fix bug header", True, "registered project match"),
        
        # Test 5: Known alias for registered project -> MUST PASS
        (r"Cập nhật trang SIS Gamuda Gardens", True, "registered project gamuda match"),
        
        # Test 6: Random unknown project / query -> MUST REJECT (Out of scope)
        (r"[Random Unknown] Làm việc lạ ngoài phạm vi", False, "out of scope"),
        
        # Test 7: Slash between words (e.g. SIS / SVIS) -> SHOULD NOT BE CONFUSED AS PATH
        (r"Kiểm tra tiến độ SIS / SVIS Vạn Phúc ngày 21/10/2026", True, "registered project with slash date"),
        
        # Test 8: Exempt system action -> MUST PASS
        ("xuất báo cáo tháng", True, "exempt system action")
    ]

    all_passed = True
    for msg, expected_allowed, desc in test_cases:
        res_g = check_site_scope(msg)
        is_ok = (res_g["allowed"] == expected_allowed)
        status = "PASSED" if is_ok else "FAILED"
        if not is_ok:
            all_passed = False
        print(f"[{status}] {desc}")
        print(f"   Query: {msg}")
        print(f"   Allowed: {res_g['allowed']} (expected {expected_allowed})")
        print(f"   Reason: {res_g.get('reason')}")
        if not res_g['allowed']:
            first_line = res_g.get('refusal_message', '').split('\n')[0]
            print(f"   Refusal: {first_line}")
        print()

    print("\n--- 3. DESIGN SEARCH VALIDATE_SEARCH_PATH TESTS ---")
    path_tests = [
        (r"\172.16.44.103\design$", False, "INVALID_SYNTAX"),
        (r"\\172.16.44.103\design$", True, "OK"),
        (r"\\192.168.1.50\fake$", False, "NOT_IN_ALLOWED_RESOURCES"),
        (r"C:\Windows\System32", False, "BLACKLISTED"),
    ]
    for p, exp_valid, exp_code in path_tests:
        valid, code, msg = validate_search_path(p)
        ok = (valid == exp_valid and code == exp_code)
        status = "PASSED" if ok else "FAILED"
        if not ok:
            all_passed = False
        print(f"[{status}] Path: {p} -> valid={valid}, code={code} (expected {exp_valid}, {exp_code})")

    print("\n" + ("="*50))
    print(f"OVERALL RESULT: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("="*50)

if __name__ == "__main__":
    run_tests()
