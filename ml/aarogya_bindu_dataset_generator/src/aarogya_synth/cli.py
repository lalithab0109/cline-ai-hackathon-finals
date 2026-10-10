"""Command-line interface.

    python -m aarogya_synth generate --config configs/pilot.json --output aarogya_synthetic_dataset
    python -m aarogya_synth generate ... --append --num-base-samples 50 --generation-seed 99
    python -m aarogya_synth validate --dataset aarogya_synthetic_dataset
    python -m aarogya_synth report   --dataset aarogya_synthetic_dataset
    python -m aarogya_synth inspect-mapping --config configs/pilot.json
    python -m aarogya_synth all --config configs/pilot.json --output aarogya_synthetic_dataset

Exit codes: 0 success, 1 validation failure, 2 configuration/generation error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import DISCLAIMER, __version__
from .config import ConfigError, load_config

log = logging.getLogger("aarogya_synth")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aarogya_synth", description=f"Aarogya Bindu synthetic dataset generator. {DISCLAIMER}")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    def gen_args(sp):
        sp.add_argument("--config", type=Path, help="JSON config (default: built-in defaults)")
        sp.add_argument("--output", type=Path, default=Path("aarogya_synthetic_dataset"), help="dataset folder")
        sp.add_argument("--num-base-samples", type=int, help="override num_base_samples")
        sp.add_argument("--generation-seed", type=int, help="override generation_seed")
        sp.add_argument("--split-seed", type=int, help="override split_seed")
        sp.add_argument("--append", action="store_true", help="add a new batch to an existing dataset")

    gen_args(sub.add_parser("generate", help="generate (or append to) a dataset"))
    v = sub.add_parser("validate", help="run quality checks on a dataset")
    v.add_argument("--dataset", type=Path, default=Path("aarogya_synthetic_dataset"))
    v.add_argument("--rerender", type=int, default=12, help="rows to re-render for reproducibility (0 = skip)")
    r = sub.add_parser("report", help="create preview grid, plots and summaries")
    r.add_argument("--dataset", type=Path, default=Path("aarogya_synthetic_dataset"))
    m = sub.add_parser("inspect-mapping", help="print the color mapping table")
    m.add_argument("--config", type=Path)
    m.add_argument("--points", type=int, default=15)
    a = sub.add_parser("all", help="generate + validate + report")
    gen_args(a)
    a.add_argument("--rerender", type=int, default=12)
    return p


def _load_cfg(args):
    cfg = load_config(args.config)
    for attr, key in (("num_base_samples", "num_base_samples"), ("generation_seed", "generation_seed"),
                      ("split_seed", "split_seed")):
        val = getattr(args, attr, None)
        if val is not None:
            setattr(cfg, key, val)
    cfg.validate()
    return cfg


def _validate(dataset: Path, rerender: int) -> int:
    from .validation import run_validation

    ok, checks = run_validation(dataset, rerender=rerender)
    for c in checks:
        print(f"[{c.status:4}] {c.name}" + (f" - {c.details[0][:160]}" if c.details else ""))
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}  (report: {dataset / 'reports' / 'validation_report.md'})")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "inspect-mapping":
            from .color_mapping import build_mapping

            cfg = load_config(args.config)
            mp = build_mapping(cfg.mapping, cfg.config_dir)
            print(json.dumps(mp.describe(), indent=2))
            for row in mp.table(args.points):
                print(row)
            return 0
        if args.command in ("generate", "all"):
            from .generate import generate_dataset
            from .readme import write_dataset_readme

            cfg = _load_cfg(args)
            generate_dataset(cfg, args.output, append=args.append)
            write_dataset_readme(args.output)
            if args.command == "generate":
                print(f"Dataset written to {args.output.resolve()}. Next: validate and report.")
                return 0
        if args.command in ("report", "all"):
            if args.command == "all":
                code = _validate(args.output, args.rerender)
                if code:
                    return code
            from .reports import generate_reports

            target = args.output if args.command == "all" else args.dataset
            for pth in generate_reports(target):
                print(f"wrote {pth}")
            return 0
        if args.command == "validate":
            return _validate(args.dataset, args.rerender)
    except ConfigError as exc:
        log.error("configuration error: %s", exc)
        return 2
    except Exception as exc:  # GenerationError and unexpected errors: stop with a clear message
        from .generate import GenerationError

        if isinstance(exc, GenerationError):
            log.error("generation stopped: %s", exc)
            return 2
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
