"""The builder: reads a bank's brief and builds a Freya phone agent, with no manual step.

    source env.sh
    python3 builder/build.py <case_folder> <mock_url>                                      # the final: a folder of bank documents
    python3 builder/build.py <brief_path> <tool_api_path>                                  # a single brief with its tool API file
    python3 builder/build.py briefs/brief-a.md tools/openapi.json --practice A             # practice
    python3 builder/build.py briefs/brief-b.md tools/openapi.json --base briefs/brief-a.md --practice B

Every run works in a fresh folder runs/<slot>-<time>/ that holds only this run's inputs, so nothing from an earlier
run (another brief's generator or workflow) can leak into it. Claude runs there through the Claude Agent SDK with the
skill in .claude/skills. The run is cut at RUN_LIMIT_MIN minutes; the last saved workflow is exported either way.

Writes into the run folder:
    trace.md        start and end time, every model call (model and a one-line purpose), what was created on Freya, every test
    trace.jsonl     every SDK message, raw
    <slot>.workflow.json   the exported phone agent, as submitted
    result.json     workflow_id, agent_id, the tests of this run
"""
import argparse, asyncio, dataclasses, json, os, pathlib, shutil, sys, time

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, ToolUseBlock, query

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
import freya

RUN_LIMIT_MIN = float(os.environ.get("BUILDER_RUN_LIMIT_MIN", "28"))   # the rules allow 30 minutes per brief, tests included
MODEL = os.environ.get("BUILDER_MODEL", "claude-opus-5-5")
FALLBACK_MODEL = os.environ.get("BUILDER_FALLBACK_MODEL", "claude-sonnet-5-5")   # used for the rest of the run after a model error
SPEC_UNTIL_MIN, BUILD_UNTIL_MIN = 9, 20                                  # phase ends, in minutes from the start of the run
SPEC_SECTIONS = ["call variables", "stages", "who is on the line", "identity", "account", "calendar", "calculations", "offers",
                 "confirmation", "special situations", "tools", "closing", "several products", "language", "exact sentences",
                 "open questions", "test scenarios"]                    # the section names the skill asks for

BUDGET_PY = '''"""Prints the minutes left in this builder run. Check it before you start a test."""
import json, time
d = json.load(open("input/budget.json"))
left = (d["deadline"] - time.time()) / 60
print(f"{left:.1f} minutes left of {d['limit_min']:.0f}. A test run takes 2 to 15 minutes. Start one only with more than {d['min_for_test']} minutes left.")
'''


def now(): return time.strftime("%Y-%m-%d %H:%M:%S")


