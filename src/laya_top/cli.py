import argparse
import importlib.metadata
import json
import platform
import sys
import time
from dataclasses import asdict

from . import __version__
from .collector import Collector, DemoCollector
from .config import MODEL_REPO, config_dir, discover_model, load_labels, model_dir
from .tagging import application, rule_tag


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Live processes, clear tags, local intelligence.")
    root.add_argument("--version", action="version", version=f"laya-top {__version__}")
    root.add_argument("--model", help="Local Core ML bundle; never downloaded automatically")
    root.add_argument("--no-ai", action="store_true", help="Use deterministic tags only")
    root.add_argument("--demo", action="store_true", help="Illustrative data; controls disabled")
    root.add_argument(
        "--interval", type=float, default=2, help="Refresh seconds (0.5–30; default 2)"
    )
    commands = root.add_subparsers(dest="command")
    snapshot = commands.add_parser("snapshot", help="Print a read-only JSON snapshot")
    snapshot.add_argument("--count", type=int, default=30)
    snapshot.add_argument("--json", action="store_true", help="JSON is the default output")
    doctor = commands.add_parser("doctor", help="Check dependencies, permissions and model")
    doctor.add_argument("--check-model", action="store_true", help="Load and test local inference")
    model = commands.add_parser("model", help="Manage the optional local model")
    model.add_argument("operation", choices=["download", "path"])
    return root


def main():
    root = parser()
    args = root.parse_args()
    if not 0.5 <= args.interval <= 30:
        root.error("--interval must be between 0.5 and 30 seconds")
    model = discover_model(args.model)
    if args.command == "doctor":
        from .intelligence import Intelligence

        ai = Intelligence(model, enabled=not args.no_ai)
        dependencies = {}
        for name in ("psutil", "textual", "laya-coreml"):
            try:
                dependencies[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                dependencies[name] = "not installed"
        diagnostic = {
            "version": __version__,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "dependencies": dependencies,
            "model": str(model) if model else None,
            "ai_available": ai.available,
            "ai_status": ai.detail,
            "config": str(config_dir()),
        }
        try:
            diagnostic["visible_processes"] = len(Collector().sample().processes)
        except (OSError, RuntimeError) as error:
            diagnostic["process_error"] = (
                f"{type(error).__name__}: OS process access is blocked. Run in a normal terminal."
            )
        if args.check_model:
            if not ai.available:
                root.error(ai.detail)
            from .intelligence import CoreMLBackend

            started = time.monotonic()
            try:
                backend = CoreMLBackend(model)
                diagnostic["load_seconds"] = round(time.monotonic() - started, 2)
                started = time.monotonic()
                result = backend.predict("Google Chrome")
                diagnostic["model_check"] = asdict(result)
                diagnostic["first_prediction_ms"] = round((time.monotonic() - started) * 1000, 2)
            except Exception as error:
                root.error(f"Model check failed: {type(error).__name__}: {error}")
        print(json.dumps(diagnostic, indent=2))
        return
    if args.command == "model":
        target = model or model_dir()
        if args.operation == "path":
            print(target)
            return
        try:
            from huggingface_hub import snapshot_download
        except ImportError:
            root.error("Install the laya extra on Apple Silicon, or install huggingface-hub.")
        print(f"Downloading {MODEL_REPO} to {target}", file=sys.stderr)
        snapshot_download(MODEL_REPO, local_dir=str(target))
        print(target)
        return
    if args.command == "snapshot":
        if args.count < 1:
            root.error("--count must be positive")
        collector = DemoCollector() if args.demo else Collector()
        collector.sample()
        time.sleep(0.2)
        snapshot = collector.sample()
        overrides = load_labels()
        payload = asdict(snapshot)
        payload["processes"] = [
            dict(asdict(p), application=application(p), tag=asdict(rule_tag(p, overrides)))
            for p in sorted(snapshot.processes, key=lambda p: -p.cpu)[: args.count]
        ]
        payload["demo"] = args.demo
        payload["tagging"] = "rules and saved labels (no model inference in snapshots)"
        print(json.dumps(payload, indent=2))
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        root.error("The live UI needs a terminal. Use 'laya-top snapshot' for JSON.")
    from .app import LayaTop

    LayaTop(model=model, no_ai=args.no_ai, demo=args.demo, interval=args.interval).run()
