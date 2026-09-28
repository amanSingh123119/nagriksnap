"""Process due NagrikSnap notification outbox rows once. Schedule this script externally."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database as db
from main import send_sms


def run(limit=25):
    rows = db.claim_due_notifications(limit)
    sent = failed = 0
    for row in rows:
        try:
            result = send_sms(row["recipient"], row["message"])
            ok = bool(result and result.get("success"))
            mode = "simulated" if (result or {}).get("simulated") else "provider"
            error = "" if ok else str((result or {}).get("error") or (result or {}).get("message") or "Provider rejected delivery")
        except Exception as exc:
            ok, error, mode = False, str(exc), "provider"
        db.finish_notification(row["id"], ok, error, mode)
        if ok:
            sent += 1
        else:
            failed += 1
    simulated = sum(1 for row in rows if row.get("delivery_mode") == "simulated")
    print(f"Processed {len(rows)} outbox item(s): {sent} accepted, {failed} retry/failure; previously simulated rows in batch: {simulated}")
    return sent, failed


if __name__ == "__main__":
    run(int(os.getenv("OUTBOX_BATCH_SIZE", "25")))