def to_text(src, dst_dir):
    """Write a .txt twin of a Word, PDF, Excel or RTF file so it can be read. Returns the twin's name or None."""
    import subprocess
    out = dst_dir / (src.name + ".txt"); ext = src.suffix.lower()
    try:
        if ext in (".docx", ".doc", ".rtf", ".odt", ".pages"):
            subprocess.run(["textutil", "-convert", "txt", "-output", str(out), str(src)], check=True, capture_output=True, timeout=60)
        elif ext == ".pdf":
            subprocess.run(["pdftotext", "-layout", str(src), str(out)], check=True, capture_output=True, timeout=60)
        elif ext in (".xlsx", ".xlsm", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(src, data_only=True); lines = []
            for ws in wb.worksheets:
                lines.append(f"## sheet: {ws.title}")
                for row in ws.iter_rows(values_only=True):
                    if any(c is not None for c in row): lines.append(" | ".join("" if c is None else str(c) for c in row))
            out.write_text("\n".join(lines))
        else:
            return None
        return out.name
    except Exception as e:
        out.write_text(f"(could not convert {src.name}: {e}. Read the original file.)"); return out.name


def prepare_workdir(briefs, api_file, slot, started):
    """A fresh folder with this run's inputs only. Kit tools are linked so they keep writing to the kit's results/.

    A brief may be a folder of bank documents (Markdown, Word, PDF, Excel): every file is copied into input/ with a .txt
    twin for the formats that need converting. api_file is a tool API file, or the URL of the mock bank (then None here)."""
    run = KIT / "runs" / f"{slot}-{time.strftime('%Y%m%d-%H%M%S')}"
    (run / "input").mkdir(parents=True)
    (run / "tools").mkdir()
    for b in briefs:
        b = pathlib.Path(b)
        if b.is_dir():
            for f in sorted(x for x in b.rglob("*") if x.is_file() and not x.name.startswith(".")):
                dst = run / "input" / f.relative_to(b); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(f, dst)
                to_text(f, dst.parent)
                if f.name.lower() in ("openapi.json", "openapi.yaml", "openapi.yml") and not api_file: shutil.copy(f, run / "tools" / f.name)
        else:
            shutil.copy(b, run / "input" / b.name)
    if api_file:
        shutil.copy(api_file, run / "input" / "openapi.json")
        shutil.copy(api_file, run / "tools" / "openapi.json")      # the docs and skill call it tools/openapi.json
    for name in ("run_cases.py", "score.py"): (run / "tools" / name).symlink_to(KIT / "tools" / name)
    shutil.copytree(KIT / "docs", run / "docs")
    (run / "lib").mkdir(); shutil.copy(KIT / "lib" / "calendar_kit.py", run / "lib" / "calendar_kit.py")   # tested, brief-free helpers
    (run / "examples").mkdir(); shutil.copy(KIT / "examples" / "base-agent.json", run / "examples" / "base-agent.json")
    shutil.copytree(KIT / ".claude" / "skills", run / ".claude" / "skills")
    shutil.copy(KIT / "freya.py", run / "freya.py")                 # the practice customers stay in the kit; run_cases.py reads them there
    state = KIT / ".freya-agents.json"                               # one slot keeps one workflow across runs (200-workflow limit)
    if not state.exists(): state.write_text("{}")
    (run / ".freya-agents.json").symlink_to(state)
    (run / "budget.py").write_text(BUDGET_PY)
    (run / "input" / "budget.json").write_text(json.dumps({"deadline": started + RUN_LIMIT_MIN * 60, "limit_min": RUN_LIMIT_MIN, "min_for_test": 12}))
    return run


def current_state(slot):
    return json.loads((KIT / ".freya-agents.json").read_text()).get(slot)


def chat_test_customer():
    """A customer of the bank's test system for chat checks, read from the workspace (a workflow's test_variables
    that carry test_caller_* answers). Environment, not brief content. Cached in the kit; None when there is none."""
    cache = KIT / ".chat-test-customer.json"
    if cache.exists(): return json.loads(cache.read_text()) or None
    found = None
    try:
        ws = freya.workspace_id()
        r = freya.api("GET", "/api/v2/workflow", workspaceId=ws, limit=50)
        items = r.get("workflows") or r.get("items") or r
        for w in (items if isinstance(items, list) else [])[:50]:
            tv = (freya.api("GET", f"/api/v2/workflow/{w['id']}", workspaceId=ws)["workflow"].get("workflow") or {}).get("test_variables") or {}
            if tv.get("customer_id") and any(k.startswith("test_caller_") for k in tv): found = tv; break
    except Exception:
        pass
    cache.write_text(json.dumps(found or {}))
    return found


def purpose(block):
    """One line that says what a model call was for."""
    if isinstance(block, TextBlock): return " ".join(block.text.split())[:160]
    if isinstance(block, ToolUseBlock):
        i = block.input or {}
        what = i.get("description") or i.get("file_path") or i.get("pattern") or i.get("skill") or str(i.get("command", ""))[:100]
        return f"tool {block.name}: {' '.join(str(what).split())[:140]}"
    return type(block).__name__


async def main():
    ap = argparse.ArgumentParser(description="Build a Freya phone agent from a bank's brief.")
    ap.add_argument("brief", help="the brief to build a phone agent for: a file, or a folder of the bank's documents")
    ap.add_argument("api", help="the bank's tool API file, or the URL of the mock bank the phone agent must call")
    ap.add_argument("--base", nargs="*", default=[], help="briefs this one builds on, if any")
    ap.add_argument("--slot", help="Freya slot name (default: the brief's file name without .md)")
    ap.add_argument("--practice", choices=["A", "B"], help="practice customers that fit these briefs. Leave it out for a brief they do not cover")
    a = ap.parse_args()
    a.briefs = list(a.base) + [a.brief]
    slot = a.slot or pathlib.Path(a.brief).stem
    started = time.time()
    mock_url = a.api.rstrip("/") if a.api.startswith("http") else None
    run = prepare_workdir(a.briefs, None if mock_url else a.api, slot, started)
    tester = None if mock_url else chat_test_customer()           # the workspace's test customer belongs to the practice bank
    if tester: (run / "input" / "chat_test_customer.json").write_text(json.dumps(tester, indent=1))
    log_lines_before = sum(1 for _ in open(KIT / "results" / "log.jsonl")) if (KIT / "results" / "log.jsonl").exists() else 0
    state_before = json.loads((KIT / ".freya-agents.json").read_text()).get(slot)

    def saved_since(before):
        """True when the slot was created, or got a new published version, after `before` was read."""
        return current_state(slot) not in (None, before)

    def spec_missing():
        f = run / "spec.md"
        if not f.exists() or f.stat().st_size < 2000: return "spec.md is missing or nearly empty. Write it as section 1 of the skill says."
        text = f.read_text().lower()
        missing = [x for x in SPEC_SECTIONS if x not in text]
        return f"spec.md has no section for: {', '.join(missing)}. Add them (write 'none in this brief' where one does not apply)." if missing else None

    md = open(run / "trace.md", "w"); raw = open(run / "trace.jsonl", "w")
    def tw(line): md.write(line + "\n"); md.flush()
    tw(f"# Builder trace: {slot}\n")
    tw(f"- start: {now()}")
    tw(f"- briefs: {', '.join(a.briefs)}")
    tw(f"- tool API: {a.api}")
    tw(f"- builder model: {MODEL} (Claude Agent SDK, skill build-phone-agent)")
    tw(f"- phone agent model: {freya.AGENT_LLM['model']} (set by the event, not by the builder)")
    tw(f"- run folder: {run.relative_to(KIT)}")
    tw(f"- practice customers: {'brief ' + a.practice if a.practice else 'none for this brief'}")
    tw(f"- time limit: {RUN_LIMIT_MIN:.0f} min, in phases: spec until minute {SPEC_UNTIL_MIN}, build until {BUILD_UNTIL_MIN}, test until {RUN_LIMIT_MIN:.0f}\n")
    tw("## Model calls\n")
    tw("| time | model | purpose |")
    tw("|---|---|---|")

    names = ", ".join("input/" + pathlib.Path(b).name + ("/ (a folder of documents)" if pathlib.Path(b).is_dir() else "") for b in a.briefs)
    if pathlib.Path(a.brief).is_dir(): names = "every file in input/ (the bank's documents for this case)"
    api_line = (f"The phone agent's tools call the bank's services at {mock_url} (a mock bank that follows the service contract in the documents). "
                f"Use this URL as the server for every tool; take paths, fields and values from the service contract"
                + (" and tools/openapi.json" if any((run / "tools").glob("openapi.*")) else "") + ".\n") if mock_url else \
               "The bank's tool API for these briefs: tools/openapi.json.\n"
    context = (f"Briefs: {names}. When several briefs are listed, the last one is the brief to build for and earlier ones are what it builds on.\n"
               "Word, PDF and Excel files have a .txt twin next to them; read the twin, and the original when the twin is unclear.\n"
               "The phone agent speaks the language of the bank's documents and example conversations, and uses their wording.\n"
               + api_line +
               f"Slot: {slot}. Save with this slot name and no other.\n"
               f"Work only inside the current folder. Do not read or copy files from parent folders or from earlier runs.\n")
    context += (
               "For chat checks, input/chat_test_customer.json holds call variables of a test customer in the bank's test system and the "
               "answers to its security questions (keys starting with test_caller_). The bank may not know it under this brief's tool API; "
               "if a tool says the customer is unknown, check only what you can.\n" if tester else "")
    # Brief B builds on A and its customers can have one product, so a B agent is tested on every practice customer.
    which = f"--brief {a.practice} " if a.practice == "A" else ""
    practice = (f"Practice customers for this brief: `python3 tools/run_cases.py <agent_id> {which}--out test-<n>.json`.\n" if a.practice else
                "There are no practice customers for this brief. Do not run tools/run_cases.py: its customers belong to another brief. "
                "Test with chat conversations instead (skill section 5).\n")
    # The run is split into phases that the builder enforces, so no phase can be cut short to save time for another.
    phases = [
        ("spec", SPEC_UNTIL_MIN,
         "Use the build-phone-agent skill. In this phase do ONLY its section 1: read everything and write spec.md, complete, with every section, "
         "the worked examples and the test scenarios. Do not shorten it to save time: the build and the tests have their own time after this phase. "
         "Do not write or save a workflow yet. Stop when spec.md passes the skill's 'Check before you continue'.\n" + context,
         spec_missing),
        ("build", BUILD_UNTIL_MIN,
         "Next phase. Do sections 2, 3 and 4 of the skill, working from spec.md: design the agent, generate the tools from tools/openapi.json, "
         "write build_workflow.py, run the local checks, validate, save with the slot, and do one short chat check. "
         "Do not run the tests of section 5 yet. Stop when the workflow is saved.\n" + context,
         lambda: None if saved_since(phase_state["build"]) else "The workflow is not saved yet. Fix what stops it and save it with the slot."),
        ("test", RUN_LIMIT_MIN,
         "Last phase. Do sections 5 and 6 of the skill: test the saved agent, fix what fails, and finish with the summary line. "
         f"Run `python3 budget.py` before every test.\n" + practice + context,
         lambda: None),
    ]
    model = [MODEL]
    options = lambda sid: ClaudeAgentOptions(
        cwd=run, model=model[0], skills=["build-phone-agent"], setting_sources=["project"], resume=sid,
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep", "Bash"], permission_mode="dontAsk", max_turns=150,
        env={"BASH_DEFAULT_TIMEOUT_MS": "900000", "BASH_MAX_TIMEOUT_MS": "1200000", "CLAUDE_CODE_DISABLE_BACKGROUND_TASKS": "1"},
    )
    calls, cost, stop_reason, session = 0, 0.0, "finished", None
    phase_state = {}
    raw.write(json.dumps({"start": now(), "briefs": a.briefs, "api": a.api, "slot": slot, "model": MODEL}) + "\n")

    async def drive(prompt):
        nonlocal calls, cost, session
        async for m in query(prompt=prompt, options=options(session)):
            raw.write(json.dumps({"type": type(m).__name__, **dataclasses.asdict(m)}, default=str) + "\n"); raw.flush()
            sid = getattr(m, "session_id", None) or (getattr(m, "data", None) or {}).get("session_id")
            if sid: session = sid                                  # the next phase resumes this conversation
            if isinstance(m, AssistantMessage):
                calls += 1
                for b in m.content:
                    if isinstance(b, (TextBlock, ToolUseBlock)):
                        tw(f"| {time.strftime('%H:%M:%S')} | {getattr(m, 'model', MODEL)} | {purpose(b).replace('|', '/')} |")
                    if isinstance(b, TextBlock): print(b.text, flush=True)
                    elif isinstance(b, ToolUseBlock): print(f"  [{b.name}] {str(b.input)[:120]}", flush=True)
            elif isinstance(m, ResultMessage):
                cost += m.total_cost_usd or 0

    for name, until_min, prompt, check in phases:
        phase_state[name] = current_state(slot)
        tw(f"| {time.strftime('%H:%M:%S')} | builder | **phase {name}: start** (until minute {until_min:.0f}) |")
        for attempt in range(2):                                   # one follow-up when the phase's own check fails
            left = until_min * 60 - (time.time() - started)
            if left < 30: break
            try:
                await asyncio.wait_for(drive(prompt), timeout=left)
            except asyncio.TimeoutError:
                tw(f"| {time.strftime('%H:%M:%S')} | builder | phase {name}: time is up |"); break
            except Exception as e:                                 # the build must still end with an exported agent and a trace
                tw(f"| {time.strftime('%H:%M:%S')} | builder | phase {name}: error {type(e).__name__}: {str(e)[:150]} |")
                stop_reason = f"builder error in phase {name}: {type(e).__name__}"
                if model[0] != FALLBACK_MODEL and attempt == 0:      # a usage limit or an API error: go on with the fallback model
                    model[0] = FALLBACK_MODEL
                    tw(f"| {time.strftime('%H:%M:%S')} | builder | switching to {FALLBACK_MODEL} and repeating phase {name} |")
                    prompt = f"The previous attempt at this phase stopped with an error. Continue it from the files in the folder.\n" + prompt
                    continue
                break
            problem = check()
            if not problem: break
            tw(f"| {time.strftime('%H:%M:%S')} | builder | phase {name}: check failed: {problem[:150]} |")
            prompt = problem + " Do only this, then stop."
        tw(f"| {time.strftime('%H:%M:%S')} | builder | **phase {name}: end** |")
    if time.time() - started >= RUN_LIMIT_MIN * 60 - 5: stop_reason = f"stopped at the {RUN_LIMIT_MIN:.0f}-minute limit"

    # What exists on Freya after the run, and the exported file that is submitted.
    tw("\n## Created on Freya\n")
    state_after = json.loads((KIT / ".freya-agents.json").read_text()).get(slot)
    exported = None
    if state_after:
        verb = "updated the existing workflow" if state_before else "created a new workflow"
        tw(f"- slot `{slot}`: {verb}. workflow_id `{state_after['workflow_id']}`, agent_id `{state_after['agent_id']}`, published version {state_after.get('version', 1)}")
        try:
            exported = freya.export_workflow(state_after["workflow_id"], str(run / f"{slot}.workflow.json"))
            tw(f"- exported to `{pathlib.Path(exported).relative_to(KIT)}`")
            if mock_url:                                           # the submission layout: submission/final.workflow.json
                (KIT / "submission").mkdir(exist_ok=True); shutil.copy(exported, KIT / "submission" / "final.workflow.json")
                tw("- copied to `submission/final.workflow.json`")
        except Exception as e:
            tw(f"- export failed: {e}")
    else:
        tw("- nothing was saved")

    tw("\n## Tests the builder ran on its own agent\n")
    tests = []
    if (KIT / "results" / "log.jsonl").exists():
        tests = [json.loads(l) for l in list(open(KIT / "results" / "log.jsonl"))[log_lines_before:]]
        tests = [t for t in tests if not state_after or t.get("agent_id") == state_after["agent_id"]]
    for t in tests:
        style = f", style {t['style']}" if t.get("style") else ""
        tw(f"- {t['at']}: brief {t.get('brief') or 'all'}{style}, {t['runs']} run(s): {t['passed']}/{t['total']} passed in {t['seconds']} s. Failed: {', '.join(t['failed']) or 'none'}")
    if not tests: tw("- none")

    tw("\n## End\n")
    tw(f"- end: {now()}")
    tw(f"- duration: {(time.time() - started) / 60:.1f} min")
    tw(f"- outcome: {stop_reason}")
    tw(f"- model calls: {calls}")
    tw(f"- builder cost: ${cost:.2f}")
    md.close(); raw.close()
    (run / "result.json").write_text(json.dumps({"slot": slot, **(state_after or {}), "exported": exported, "tests": tests, "stop": stop_reason,
                                                 "minutes": round((time.time() - started) / 60, 1)}, indent=1))
    print(f"\n{stop_reason}. {(time.time() - started) / 60:.1f} min. Run folder: {run}")


if __name__ == "__main__":
    asyncio.run(main())
