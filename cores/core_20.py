# cores/core_20.py
# Core 20 - Self-Upgrade Engine
#
# Two completely separate lanes, deliberately kept apart:
#
# LANE 1 - Daily behavioral learning: continuous, automatic, NO
#          confirmation. Pure memory/preference storage — never
#          touches code. This is what makes Zephyr/Altair feel more
#          human over time.
#
# LANE 2 - Code self-modification: ALWAYS Tier 3 in Core 19 — every
#          call into apply_change() must come after explicit user
#          confirmation. Always backs up first, validates syntax
#          before writing anything, verifies the new version actually
#          loads, and automatically rolls back if it doesn't.
#
# Core 20 itself never decides confirmation is unnecessary — that
# gate lives entirely in Core 19. This file just does the actual
# work once permission has already been granted.

import os
import ast
import json
import shutil
import time
import importlib.util


class Core20SelfUpgrade:
    """
    Phase 2 - Core 20
    -------------------
    Responsibility:
    - Lane 1: store/recall learned behavioral patterns, no gating
    - Lane 2: safely propose, apply, verify, and (if needed) roll
      back real code changes — but only ever called after Core 19
      has already confirmed Tier 3 with the user
    """

    def __init__(self, backup_dir="data/self_upgrade_backups", memory_file="data/self_upgrade_memory.json"):
        self.backup_dir = backup_dir
        self.memory_file = memory_file
        os.makedirs(self.backup_dir, exist_ok=True)
        memory_dir = os.path.dirname(self.memory_file)
        if memory_dir:
            os.makedirs(memory_dir, exist_ok=True)
        self._load_memory()
        print("[Core 20] Self-upgrade engine initialized")

    # ==========================
    # LANE 1: Daily behavioral learning — no confirmation, ever
    # ==========================
    def _load_memory(self):
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.behavior_memory = json.load(f)
                    return
            except Exception as e:
                print(f"[Core 20] Memory load error: {e}")
        self.behavior_memory = {}

    def _save_memory(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.behavior_memory, f, indent=2)
        except Exception as e:
            print(f"[Core 20] Memory save error: {e}")

    def learn(self, category: str, key: str, value):
        """No confirmation needed — this is pure memory, never code.
        Real-life example: like a person naturally remembering you
        take your coffee black, without asking permission to
        remember it every single time."""
        if category not in self.behavior_memory:
            self.behavior_memory[category] = {}
        self.behavior_memory[category][key] = {
            "value": value,
            "learned_at": time.time(),
        }
        self._save_memory()
        print(f"[Core 20] Learned: {category}.{key} = {value}")

    def recall(self, category: str, key: str, default=None):
        entry = self.behavior_memory.get(category, {}).get(key)
        return entry["value"] if entry else default

    def get_all_learned(self, category: str = None):
        if category:
            return self.behavior_memory.get(category, {})
        return self.behavior_memory

    # ==========================
    # LANE 2: Code self-modification — ALWAYS Tier 3, gated by Core 19
    # ==========================
    def propose_change(self, target_file: str, new_content: str) -> dict:
        """Step 1 — validates BEFORE anything touches the real file
        or a confirmation question is even asked. If the proposed
        code is broken, there's no point asking 'are you sure?' at
        all — this lets Core 19 refuse before bothering the user."""
        if not os.path.exists(target_file):
            return {"success": False, "message": f"Target file not found: {target_file}"}

        valid, error = self._validate_syntax(new_content)
        if not valid:
            return {"success": False, "message": f"Proposed code has a syntax error: {error}"}

        return {"success": True, "message": "Proposal is syntactically valid and ready for confirmation"}

    def _validate_syntax(self, code: str):
        try:
            ast.parse(code)
            return True, None
        except SyntaxError as e:
            return False, str(e)

    def apply_change(self, target_file: str, new_content: str) -> dict:
        """Step 2 — only ever called AFTER Core 19 has confirmed
        Tier 3 with the user. Backs up first, applies, verifies the
        result actually loads as real Python (not just valid syntax
        — genuinely importable), and rolls back automatically if it
        doesn't, so a bad change can never leave the system broken."""
        valid, error = self._validate_syntax(new_content)
        if not valid:
            return {"success": False, "message": f"Refused — invalid syntax: {error}"}

        backup_path = self._backup(target_file)
        if not backup_path:
            return {"success": False, "message": "Could not create a backup — refusing to modify without one"}

        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            return {"success": False, "message": f"Write failed: {e}"}

        loads_ok, detail = self._verify_loads(target_file)
        if not loads_ok:
            restored = self._restore(backup_path, target_file)
            return {
                "success": False,
                "message": (
                    f"New version failed to load ({detail}) — "
                    f"{'automatically rolled back to the previous working version' if restored else 'ROLLBACK ALSO FAILED, manual recovery needed from ' + backup_path}"
                ),
            }

        result = {"success": True, "message": "Change applied and verified successfully", "backup": backup_path}
        if detail:  # pyflakes-not-installed caveat, still worth surfacing on success
            result["message"] += f" (Note: {detail})"
        return result

    def _backup(self, target_file: str):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(target_file)
            backup_path = os.path.join(self.backup_dir, f"{filename}.{timestamp}.bak")
            shutil.copy2(target_file, backup_path)
            print(f"[Core 20] Backed up {target_file} -> {backup_path}")
            return backup_path
        except Exception as e:
            print(f"[Core 20] Backup failed: {e}")
            return None

    def _restore(self, backup_path: str, target_file: str) -> bool:
        try:
            shutil.copy2(backup_path, target_file)
            print(f"[Core 20] Rolled back {target_file} from {backup_path}")
            return True
        except Exception as e:
            print(f"[Core 20] ROLLBACK FAILED: {e} — manual recovery needed from {backup_path}")
            return False

    def _verify_loads(self, target_file: str):
        """Two layers, in order of how thorough they are:

        1. pyflakes static analysis (if installed) — catches
           undefined names EVEN INSIDE function bodies that never
           get called, like `return some_name_that_does_not_exist`.
           This is real static analysis, not execution — it reads
           the code without running any of it.

        2. Fallback: actually importing the module. This only
           proves the file loads without crashing at import time —
           it does NOT prove every function inside it works
           correctly, since Python doesn't evaluate a function's
           body until that function is actually called. A bug
           living only inside an uncalled function's body can slip
           past this fallback. This is a real, known limitation —
           installing pyflakes (`pip install pyflakes` on the
           laptop, not in this sandbox) closes that gap.
        """
        try:
            import pyflakes.api
            import pyflakes.reporter
            import io

            with open(target_file, "r", encoding="utf-8") as f:
                code = f.read()

            output = io.StringIO()
            reporter = pyflakes.reporter.Reporter(output, output)
            error_count = pyflakes.api.check(code, target_file, reporter)

            if error_count > 0:
                return False, f"pyflakes found issues:\n{output.getvalue().strip()}"

            # pyflakes passed — still confirm it actually imports too,
            # since pyflakes checks code correctness, not e.g. missing
            # runtime dependencies.
            return self._try_import(target_file)

        except ImportError:
            # pyflakes not installed — fall back, but do NOT claim
            # this is equivalent. The caller sees the caveat in the
            # returned message.
            loads_ok, error = self._try_import(target_file)
            if not loads_ok:
                return False, error
            return True, (
                "NOTE: pyflakes isn't installed, so this only confirmed the file "
                "imports without crashing — it did NOT check whether every function "
                "inside it is actually correct. Install pyflakes for real verification: "
                "pip install pyflakes"
            )

    def _try_import(self, target_file: str):
        try:
            spec = importlib.util.spec_from_file_location("_core20_verify_module", target_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return True, None
        except Exception as e:
            return False, str(e)

    # ==========================
    # TWO-FACTOR PHONE CONFIRMATION (new)
    #
    # A spoken "yes" alone is no longer enough to authorize a
    # self-upgrade — voice cloning makes that channel untrustworthy
    # on its own. Every self-upgrade action now requires a SECOND,
    # independent confirmation on the phone before anything is
    # actually applied. Fails closed: no phone response ever means
    # no upgrade, never "proceed anyway."
    #
    # An explicit "No, it's not me" tap is a deliberate signal and
    # escalates (lock + intruder detection, wired in Core 18). A
    # silent timeout does NOT escalate — going quiet just means
    # you were asleep or busy, not necessarily an intruder, so it
    # only cancels the pending upgrade rather than raising an alarm.
    # ==========================

    PHONE_CONFIRMATION_TIMEOUT_SECONDS = 90

    def __init_phone_confirmation_state(self):
        # Called lazily so existing __init__ callers don't need updating.
        if not hasattr(self, "pending_upgrade_confirmation"):
            self.pending_upgrade_confirmation = None

    def request_upgrade_confirmation(self, description: str, target_file: str, new_content: str, request_id: str) -> dict:
        """Called once the SPOKEN confirmation has already been
        answered 'yes' — this does NOT apply anything yet. It stages
        the proposed change and returns what should be pushed to the
        phone. The actual apply only happens in confirm_from_phone()."""
        self.__init_phone_confirmation_state()

        valid, error = self._validate_syntax(new_content)
        if not valid:
            return {"success": False, "message": f"Refused before even asking the phone — invalid syntax: {error}"}

        now = time.time()
        self.pending_upgrade_confirmation = {
            "request_id": request_id,
            "description": description,
            "target_file": target_file,
            "new_content": new_content,
            "requested_at": now,
        }

        local_time = time.localtime(now)
        push_payload = {
            "request_id": request_id,
            "description": description,
            "date": time.strftime("%d/%m/%Y", local_time),
            "time": time.strftime("%H:%M:%S", local_time),
        }
        print(f"[Core 20] Staged upgrade '{description}' — waiting for phone confirmation (id={request_id})")
        return {"success": True, "message": "Waiting for phone confirmation", "push_payload": push_payload}

    def has_pending_upgrade_confirmation(self) -> bool:
        self.__init_phone_confirmation_state()
        self._expire_upgrade_if_stale()
        return self.pending_upgrade_confirmation is not None

    def _expire_upgrade_if_stale(self):
        if not self.pending_upgrade_confirmation:
            return
        age = time.time() - self.pending_upgrade_confirmation["requested_at"]
        if age > self.PHONE_CONFIRMATION_TIMEOUT_SECONDS:
            desc = self.pending_upgrade_confirmation["description"]
            print(f"[Core 20] Phone confirmation for '{desc}' timed out after {round(age)}s — "
                  f"cancelling (fail-closed, no escalation — this is a timeout, not a denial)")
            self.pending_upgrade_confirmation = None

    def confirm_from_phone(self, request_id: str) -> dict:
        """Phone tapped 'Yes, it's me, I confirm the upgrade'. Only
        NOW does the actual code change get applied — this is the
        real gate, not the spoken yes."""
        self.__init_phone_confirmation_state()
        self._expire_upgrade_if_stale()

        pending = self.pending_upgrade_confirmation
        if not pending or pending["request_id"] != request_id:
            return {"success": False, "message": "No matching pending upgrade (it may have expired)"}

        self.pending_upgrade_confirmation = None
        print(f"[Core 20] Phone CONFIRMED upgrade: {pending['description']}")
        return self.apply_change(pending["target_file"], pending["new_content"])

    def deny_from_phone(self, request_id: str) -> dict:
        """Phone tapped 'No, it's not me' — a deliberate signal, not
        a timeout. Discards the pending upgrade AND returns a flag
        telling the caller (main_app/Core 18 wiring) to lock the
        laptop and enable intruder detection."""
        self.__init_phone_confirmation_state()

        pending = self.pending_upgrade_confirmation
        if not pending or pending["request_id"] != request_id:
            return {"success": False, "message": "No matching pending upgrade", "should_escalate": False}

        self.pending_upgrade_confirmation = None
        print(f"[Core 20] Phone DENIED upgrade: {pending['description']} — this was NOT authorized, escalating")
        return {
            "success": True,
            "message": "Upgrade cancelled and flagged as unauthorized",
            "should_escalate": True,  # caller should call core.lock() + intruder_detector.enable()
        }

    # ==========================
    # DEPLOY (new) — the final step after a self-upgrade has been
    # fully applied AND verified by BOTH the spoken and phone
    # confirmation. Commits and pushes the real change to git.
    #
    # Render (or any git-connected host) typically auto-redeploys on
    # push by default — that alone is usually enough. An optional
    # deploy_hook_url can also be set for an explicit, direct trigger
    # as a backup, in case auto-deploy isn't enabled on that service.
    #
    # A failure here does NOT undo the code change itself — the file
    # was already written and verified locally by apply_change(). A
    # git/deploy failure is reported as its own separate outcome, not
    # mixed up with whether the actual code change succeeded.
    # ==========================

    def deploy_change(self, target_file: str, description: str, repo_dir: str = None,
                       deploy_hook_url: str = None, render_relevant_files: tuple = ("zephyr_cloud_server.py",)) -> dict:
        """Call this AFTER apply_change() (or confirm_from_phone(),
        which calls apply_change() internally) has already succeeded.
        repo_dir defaults to the target file's own directory.

        deploy_hook_url is read from the RENDER_DEPLOY_HOOK_URL
        environment variable by default — same pattern this project
        already uses for FIREBASE_KEY_JSON — rather than being
        hardcoded here. This matters more than usual for this file
        specifically, since Core 20 is exactly the kind of file its
        own self-upgrade automation could modify and push to git;
        a hardcoded secret here would end up sitting in git history."""
        import subprocess

        if deploy_hook_url is None:
            deploy_hook_url = os.environ.get("RENDER_DEPLOY_HOOK_URL")

        repo_dir = repo_dir or os.path.dirname(os.path.abspath(target_file)) or "."
        filename = os.path.basename(target_file)

        commit_message = f"Self-upgrade: {description}"

        try:
            add_result = subprocess.run(
                ["git", "add", target_file], cwd=repo_dir,
                capture_output=True, text=True, timeout=15,
            )
            if add_result.returncode != 0:
                return {"success": False, "message": f"git add failed: {add_result.stderr.strip()}"}

            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message], cwd=repo_dir,
                capture_output=True, text=True, timeout=15,
            )
            if commit_result.returncode != 0:
                # "nothing to commit" isn't really a failure — the
                # file may already match what's committed
                if "nothing to commit" in commit_result.stdout.lower():
                    print("[Core 20] Nothing new to commit — file already matches git history")
                else:
                    return {"success": False, "message": f"git commit failed: {commit_result.stderr.strip()}"}

            push_result = subprocess.run(
                ["git", "push"], cwd=repo_dir,
                capture_output=True, text=True, timeout=60,
            )
            if push_result.returncode != 0:
                return {
                    "success": False,
                    "message": f"Code was updated and committed locally, but git push failed: {push_result.stderr.strip()}",
                }

            print(f"[Core 20] Pushed to git: {commit_message}")

        except FileNotFoundError:
            return {"success": False, "message": "git is not installed or not on PATH"}
        except subprocess.TimeoutExpired:
            return {"success": False, "message": "git operation timed out (network issue?)"}
        except Exception as e:
            return {"success": False, "message": f"git operation failed: {e}"}

        # Explicit Render deploy hook — optional backup on top of
        # auto-deploy-on-push, only relevant for files Render
        # actually runs (laptop-only cores have nothing to do with it).
        if deploy_hook_url and filename in render_relevant_files:
            try:
                import requests
                response = requests.post(deploy_hook_url, timeout=15)
                if response.status_code == 200:
                    print(f"[Core 20] Render deploy hook triggered for {filename}")
                    return {"success": True, "message": "Pushed to git and explicitly triggered Render redeploy"}
                else:
                    return {
                        "success": True,
                        "message": f"Pushed to git successfully, but the Render deploy hook returned "
                                   f"status {response.status_code} — auto-deploy-on-push should still handle it "
                                   f"if that's enabled on the service",
                    }
            except Exception as e:
                return {
                    "success": True,
                    "message": f"Pushed to git successfully, but calling the Render deploy hook failed ({e}) — "
                               f"auto-deploy-on-push should still handle it if that's enabled on the service",
                }

        return {"success": True, "message": "Pushed to git — Render will auto-redeploy if that's enabled on the service"}


