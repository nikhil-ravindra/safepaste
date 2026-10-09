"""Quick checks for Person 1's files. Run: python test_person1.py"""
import os, sys
import inspector, risk, vision

POLICY = "Never send client names, deal values, unreleased codenames like Project Falcon, or credentials."
TEXT = "Summarize: Acme Corp signed a ₹4.2 Cr deal for Project Falcon. Contact ravi@acme.in, api_key=sk-test1234567890abcdef"

print("Model:", os.environ.get("SAFEPASTE_MODEL"))
f = inspector.inspect(TEXT, POLICY)
for item in f:
    print(" ", item)
print("Gemma error:", inspector.LAST_ERROR)
print("Risk:", risk.assess(f, TEXT))

if len(sys.argv) > 1:
    print("\nScreenshot text:\n", vision.transcribe(open(sys.argv[1], "rb").read()))
    print("Vision error:", vision.LAST_ERROR)