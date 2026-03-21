"""Tests for the afs doctor CLI command."""

from __future__ import annotations

import argparse
import json

from afs.cli.doctor import register_parsers
from afs.diagnostics import DiagnosticResult


def test_doctor_registers_parser() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_parsers(subparsers)
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"
    assert hasattr(args, "func")


def test_doctor_json_output(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        "afs.cli.doctor.run_all_checks",
        lambda config_path=None, auto_fix=False: [
            DiagnosticResult(name="config", status="ok", message="ready")
        ],
    )
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_parsers(subparsers)
    args = parser.parse_args(["doctor", "--json"])
    args.func(args)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert "checks" in parsed
    assert isinstance(parsed["checks"], list)


def test_doctor_text_output(capsys, monkeypatch) -> None:
    monkeypatch.setattr(
        "afs.cli.doctor.run_all_checks",
        lambda config_path=None, auto_fix=False: [
            DiagnosticResult(
                name="context_root",
                status="warn",
                message="missing",
                fix_available=True,
                fix_description="repair it",
            )
        ],
    )
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_parsers(subparsers)
    args = parser.parse_args(["doctor"])
    args.func(args)
    captured = capsys.readouterr()
    assert "AFS Doctor" in captured.out