# --------------------------------------------------
# Example usage — run this file directly to test Core 20 by itself,
# same pattern as every other core. Uses temporary throwaway files
# so nothing in your real project ever gets touched by this demo.
# --------------------------------------------------
if __name__ == "__main__":
    import tempfile

    engine = Core20SelfUpgrade(
        backup_dir=os.path.join(tempfile.gettempdir(), "core20_demo_backups"),
        memory_file=os.path.join(tempfile.gettempdir(), "core20_demo_memory.json"),
    )

    # ---- LANE 1 demo ----
    print("\n--- Lane 1: Daily behavioral learning ---")
    engine.learn("preferences", "greeting_style", "casual")
    engine.learn("patterns", "usual_wake_time", "07:30")
    print("Recalled greeting style:", engine.recall("preferences", "greeting_style"))
    print("All learned preferences:", engine.get_all_learned("preferences"))

    # ---- LANE 2 demo — using a real temp file, never a project file ----
    print("\n--- Lane 2: Code self-modification ---")
    demo_file = os.path.join(tempfile.gettempdir(), "core20_demo_target.py")
    with open(demo_file, "w") as f:
        f.write("def greet():\n    return 'hello v1'\n")

    # A GOOD proposed change — valid syntax, should succeed end to end
    good_change = "def greet():\n    return 'hello v2'\n"
    print("Proposing a valid change:", engine.propose_change(demo_file, good_change))
    print("Applying it:", engine.apply_change(demo_file, good_change))

    # A BROKEN proposed change — invalid syntax, should be refused
    # before ever touching the real file
    broken_change = "def greet(:\n    return 'this is broken'\n"
    print("\nProposing a broken change:", engine.propose_change(demo_file, broken_change))

    # A change that's VALID syntax but would fail on load (e.g. calls
    # something that doesn't exist) — this is exactly what _verify_loads
    # exists to catch, and it should trigger an automatic rollback
    runtime_broken_change = "def greet():\n    return this_name_does_not_exist_anywhere\n"
    print("\nApplying a syntactically-valid-but-broken-on-load change:")
    result = engine.apply_change(demo_file, runtime_broken_change)
    print(result)

    with open(demo_file) as f:
        print("\nFile content after rollback (should still say 'hello v2'):")
        print(f.read())

    # ---- Two-factor phone confirmation demo ----
    print("\n--- Two-factor phone confirmation ---")
    with open(demo_file, "w") as f:
        f.write("def greet():\n    return 'hello v2'\n")

    staged = engine.request_upgrade_confirmation(
        description="Update greet() to return a new message",
        target_file=demo_file,
        new_content="def greet():\n    return 'hello v3'\n",
        request_id="demo-req-1",
    )
    print("Staged (spoken yes already given, now waiting on phone):", staged)
    print("Push payload that would go to the phone:", staged["push_payload"])
    print("Pending?", engine.has_pending_upgrade_confirmation())

    # Simulate the phone tapping DENY — should escalate
    deny_result = engine.deny_from_phone("demo-req-1")
    print("\nPhone denies:", deny_result)
    print("Pending after deny?", engine.has_pending_upgrade_confirmation())

    # Simulate a fresh request, this time confirmed
    engine.request_upgrade_confirmation(
        description="Update greet() to return a new message",
        target_file=demo_file,
        new_content="def greet():\n    return 'hello v3'\n",
        request_id="demo-req-2",
    )
    confirm_result = engine.confirm_from_phone("demo-req-2")
    print("\nPhone confirms:", confirm_result)
    with open(demo_file) as f:
        print("File content after real confirmation (should say 'hello v3'):", f.read().strip())

    # Simulate a timeout — should cancel WITHOUT escalating
    engine.request_upgrade_confirmation(
        description="A request nobody answers",
        target_file=demo_file,
        new_content="def greet():\n    return 'hello v4'\n",
        request_id="demo-req-3",
    )
    engine.pending_upgrade_confirmation["requested_at"] -= (Core20SelfUpgrade.PHONE_CONFIRMATION_TIMEOUT_SECONDS + 5)
    print("\nPending after simulated timeout (should be False, no escalation logged above)?",
          engine.has_pending_upgrade_confirmation())

    # ---- Real git deploy demo — against an actual local repo ----
    print("\n--- Deploy (real git commit + push) ---")
    git_repo_dir = "/tmp/core20_git_test"
    git_target_file = os.path.join(git_repo_dir, "target.py")

    with open(git_target_file, "w") as f:
        f.write("def greet(): return 'v2 - upgraded by core 20'\n")

    deploy_result = engine.deploy_change(
        target_file=git_target_file,
        description="Demo upgrade via Core 20",
        repo_dir=git_repo_dir,
    )
    print("Deploy result:", deploy_result)

    import subprocess
    log = subprocess.run(["git", "log", "--oneline", "-3"], cwd=git_repo_dir, capture_output=True, text=True)
    print("\nReal git log after deploy:")
    print(log.stdout)

    # Cleanup
    os.remove(demo_file)
    print("\nDemo complete — temp files cleaned up.")