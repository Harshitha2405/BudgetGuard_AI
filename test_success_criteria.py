import json, os, sys, threading, urllib.request, urllib.error

API_URL = os.environ.get("API_URL")  # e.g. https://xxxx.execute-api.us-east-1.amazonaws.com/v1
API_KEY = os.environ.get("API_KEY")

if not API_URL or not API_KEY:
    print("Set API_URL and API_KEY environment variables first.")
    sys.exit(1)


def call(session_id="default", model="gpt-4o-mini", expect_status=None, label=""):
    req = urllib.request.Request(
        f"{API_URL}/chat/completions",
        data=json.dumps({"model": model, "messages": [{"role": "user", "content": "Say OK"}]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-api-key": API_KEY, "x-session-id": session_id},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status, body = resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        status, body = e.code, json.loads(e.read().decode("utf-8"))
    result = "PASS" if (expect_status is None or status == expect_status) else "FAIL"
    print(f"[{result}] {label}: HTTP {status} - {body.get('error') or body.get('_governance') or ''}")
    return status, body


print("== Test 1: Concurrent calls from the same agent ==")
threads = [threading.Thread(target=call, kwargs={"label": f"concurrent-{i}"}) for i in range(3)]
for t in threads: t.start()
for t in threads: t.join()
print("Check DynamoDB: spend_month should reflect all 3 calls, no lost updates.\n")

print("== Test 2/3: Warning at 80%, hard block at 100% ==")
print("Lower the agent's limit_month via register.py, then call repeatedly to approach it.")
call(label="approaching-limit")
call(expect_status=429, label="over-limit-call")

print("\n== Test 4: Session budget close ==")
call(session_id="test-session-1", label="session-call-1")
call(session_id="test-session-1", expect_status=402, label="session-call-2-should-402")

print("\n== Test 5: Model substitution ==")
status, body = call(model="gpt-4o", label="model-substitution-check")
print("Check body['_governance']['model_substituted'] and model_used.")

print("\n== Bonus: Runaway detector ==")
call(label="runaway-trigger")
print("Check DynamoDB - agent status should flip to PAUSED; next call should return 403.")
