import os
import sys
import datetime
import subprocess

# Ensure src is in python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(BASE_DIR, "src"))

from core import config

def log(msg: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    
    log_file = os.path.join(config.DATA_DIR, "daily_scheduler.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def main():
    force = "--force" in sys.argv
    today_str = datetime.date.today().isoformat()
    last_run_file = os.path.join(config.DATA_DIR, "last_daily_run.txt")
    
    log("=" * 60)
    log("SCHOLARSHIPS HUNTER - DAILY AUTOMATED RUNNER")
    log("=" * 60)
    
    if os.path.exists(last_run_file) and not force:
        try:
            with open(last_run_file, "r", encoding="utf-8") as f:
                last_run = f.read().strip()
            if last_run == today_str:
                log(f"[SKIP] Scholarships Hunter has already executed today ({today_str}). Exiting cleanly.")
                log("=" * 60)
                return 0
        except Exception as e:
            log(f"[WARNING] Could not read last run file: {e}")

    log(f"[*] Starting daily sweep for date: {today_str} (Force: {force})...")
    
    python_exe = sys.executable
    run_all_script = os.path.join(BASE_DIR, "run_all.py")
    deep_eval_script = os.path.join(BASE_DIR, "src", "utils", "deep_evaluator.py")
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    try:
        # Step 1: Run run_all.py (Ingest fresh scholarships from all 8 portals + process backlog)
        log("[Step 1/2] Running multi-source orchestrator (run_all.py)...")
        proc = subprocess.run([python_exe, run_all_script], cwd=BASE_DIR, env=env)
        
        if proc.returncode != 0:
            log(f"[WARNING] run_all.py exited with returncode: {proc.returncode}")
        else:
            log("[Step 1/2 OK] Ingestion & backlog evaluation finished.")
            
        # Step 2: Run daily deep check batch of up to 100 unchecked high-scoring opportunities
        log("[Step 2/2] Running Deep Website Evaluator (Batch of 100 rows)...")
        deep_proc = subprocess.run(
            [python_exe, deep_eval_script, "--auto", "--all-sources", "--limit", "100"],
            cwd=BASE_DIR,
            env=env
        )
        
        if deep_proc.returncode == 0:
            log("[Step 2/2 OK] Daily 100-row deep evaluation completed successfully.")
        else:
            log(f"[WARNING] Deep evaluator exited with returncode: {deep_proc.returncode}")
            
        # Record successful daily execution date
        with open(last_run_file, "w", encoding="utf-8") as f:
            f.write(today_str)
            
        log("[SUCCESS] All daily tasks finished. Tracker updated.")
        log("=" * 60)
        return 0
    except Exception as ex:
        log(f"[FATAL] Failed to execute daily runner: {ex}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
