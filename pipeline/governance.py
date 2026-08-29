"""Fail-closed artifact contracts and tamper-evident run provenance.

Keep arithmetic in deterministic stage scripts. Use this module to enforce the
boundaries between those stages: safe run paths, JSON Schema gates, semantic
checks, atomic writes, input snapshots, and a hash-chained audit log.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from pipeline.ips import parse_ips, validate_ips_weights

REPO = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO / "schemas"
MANIFEST_VERSION = "1.0"
AUDIT_GENESIS = "0" * 64

STAGE_SCHEMAS: dict[str, tuple[str, str]] = {
    "regime": ("regime.json", "regime.schema.json"),
    "cmas": ("cmas.json", "cmas.schema.json"),
    "covariance": ("covariance.json", "covariance.schema.json"),
    "pc_proposals": ("pc_proposals.json", "pc_proposals.schema.json"),
    "peer_review": ("peer_review.json", "peer_review.schema.json"),
    "final_portfolio": ("final_portfolio.json", "final_portfolio.schema.json"),
}
STAGE_ORDER = tuple(STAGE_SCHEMAS)
REQUIRED_INPUTS = ("ips", "macro", "prices")
REQUIRED_MACRO_SERIES = ("INDPRO", "CPIAUCSL", "DFF", "T10Y3M", "NFCI")
REGIME_TO_ENSEMBLE = {
    "expansion": "sharpe_weighted",
    "recovery": "sharpe_weighted",
    "late_cycle": "confidence_weighted",
    "recession": "regime_weighted",
}
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class GovernanceError(RuntimeError):
    """Base class for a fail-closed governance error."""


class SchemaGateError(GovernanceError):
    """Raised when an artifact fails its structural or semantic contract."""


class StageOrderError(GovernanceError):
    """Raised when a stage attempts to commit outside the finite-state order."""


class VerificationError(GovernanceError):
    """Raised when a completed run cannot be verified."""


def utc_now() -> str:
    """Return a stable ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_run_id(run_id: str) -> str:
    """Validate a run identifier before using it as a directory name."""
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise GovernanceError(
            "run_id must be 1-64 characters using only letters, numbers, '.', '_', or '-'"
        )
    if run_id in {".", ".."}:
        raise GovernanceError("run_id cannot be '.' or '..'")
    return run_id


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON deterministically and reject NaN/Infinity."""
    try:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SchemaGateError(f"Artifact is not strict JSON: {exc}") from exc
    return rendered.encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Replace a file atomically after flushing its bytes to disk."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: str | Path, value: Any) -> None:
    payload = json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8") + b"\n"
    atomic_write_bytes(path, payload)


def atomic_write_text(path: str | Path, value: str) -> None:
    atomic_write_bytes(path, value.encode("utf-8"))


def _json_path(parts: Sequence[Any]) -> str:
    if not parts:
        return "$"
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


def _assert_finite(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise SchemaGateError(f"{path}: non-finite number is forbidden")
    if isinstance(value, Mapping):
        for key, child in value.items():
            _assert_finite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_finite(child, f"{path}[{index}]")


def _validate_weight_map(weights: Mapping[str, Any], path: str) -> None:
    if not weights:
        raise SchemaGateError(f"{path}: weight map cannot be empty")
    values = [float(value) for value in weights.values()]
    if any(value < -1e-10 for value in values):
        raise SchemaGateError(f"{path}: long-only weights cannot be negative")
    if abs(sum(values) - 1.0) > 1e-6:
        raise SchemaGateError(f"{path}: weights must sum to 1.0")


def _semantic_validate(stage: str, payload: Mapping[str, Any]) -> None:
    """Enforce relationships that JSON Schema cannot express cleanly."""
    _assert_finite(payload)

    if stage == "regime":
        if abs(sum(payload["scores"].values()) - 1.0) > 1e-6:
            raise SchemaGateError("$.scores: regime probabilities must sum to 1.0")
        winning_regime = max(payload["scores"], key=payload["scores"].get)
        winning_score = payload["scores"][winning_regime]
        if payload["regime"] != winning_regime:
            raise SchemaGateError("$.regime: must identify the highest-probability regime")
        if not math.isclose(payload["top1_confidence"], winning_score, abs_tol=1e-10):
            raise SchemaGateError("$.top1_confidence: must equal the winning regime score")
        if payload["top1_confidence_low"] != (winning_score < 0.4):
            raise SchemaGateError(
                "$.top1_confidence_low: must reflect the 0.40 confidence threshold"
            )

    elif stage == "cmas":
        tickers = [row["ticker"] for row in payload["cmas"]]
        if len(tickers) != len(set(tickers)):
            raise SchemaGateError("$.cmas: ticker values must be unique")
        if any(row["volatility"] <= 0 for row in payload["cmas"]):
            raise SchemaGateError("$.cmas: volatility must be positive")

    elif stage == "covariance":
        import numpy as np

        tickers = payload["tickers"]
        matrix = np.asarray(payload["covariance"], dtype=float)
        n_assets = len(tickers)
        if len(tickers) != len(set(tickers)):
            raise SchemaGateError("$.tickers: values must be unique")
        if matrix.shape != (n_assets, n_assets):
            raise SchemaGateError(
                f"$.covariance: expected a {n_assets}x{n_assets} matrix, got {matrix.shape}"
            )
        if not np.allclose(matrix, matrix.T, atol=1e-10):
            raise SchemaGateError("$.covariance: matrix must be symmetric")
        if np.any(np.diag(matrix) <= 0):
            raise SchemaGateError("$.covariance: diagonal variances must be positive")
        if float(np.linalg.eigvalsh(matrix).min()) < -1e-8:
            raise SchemaGateError("$.covariance: matrix must be positive semidefinite")
        actual_condition = float(np.linalg.cond(matrix))
        if not math.isclose(
            payload["condition_number"], actual_condition, rel_tol=1e-7, abs_tol=1e-9
        ):
            raise SchemaGateError(
                "$.condition_number: must match the committed covariance matrix"
            )
        if not payload["psd_repaired"] and payload["min_eigenvalue"] < -1e-8:
            raise SchemaGateError(
                "$.min_eigenvalue: an unrepaired covariance cannot report a negative eigenvalue"
            )

    elif stage == "pc_proposals":
        methods = [row["method"] for row in payload["proposals"]]
        if len(methods) != len(set(methods)):
            raise SchemaGateError("$.proposals: method names must be unique")
        for index, proposal in enumerate(payload["proposals"]):
            if proposal["status"] == "ok":
                if "error" in proposal:
                    raise SchemaGateError(
                        f"$.proposals[{index}].error: successful proposals cannot report an error"
                    )
                _validate_weight_map(proposal["weights"], f"$.proposals[{index}].weights")
                required = {"expected_return", "volatility", "sharpe", "max_weight", "effective_n"}
                missing = required.difference(proposal["metrics"])
                if missing:
                    raise SchemaGateError(
                        f"$.proposals[{index}].metrics: missing {sorted(missing)}"
                    )
            else:
                if proposal["feasible"]:
                    raise SchemaGateError(
                        f"$.proposals[{index}]: failed proposals cannot be feasible"
                    )
                if not proposal.get("error", "").strip():
                    raise SchemaGateError(
                        f"$.proposals[{index}].error: failed proposals require an error"
                    )
                if proposal["metrics"]:
                    raise SchemaGateError(
                        f"$.proposals[{index}].metrics: failed proposals require empty metrics"
                    )

    elif stage == "peer_review":
        methods = [row["method"] for row in payload["borda"]]
        survivors = payload["survivors"]
        if len(methods) != len(set(methods)) or len(survivors) != len(set(survivors)):
            raise SchemaGateError("$.borda/$.survivors: method names must be unique")
        if not set(survivors).issubset(methods):
            raise SchemaGateError("$.survivors: every survivor must appear in the Borda table")
        filtered = [row["method"] for row in payload["filtered_out"]]
        if len(filtered) != len(set(filtered)):
            raise SchemaGateError("$.filtered_out: method names must be unique")
        if set(filtered).intersection(methods):
            raise SchemaGateError("$.filtered_out: methods cannot also appear in Borda results")
        challenger = payload["adversarial_challenger"]
        if challenger is not None:
            _validate_weight_map(challenger["weights"], "$.adversarial_challenger.weights")

    elif stage == "final_portfolio":
        _validate_weight_map(payload["weights"], "$.weights")
        for name, weights in payload["all_ensembles"].items():
            _validate_weight_map(weights, f"$.all_ensembles.{name}")
        selected = payload["ensemble_method"]
        if selected not in payload["all_ensembles"]:
            raise SchemaGateError("$.ensemble_method: selected method is absent from all_ensembles")
        if payload["weights"] != payload["all_ensembles"][selected]:
            raise SchemaGateError("$.weights: must equal the selected ensemble weight map")
        if payload["escalate_to_human"] != bool(payload["escalation_reason"].strip()):
            raise SchemaGateError(
                "$.escalation_reason: must be non-empty exactly when escalation is required"
            )


def validate_artifact(
    stage: str,
    payload: Mapping[str, Any],
    schema_path: str | Path | None = None,
) -> None:
    """Validate one stage artifact against schema and semantic contracts."""
    if stage not in STAGE_SCHEMAS:
        raise SchemaGateError(f"Unknown stage: {stage}")
    selected_schema = Path(schema_path) if schema_path is not None else (
        SCHEMA_DIR / STAGE_SCHEMAS[stage][1]
    )
    schema = json.loads(selected_schema.read_text(encoding="utf-8"))
    try:
        Draft7Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaGateError(
            f"Invalid JSON Schema contract for {stage}: {exc.message}"
        ) from exc
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda error: list(error.absolute_path))
    if errors:
        detail = "; ".join(
            f"{_json_path(error.absolute_path)}: {error.message}" for error in errors[:8]
        )
        raise SchemaGateError(f"{stage} failed JSON Schema validation: {detail}")
    _semantic_validate(stage, payload)
    canonical_json_bytes(payload)


class GovernedRun:
    """Own a new run directory and enforce its finite-state artifact contract."""

    def __init__(
        self,
        output_root: str | Path,
        run_id: str,
        ips_path: str | Path,
        parameters: Mapping[str, Any],
    ) -> None:
        self.run_id = validate_run_id(run_id)
        self.run_dir = Path(output_root).resolve() / self.run_id
        try:
            self.run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise GovernanceError(
                f"Run directory already exists: {self.run_dir}. Use a new run_id."
            ) from exc

        self.audit_path = self.run_dir / "audit.jsonl"
        self.manifest_path = self.run_dir / "run_manifest.json"
        self._audit_head = AUDIT_GENESIS
        self._event_sequence = 0
        self._next_stage = 0

        ips_source = Path(ips_path)
        ips_bytes = ips_source.read_bytes()
        ips_snapshot = self.run_dir / "inputs" / "ips.md"
        atomic_write_bytes(ips_snapshot, ips_bytes)
        ips_hash = sha256_bytes(ips_bytes)

        contracts: dict[str, dict[str, Any]] = {}
        for stage, (_, schema_name) in STAGE_SCHEMAS.items():
            schema_bytes = (SCHEMA_DIR / schema_name).read_bytes()
            relative_path = f"contracts/{schema_name}"
            target = self.run_dir / relative_path
            atomic_write_bytes(target, schema_bytes)
            contracts[stage] = {
                "file": relative_path,
                "sha256": sha256_bytes(schema_bytes),
                "bytes": len(schema_bytes),
            }

        self.manifest: dict[str, Any] = {
            "manifest_version": MANIFEST_VERSION,
            "run_id": self.run_id,
            "status": "running",
            "started_at": utc_now(),
            "completed_at": None,
            "parameters": dict(parameters),
            "inputs": {
                "ips": {
                    "source_name": ips_source.name,
                    "snapshot": "inputs/ips.md",
                    "sha256": ips_hash,
                    "bytes": len(ips_bytes),
                }
            },
            "contracts": contracts,
            "artifacts": {},
            "audit_log": "audit.jsonl",
            "audit_head": AUDIT_GENESIS,
        }
        self._record_event(
            "run_started",
            {
                "parameters": dict(parameters),
                "ips_sha256": ips_hash,
                "ips_snapshot": "inputs/ips.md",
                "contract_sha256": {
                    stage: record["sha256"] for stage, record in contracts.items()
                },
            },
        )
        self._write_manifest()

    def _record_event(self, event_type: str, details: Mapping[str, Any]) -> dict[str, Any]:
        self._event_sequence += 1
        event = {
            "sequence": self._event_sequence,
            "timestamp": utc_now(),
            "event": event_type,
            "details": dict(details),
            "previous_hash": self._audit_head,
        }
        event_hash = sha256_bytes(canonical_json_bytes(event))
        event["event_hash"] = event_hash
        line = canonical_json_bytes(event) + b"\n"
        with self.audit_path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        self._audit_head = event_hash
        self.manifest["audit_head"] = event_hash
        return event

    def _write_manifest(self) -> None:
        atomic_write_json(self.manifest_path, self.manifest)

    def commit_input(
        self,
        name: str,
        data: bytes,
        metadata: Mapping[str, Any],
    ) -> Path:
        """Commit a deterministic raw-data snapshot before the first stage."""
        filenames = {"macro": "inputs/macro.csv", "prices": "inputs/prices.csv"}
        if self.manifest["status"] != "running" or self._next_stage != 0:
            raise StageOrderError("Raw inputs can be committed only before the first stage")
        if name not in filenames:
            raise GovernanceError(f"Unsupported governed input: {name}")
        if name in self.manifest["inputs"]:
            raise GovernanceError(f"Governed input already committed: {name}")
        canonical_json_bytes(metadata)
        relative_path = filenames[name]
        target = self.run_dir / relative_path
        atomic_write_bytes(target, data)
        record = {
            "snapshot": relative_path,
            "sha256": sha256_file(target),
            "bytes": target.stat().st_size,
            "metadata": dict(metadata),
        }
        _validate_csv_input(self.run_dir, name, record)
        self.manifest["inputs"][name] = record
        self._record_event("input_committed", {"name": name, **record})
        self._write_manifest()
        return target

    def commit_json(self, stage: str, payload: Mapping[str, Any]) -> Path:
        if self.manifest["status"] != "running":
            raise StageOrderError("Cannot commit to a run that is not running")
        missing_inputs = set(REQUIRED_INPUTS).difference(self.manifest["inputs"])
        if missing_inputs:
            raise StageOrderError(
                f"Cannot commit stages before governed inputs: {sorted(missing_inputs)}"
            )
        expected = STAGE_ORDER[self._next_stage] if self._next_stage < len(STAGE_ORDER) else None
        if stage != expected:
            raise StageOrderError(f"Expected stage '{expected}', received '{stage}'")

        contract = self.manifest["contracts"][stage]
        validate_artifact(stage, payload, self.run_dir / contract["file"])
        filename, _ = STAGE_SCHEMAS[stage]
        target = self.run_dir / filename
        atomic_write_json(target, payload)
        digest = sha256_file(target)
        artifact = {
            "file": filename,
            "schema": contract["file"],
            "schema_sha256": contract["sha256"],
            "sha256": digest,
            "bytes": target.stat().st_size,
        }
        self.manifest["artifacts"][stage] = artifact
        self._record_event("stage_committed", {"stage": stage, **artifact})
        self._next_stage += 1
        self._write_manifest()
        return target

    def commit_attachment(self, name: str, text: str) -> Path:
        if self._next_stage != len(STAGE_ORDER):
            raise StageOrderError("Attachments can be committed only after all JSON stages")
        if name != "board_memo.md":
            raise GovernanceError("Only the governed board_memo.md attachment is supported")
        if "board_memo" in self.manifest["artifacts"]:
            raise StageOrderError("board_memo.md has already been committed")
        target = self.run_dir / name
        atomic_write_text(target, text)
        artifact = {
            "file": name,
            "schema": None,
            "sha256": sha256_file(target),
            "bytes": target.stat().st_size,
        }
        self.manifest["artifacts"]["board_memo"] = artifact
        self._record_event("attachment_committed", {"name": "board_memo", **artifact})
        self._write_manifest()
        return target

    def complete(self) -> None:
        if set(self.manifest["inputs"]) != set(REQUIRED_INPUTS):
            raise StageOrderError("Cannot complete without all governed input snapshots")
        if self._next_stage != len(STAGE_ORDER):
            raise StageOrderError(
                f"Cannot complete before all stages commit ({self._next_stage}/{len(STAGE_ORDER)})"
            )
        if "board_memo" not in self.manifest["artifacts"]:
            raise StageOrderError("Cannot complete before board_memo.md commits")
        self.manifest["status"] = "complete"
        self.manifest["completed_at"] = utc_now()
        self._record_event("run_completed", {"artifact_count": len(self.manifest["artifacts"])})
        self._write_manifest()

    def fail(self, exc: BaseException) -> None:
        if self.manifest["status"] != "running":
            return
        self.manifest["status"] = "failed"
        self.manifest["completed_at"] = utc_now()
        self.manifest["failure"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:1000],
            "failed_before_stage": (
                STAGE_ORDER[self._next_stage]
                if self._next_stage < len(STAGE_ORDER)
                else "completion"
            ),
        }
        self._record_event("run_failed", self.manifest["failure"])
        self._write_manifest()


def _load_audit_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_bytes().splitlines(), start=1):
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise VerificationError(f"audit.jsonl line {line_number} is invalid JSON") from exc
        if not isinstance(event, dict):
            raise VerificationError(f"audit.jsonl line {line_number} must be a JSON object")
        events.append(event)
    return events


def _parse_utc_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise VerificationError(f"{label} must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise VerificationError(f"{label} is not a valid timestamp") from exc
    return parsed


def _resolve_run_member(root: Path, relative_name: str) -> Path:
    if not isinstance(relative_name, str) or not relative_name:
        raise VerificationError("Run manifest paths must be non-empty strings")
    relative = Path(relative_name)
    if relative.is_absolute() or ".." in relative.parts:
        raise VerificationError(f"Unsafe path in run manifest: {relative_name!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise VerificationError(
            f"Run manifest path escapes the run directory: {relative_name!r}"
        ) from exc
    return candidate


def _validate_csv_input(root: Path, name: str, record: Mapping[str, Any]) -> None:
    """Cross-check a raw CSV snapshot against its anchored metadata."""
    path = _resolve_run_member(root, record.get("snapshot", ""))
    metadata = record.get("metadata", {})
    try:
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            row_count = 0
            latest_date: date | None = None
            for row in reader:
                if not row:
                    continue
                observed = date.fromisoformat(row[0])
                latest_date = observed if latest_date is None else max(latest_date, observed)
                row_count += 1
        expected_columns = metadata.get("series" if name == "macro" else "tickers")
        if not header or header[0] != "date" or header[1:] != expected_columns:
            raise ValueError("CSV columns differ from metadata")
        if name == "macro" and tuple(expected_columns or ()) != REQUIRED_MACRO_SERIES:
            raise ValueError("macro series do not match the required classifier inputs")
        if row_count != metadata.get("rows"):
            raise ValueError("CSV row count differs from metadata")
        if latest_date is None or latest_date.isoformat() != metadata.get("data_through"):
            raise ValueError("CSV data-through date differs from metadata")
        as_of = date.fromisoformat(metadata.get("as_of", ""))
        if latest_date > as_of:
            raise ValueError("CSV contains observations after as_of")
    except (OSError, StopIteration, TypeError, ValueError, csv.Error) as exc:
        raise VerificationError(f"Invalid {name} input CSV: {exc}") from exc


def _verify_portfolio_metrics(
    label: str,
    weights: Mapping[str, Any],
    reported: Mapping[str, Any],
    tickers: Sequence[str],
    cmas: Mapping[str, Any],
    covariance: Mapping[str, Any],
    risk_free_rate: float,
) -> None:
    """Recompute every reported metric from the committed CMA and covariance."""
    import numpy as np

    cma_by_ticker = {row["ticker"]: row for row in cmas["cmas"]}
    vector = np.asarray([weights[ticker] for ticker in tickers], dtype=float)
    expected_returns = np.asarray(
        [cma_by_ticker[ticker]["expected_return"] for ticker in tickers], dtype=float
    )
    volatilities = np.asarray(
        [cma_by_ticker[ticker]["volatility"] for ticker in tickers], dtype=float
    )
    matrix = np.asarray(covariance["covariance"], dtype=float)
    expected_return = float(vector @ expected_returns)
    variance = float(vector @ matrix @ vector)
    volatility = float(np.sqrt(max(variance, 0.0)))
    squared_sum = float(np.sum(vector**2))
    actual = {
        "expected_return": expected_return,
        "volatility": volatility,
        "sharpe": (
            (expected_return - risk_free_rate) / volatility if volatility > 1e-9 else 0.0
        ),
        "max_weight": float(vector.max()),
        "effective_n": 1.0 / squared_sum if squared_sum > 0 else 0.0,
        "diversification_ratio": (
            float(vector @ volatilities) / volatility if volatility > 1e-9 else 1.0
        ),
    }
    for metric, actual_value in actual.items():
        if metric not in reported or not math.isclose(
            float(reported[metric]), actual_value, rel_tol=1e-8, abs_tol=1e-10
        ):
            raise ValueError(f"{label} metric {metric} cannot be reproduced")


def _validate_cross_artifact_contract(
    manifest: Mapping[str, Any],
    input_records: Mapping[str, Any],
    payloads: Mapping[str, Mapping[str, Any]],
    ips_path: Path,
) -> None:
    """Verify lineage, mandate bounds, and consistency across stage artifacts."""
    try:
        ips = parse_ips(ips_path)
        parameters = manifest["parameters"]
        expected_as_of = parameters["as_of"]
        as_of_date = date.fromisoformat(expected_as_of)
        tickers = ips["tickers"]

        for name, record in input_records.items():
            if name in {"macro", "prices"}:
                if record["metadata"]["as_of"] != expected_as_of:
                    raise ValueError(f"{name} input as_of differs from run parameters")
        macro_metadata = input_records.get("macro", {}).get("metadata")
        price_metadata = input_records.get("prices", {}).get("metadata")
        if price_metadata is not None:
            if price_metadata["tickers"] != tickers:
                raise ValueError("Price input ticker order differs from the IPS")
            if not math.isclose(
                float(price_metadata["lookback_years"]),
                float(parameters["lookback_years"]),
            ):
                raise ValueError("Price lookback differs from run parameters")

        for stage, payload in payloads.items():
            if payload.get("as_of") != expected_as_of:
                raise ValueError(f"{stage} as_of differs from run parameters")
            data_through = payload.get("data_through")
            if data_through and date.fromisoformat(data_through) > as_of_date:
                raise ValueError(f"{stage} contains data after as_of")

        regime = payloads.get("regime")
        cmas = payloads.get("cmas")
        covariance = payloads.get("covariance")
        proposals = payloads.get("pc_proposals")
        peer = payloads.get("peer_review")
        final = payloads.get("final_portfolio")

        if regime is not None and macro_metadata is not None:
            if regime["data_through"] != macro_metadata["data_through"]:
                raise ValueError("Regime data-through differs from the macro snapshot")
            if regime["vintage_policy"] != macro_metadata["vintage_policy"]:
                raise ValueError("Regime vintage policy differs from the macro snapshot")
        if cmas is not None:
            if [row["ticker"] for row in cmas["cmas"]] != tickers:
                raise ValueError("CMA ticker order differs from the IPS")
            if regime is not None and cmas["regime"] != regime["regime"]:
                raise ValueError("CMA regime differs from the regime artifact")
            if price_metadata is not None and cmas["data_through"] != price_metadata[
                "data_through"
            ]:
                raise ValueError("CMA data-through differs from the price snapshot")
            if not math.isclose(
                float(cmas["lookback_years"]), float(parameters["lookback_years"])
            ):
                raise ValueError("CMA lookback differs from run parameters")
        if covariance is not None:
            if covariance["tickers"] != tickers:
                raise ValueError("Covariance ticker order differs from the IPS")
            if covariance["method"] != parameters["covariance_method"]:
                raise ValueError("Covariance method differs from run parameters")
            if not math.isclose(
                float(covariance["lookback_years"]),
                float(parameters["lookback_years"]),
            ):
                raise ValueError("Covariance lookback differs from run parameters")
            if price_metadata is not None:
                if date.fromisoformat(covariance["data_through"]) > date.fromisoformat(
                    price_metadata["data_through"]
                ):
                    raise ValueError("Covariance data-through exceeds the price snapshot")
                if covariance["n_observations"] > max(price_metadata["rows"] - 1, 0):
                    raise ValueError("Covariance observation count exceeds the price snapshot")
        if proposals is not None:
            for proposal in proposals["proposals"]:
                if set(proposal["weights"]) != set(tickers):
                    raise ValueError(f"Proposal {proposal['method']} ticker set differs from IPS")
                if proposal["status"] == "ok":
                    validate_ips_weights(
                        proposal["weights"], ips, f"proposal {proposal['method']}"
                    )
                    if not proposal["feasible"]:
                        raise ValueError(f"Successful proposal {proposal['method']} is infeasible")
                    if cmas is not None and covariance is not None:
                        _verify_portfolio_metrics(
                            f"proposal {proposal['method']}",
                            proposal["weights"],
                            proposal["metrics"],
                            tickers,
                            cmas,
                            covariance,
                            float(parameters["risk_free_rate"]),
                        )
        if peer is not None:
            if proposals is not None:
                proposal_by_method = {
                    row["method"]: row for row in proposals["proposals"]
                }
                eligible = {
                    method
                    for method, proposal in proposal_by_method.items()
                    if proposal["status"] == "ok"
                    and proposal["feasible"]
                    and proposal["metrics"]["volatility"] <= ips["vol_cap"]
                }
                borda_methods = {row["method"] for row in peer["borda"]}
                filtered_methods = {row["method"] for row in peer["filtered_out"]}
                if borda_methods != eligible:
                    raise ValueError("Peer-review Borda methods differ from eligible proposals")
                if filtered_methods != set(proposal_by_method).difference(eligible):
                    raise ValueError("Peer-review filters do not cover ineligible proposals")
                expected_survivors = [
                    row["method"] for row in peer["borda"][: parameters["top_k"]]
                ]
                if peer["survivors"] != expected_survivors:
                    raise ValueError("Peer-review survivors differ from the ranked top_k")
            challenger = peer["adversarial_challenger"]
            if challenger is not None:
                validate_ips_weights(challenger["weights"], ips, "adversarial challenger")
        if final is not None:
            validate_ips_weights(final["weights"], ips, "final portfolio")
            for method, weights in final["all_ensembles"].items():
                validate_ips_weights(weights, ips, f"ensemble {method}")
            if final["dissenting_view"] is not None:
                validate_ips_weights(
                    final["dissenting_view"]["weights"], ips, "dissenting view"
                )
            if cmas is not None and covariance is not None:
                _verify_portfolio_metrics(
                    "final portfolio",
                    final["weights"],
                    final["metrics"],
                    tickers,
                    cmas,
                    covariance,
                    float(parameters["risk_free_rate"]),
                )
            if regime is not None and final["regime"] != regime["regime"]:
                raise ValueError("Final regime differs from the regime artifact")
            if proposals is not None and peer is not None and regime is not None:
                expected_ensemble = (
                    "trimmed_mean"
                    if regime["top1_confidence_low"]
                    else REGIME_TO_ENSEMBLE[regime["regime"]]
                )
                if final["ensemble_method"] != expected_ensemble:
                    raise ValueError("Final ensemble selection differs from policy")
                dissent = final["dissenting_view"]
                if peer["survivors"] and dissent is None:
                    raise ValueError("Final portfolio omits the required dissenting view")
                if dissent is not None:
                    if dissent["method"] not in peer["survivors"]:
                        raise ValueError("Dissenting method did not survive peer review")
                    source = next(
                        row
                        for row in proposals["proposals"]
                        if row["method"] == dissent["method"]
                    )
                    if dissent["weights"] != source["weights"]:
                        raise ValueError("Dissenting weights differ from the source proposal")
                feasible_count = sum(
                    1 for proposal in proposals["proposals"] if proposal["feasible"]
                )
                challenger_won = bool(
                    (peer.get("adversarial_challenger") or {}).get("won", False)
                )
                expected_escalation = (
                    final["metrics"]["volatility"] > ips["vol_cap"] - 0.005
                    or feasible_count < ips["min_feasible_proposals"]
                    or challenger_won
                    or regime["top1_confidence_low"]
                )
                if final["escalate_to_human"] != expected_escalation:
                    raise ValueError("Final human-escalation flag is inconsistent")
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        raise VerificationError(f"Cross-artifact contract failed: {exc}") from exc


def verify_run(run_dir: str | Path, require_complete: bool = True) -> dict[str, Any]:
    """Verify inputs, schemas, hashes, state, audit chain, and artifact lineage."""
    root = Path(run_dir).resolve()
    manifest_path = root / "run_manifest.json"
    audit_path = root / "audit.jsonl"
    if not manifest_path.is_file() or not audit_path.is_file():
        raise VerificationError("run_manifest.json and audit.jsonl are required")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping):
        raise VerificationError("run_manifest.json must contain a JSON object")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise VerificationError(f"Unsupported manifest version: {manifest.get('manifest_version')}")
    if require_complete and manifest.get("status") != "complete":
        raise VerificationError(f"Run status is {manifest.get('status')!r}, not 'complete'")
    try:
        manifest_run_id = validate_run_id(manifest.get("run_id", ""))
    except GovernanceError as exc:
        raise VerificationError(f"Manifest run_id is invalid: {exc}") from exc
    if manifest_run_id != root.name:
        raise VerificationError("Manifest run_id does not match the run directory")

    input_records = manifest.get("inputs", {})
    if not isinstance(input_records, Mapping):
        raise VerificationError("Manifest inputs must be an object")
    if not set(input_records).issubset(REQUIRED_INPUTS):
        raise VerificationError("Manifest contains an unsupported input record")
    if "ips" not in input_records:
        raise VerificationError("Manifest is missing the IPS input record")
    if manifest.get("status") == "complete" and set(input_records) != set(REQUIRED_INPUTS):
        raise VerificationError("Complete run input set does not match required inputs")
    for name, record in input_records.items():
        if not isinstance(record, Mapping):
            raise VerificationError(f"Input record must be an object: {name}")
        input_path = _resolve_run_member(root, record.get("snapshot", ""))
        if not input_path.is_file():
            raise VerificationError(f"Missing input snapshot: {name}")
        if input_path.stat().st_size != record.get("bytes"):
            raise VerificationError(f"Input snapshot byte count mismatch: {name}")
        if sha256_file(input_path) != record.get("sha256"):
            raise VerificationError(f"Input snapshot hash mismatch: {name}")
        if name in {"macro", "prices"}:
            _validate_csv_input(root, name, record)

    ips = input_records["ips"]

    events = _load_audit_events(audit_path)
    if not events:
        raise VerificationError("audit.jsonl is empty")
    if events[0].get("event") != "run_started":
        raise VerificationError("First audit event must be run_started")
    first_details = events[0].get("details")
    if not isinstance(first_details, Mapping):
        raise VerificationError("First audit event details must be an object")
    if first_details.get("ips_sha256") != ips.get("sha256"):
        raise VerificationError("IPS hash is not anchored in the first audit event")
    if first_details.get("ips_snapshot") != ips.get("snapshot"):
        raise VerificationError("IPS snapshot path differs from the first audit event")
    if first_details.get("parameters") != manifest.get("parameters"):
        raise VerificationError("Manifest parameters differ from the first audit event")
    contract_records = manifest.get("contracts", {})
    if not isinstance(contract_records, Mapping):
        raise VerificationError("Manifest contracts must be an object")
    if set(contract_records) != set(STAGE_ORDER):
        raise VerificationError("Manifest contract set does not match the pipeline stages")
    if any(not isinstance(record, Mapping) for record in contract_records.values()):
        raise VerificationError("Every schema contract record must be an object")
    contract_hashes = {
        stage: record.get("sha256") for stage, record in contract_records.items()
    }
    if first_details.get("contract_sha256") != contract_hashes:
        raise VerificationError("Schema contract hashes are not anchored in the first audit event")
    for stage, record in contract_records.items():
        contract_path = _resolve_run_member(root, record.get("file", ""))
        if not contract_path.is_file():
            raise VerificationError(f"Missing schema contract for {stage}")
        if contract_path.stat().st_size != record.get("bytes"):
            raise VerificationError(f"Schema contract byte count mismatch for {stage}")
        if sha256_file(contract_path) != record.get("sha256"):
            raise VerificationError(f"Schema contract hash mismatch for {stage}")
        try:
            json.loads(contract_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise VerificationError(f"Schema contract is invalid JSON for {stage}") from exc
    previous = AUDIT_GENESIS
    committed_stages: list[str] = []
    ledger_artifacts: dict[str, dict[str, Any]] = {}
    ledger_inputs: dict[str, dict[str, Any]] = {}
    attachment_count = 0
    terminal_event: str | None = None
    last_timestamp: datetime | None = None
    for expected_sequence, event in enumerate(events, start=1):
        if event.get("sequence") != expected_sequence:
            raise VerificationError(f"Audit sequence break at event {expected_sequence}")
        if event.get("previous_hash") != previous:
            raise VerificationError(f"Audit previous_hash mismatch at event {expected_sequence}")
        claimed = event.get("event_hash")
        unsigned = {key: value for key, value in event.items() if key != "event_hash"}
        actual = sha256_bytes(canonical_json_bytes(unsigned))
        if claimed != actual:
            raise VerificationError(f"Audit event_hash mismatch at event {expected_sequence}")
        previous = actual
        timestamp = _parse_utc_timestamp(
            event.get("timestamp"), f"audit event {expected_sequence} timestamp"
        )
        if last_timestamp is not None and timestamp < last_timestamp:
            raise VerificationError(f"Audit timestamp moved backward at event {expected_sequence}")
        last_timestamp = timestamp
        event_type = event.get("event")
        details = event.get("details")
        if not isinstance(details, Mapping):
            raise VerificationError(f"Audit details must be an object at event {expected_sequence}")
        if terminal_event is not None:
            raise VerificationError(f"Audit event appears after terminal event {terminal_event}")
        if event_type == "run_started":
            if expected_sequence != 1:
                raise VerificationError("run_started may appear only as the first event")
        elif event_type == "input_committed":
            if committed_stages:
                raise VerificationError("Raw input committed after stage execution began")
            name = details.get("name")
            if name not in {"macro", "prices"} or name in ledger_inputs:
                raise VerificationError(f"Invalid or duplicate input commit: {name!r}")
            ledger_inputs[name] = dict(details)
        elif event_type == "stage_committed":
            if set(ledger_inputs) != {"macro", "prices"}:
                raise VerificationError("Stage committed before both raw-data inputs")
            stage = details.get("stage")
            if stage not in STAGE_SCHEMAS:
                raise VerificationError(f"Unknown committed stage: {stage!r}")
            committed_stages.append(stage)
            ledger_artifacts[stage] = dict(details)
        elif event_type == "attachment_committed":
            name = details.get("name")
            if committed_stages != list(STAGE_ORDER) or name != "board_memo":
                raise VerificationError(
                    "Attachment committed before all stages or with invalid name"
                )
            attachment_count += 1
            if attachment_count > 1:
                raise VerificationError("Duplicate board memo attachment commit")
            ledger_artifacts[name] = dict(details)
        elif event_type in {"run_completed", "run_failed"}:
            terminal_event = event_type
        else:
            raise VerificationError(f"Unknown audit event type: {event_type!r}")

    if previous != manifest.get("audit_head"):
        raise VerificationError("Manifest audit_head does not match the audit log")
    expected_prefix = list(STAGE_ORDER[: len(committed_stages)])
    if committed_stages != expected_prefix:
        raise VerificationError(f"Stage order mismatch: {committed_stages}")
    for name, record in input_records.items():
        if name == "ips":
            continue
        ledger_record = ledger_inputs.get(name, {})
        for field in ("snapshot", "sha256", "bytes", "metadata"):
            if ledger_record.get(field) != record.get(field):
                raise VerificationError(f"Input {name} field is not anchored: {field}")

    status = manifest.get("status")
    _parse_utc_timestamp(manifest.get("started_at"), "Manifest started_at")
    if status == "complete":
        _parse_utc_timestamp(manifest.get("completed_at"), "Manifest completed_at")
        if committed_stages != list(STAGE_ORDER) or attachment_count != 1:
            raise VerificationError("Complete run is missing stages or the board memo")
        if terminal_event != "run_completed" or events[-1].get("event") != "run_completed":
            raise VerificationError("A complete run must end with run_completed")
        if events[-1].get("details", {}).get("artifact_count") != len(
            manifest.get("artifacts", {})
        ):
            raise VerificationError("run_completed artifact count mismatch")
    elif status == "failed":
        _parse_utc_timestamp(manifest.get("completed_at"), "Manifest completed_at")
        if terminal_event != "run_failed" or events[-1].get("event") != "run_failed":
            raise VerificationError("A failed run must end with run_failed")
        if manifest.get("failure") != events[-1].get("details"):
            raise VerificationError("Manifest failure details differ from run_failed")
    elif status == "running":
        if manifest.get("completed_at") is not None:
            raise VerificationError("A running manifest cannot have completed_at")
        if terminal_event is not None:
            raise VerificationError("A running manifest cannot contain a terminal event")
    else:
        raise VerificationError(f"Unsupported run status: {status!r}")

    artifacts = manifest.get("artifacts", {})
    if not isinstance(artifacts, Mapping):
        raise VerificationError("Manifest artifacts must be an object")
    artifact_payloads: dict[str, Mapping[str, Any]] = {}
    for name, record in artifacts.items():
        if not isinstance(record, Mapping):
            raise VerificationError(f"Artifact record must be an object: {name}")
        artifact_path = _resolve_run_member(root, record["file"])
        if not artifact_path.is_file():
            raise VerificationError(f"Missing artifact: {record['file']}")
        if artifact_path.stat().st_size != record.get("bytes"):
            raise VerificationError(f"Artifact byte count mismatch: {record['file']}")
        actual_hash = sha256_file(artifact_path)
        if actual_hash != record.get("sha256"):
            raise VerificationError(f"Artifact hash mismatch: {record['file']}")
        ledger_record = ledger_artifacts.get(name, {})
        for field in ("file", "schema", "sha256", "bytes"):
            if ledger_record.get(field) != record.get(field):
                raise VerificationError(
                    f"Artifact field not anchored in audit log: {record['file']} ({field})"
                )
        if name in STAGE_SCHEMAS:
            contract = contract_records[name]
            if record.get("schema") != contract.get("file"):
                raise VerificationError(f"Artifact schema path mismatch: {record['file']}")
            if record.get("schema_sha256") != contract.get("sha256"):
                raise VerificationError(f"Artifact schema hash mismatch: {record['file']}")
            if ledger_record.get("schema_sha256") != contract.get("sha256"):
                raise VerificationError(
                    f"Artifact schema hash not anchored in audit log: {record['file']}"
                )
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            validate_artifact(name, payload, root / contract["file"])
            artifact_payloads[name] = payload

    expected_artifacts = set(STAGE_ORDER) | {"board_memo"}
    if manifest.get("status") == "complete" and set(artifacts) != expected_artifacts:
        raise VerificationError(
            f"Complete run artifact set mismatch: expected {sorted(expected_artifacts)}"
        )
    if set(artifacts) != set(ledger_artifacts):
        raise VerificationError("Manifest and audit log artifact sets differ")

    _validate_cross_artifact_contract(
        manifest,
        input_records,
        artifact_payloads,
        _resolve_run_member(root, ips["snapshot"]),
    )

    return {
        "ok": True,
        "run_id": manifest["run_id"],
        "status": manifest["status"],
        "events_verified": len(events),
        "inputs_verified": len(input_records),
        "artifacts_verified": len(artifacts),
        "contracts_verified": len(contract_records),
        "cross_artifact_verified": True,
        "audit_head": previous,
    }
