import sys
import os
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Ensure src is in the python path
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

async def stream_output(name, stream, is_stderr=False):
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode('utf-8', errors='replace').rstrip()
        if text:
            prefix = f"[{name} ERROR]" if is_stderr else f"[{name}]"
            print(f"{prefix} {text}", flush=True)

async def run_pipeline(name, command):
    print(f"[{name}] [*] Starting pipeline...", flush=True)
    
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    
    # Run the command asynchronously with real-time output streaming
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    await asyncio.gather(
        stream_output(name, process.stdout, is_stderr=False),
        stream_output(name, process.stderr, is_stderr=True)
    )
    await process.wait()
    
    if process.returncode == 0:
        print(f"[{name}] [OK] Finished successfully.", flush=True)
    else:
        print(f"[{name}] [FAIL] Failed with exit code {process.returncode}.", flush=True)

async def main():
    print("=" * 60, flush=True)
    print(" STARTING ASYNC SCHOLARSHIPS HUNTER ORCHESTRATOR ", flush=True)
    print(" Running all 8 multi-source scrapers concurrently...", flush=True)
    print("=" * 60, flush=True)
    
    python_exe = sys.executable
    
    # Define the 8 target pipelines to run in parallel
    pipelines = [
        run_pipeline("CatchThatScholarship", [python_exe, "src/scrapers/catchthatscholarship.py"]),
        run_pipeline("GradSchoolShopper", [python_exe, "src/scrapers/gradschoolshopper.py"]),
        run_pipeline("WhatsApp", [python_exe, "src/main.py", "--mode", "live", "--channel", "all", "--limit", "25"]),
        run_pipeline("ProFellow", [python_exe, "src/scrapers/profellow.py", "--no-eval"]),
        run_pipeline("WeMakeScholars", [python_exe, "src/scrapers/wemakescholars.py", "--pages", "3", "--no-eval"]),
        run_pipeline("ScholarshipsCorner", [python_exe, "src/scrapers/scholarshipscorner.py", "--pages", "2", "--no-eval"]),
        run_pipeline("MastersPortal", [python_exe, "src/scrapers/mastersportal.py", "--pages", "1", "--no-eval"]),
        run_pipeline("HussainSilat", [python_exe, "src/scrapers/hussainsilat.py", "--no-eval"])
    ]
    
    # Run them all concurrently
    await asyncio.gather(*pipelines)
    
    # Run backlog evaluation if new opportunities were queued
    backlog_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'scraped_backlog.json')
    if os.path.exists(backlog_path):
        try:
            import json
            with open(backlog_path, 'r', encoding='utf-8') as f:
                pending = json.load(f)
            if len(pending) > 0:
                print(f"\n[Orchestrator] Evaluating {len(pending)} newly queued opportunities with rotating AI pool...", flush=True)
                await run_pipeline("BacklogEvaluator", [python_exe, "src/main.py", "--mode", "backlog"])
        except Exception as e:
            print(f"[Orchestrator] Backlog evaluation notice: {e}", flush=True)
    
    print("\n" + "=" * 60, flush=True)
    print(" ALL ASYNC PIPELINES FINISHED ", flush=True)
    print(" Data safely exported to scholarships_tracker.xlsx and processed_history.db", flush=True)
    print("=" * 60, flush=True)

if __name__ == "__main__":
    # Windows fix for asyncio (Proactor is default on Python 3.8+)
    if sys.platform == 'win32' and sys.version_info < (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
