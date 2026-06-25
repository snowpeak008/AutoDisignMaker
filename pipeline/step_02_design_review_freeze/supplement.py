"""AI-driven L5 entity supplement for Step 02."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from core.adapters.base import ModelAdapter, ModelTask
from core.io import now_iso, read_json, write_json
from pipeline.step_01_gameplay_framework.helpers import (
    LoopExtractor,
    SystemDeducer,
    pick_genre_template_key,
)
from pipeline.step_02_design_review_freeze.supplement_contracts import (
    DEFAULT_MIN_PER_KIND,
    DEFAULT_TARGET_KINDS,
    FALLBACK_ENTITIES_PATH,
    NODE_BY_KIND,
    PROMPT_PATH,
    SupplementRequest,
    SupplementResult,
    field,
    selection_label,
    text,
)
from pipeline.step_02_design_review_freeze.supplement_entities import (
    merge_entities,
    normalize_entity,
    parse_response_entities,
    validate_entity,
)


MISSING_NODE_FALLBACK_LIMIT = 48


class EntitySupplementAdapter:
    """AI-driven L5 entity supplement adapter."""

    def __init__(
        self,
        ctx: Any = None,
        *,
        cache_dir: Path | None = None,
        adapter_name: str | None = None,
        model_adapter: ModelAdapter | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.ctx = ctx
        self.adapter_name = (
            adapter_name
            or text(getattr(ctx, "adapter_name", ""))
            or text(getattr(ctx, "metadata", {}).get("adapter_name") if ctx else "")
            or "none"
        )
        artifact_dir = cache_dir or getattr(ctx, "artifact_dir", None)
        self.cache_dir = Path(artifact_dir) if artifact_dir else Path.cwd()
        self.cache_path = self.cache_dir / "ai_supplement_cache.json"
        self.model_adapter = model_adapter
        self.timeout_seconds = timeout_seconds

    def should_supplement(self, coverage_report: dict[str, Any]) -> tuple[bool, str]:
        """Return whether an entity coverage report should trigger this adapter."""
        if self.adapter_name == "none":
            return False, "adapter disabled"
        try:
            rate = float(coverage_report.get("entity_coverage_rate", 0.0))
        except (TypeError, ValueError):
            rate = 0.0
        unmapped = len(coverage_report.get("unmapped_nodes", [])) + len(
            coverage_report.get("missing_entities", [])
        )
        entities = [
            entity
            for entity in coverage_report.get("entities", [])
            if isinstance(entity, dict)
        ]
        system_count = sum(
            1 for entity in entities if text(entity.get("kind")) == "system"
        )
        if rate < 0.50:
            return True, f"coverage_rate={rate:.2f} < 0.50"
        if unmapped > 30:
            return True, f"unmapped_nodes={unmapped} > 30"
        if system_count < 5:
            return True, f"system_entities={system_count} < 5"
        return False, "coverage sufficient"

    def supplement(
        self,
        entities: list[dict[str, Any]],
        parsed_context: dict[str, Any],
    ) -> SupplementResult:
        """Return original entities enriched with AI or fallback L5 entities."""
        request = self._build_request(entities, parsed_context)
        cache_payload = self._cache_payload()
        cached = self._load_cache(request.request_hash, payload=cache_payload)
        fallback_used = bool(cache_payload.get("fallback_used")) if cached else False
        cache_hit = cached is not None
        supplemented = cached or []
        supplement_error = text(cache_payload.get("error")) if cached else ""
        if supplemented:
            adapter_used = text(cache_payload.get("adapter")) or self.adapter_name
        else:
            try:
                supplemented = self._call_ai(request)
            except (ValueError, ImportError) as exc:
                supplemented = []
                supplement_error = f"{type(exc).__name__}: {exc}"
            adapter_used = self.adapter_name
            if not supplemented:
                supplemented = self._fallback(entities, parsed_context, request=request)
                fallback_used = True
            self._save_cache(
                request.request_hash,
                supplemented,
                fallback_used=fallback_used,
                error=supplement_error,
            )
        merged, added_count, completed_count = self._merge_entities(
            entities, supplemented
        )
        return SupplementResult(
            entities=merged,
            added_count=added_count,
            completed_count=completed_count,
            cache_hit=cache_hit,
            adapter_used=adapter_used,
            fallback_used=fallback_used,
            error=supplement_error,
            supplement_basis_samples=[
                text(entity.get("supplement_basis"))
                for entity in supplemented
                if text(entity.get("supplement_basis"))
            ][:3],
        )

    def _build_request(
        self,
        entities: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> SupplementRequest:
        """Build a deterministic supplement request from parsed context."""
        selections = [item for item in context.get("selections", []) if item]
        genre = pick_genre_template_key(text(context.get("raw_text")), selections)
        core_loop = LoopExtractor().extract(context).get("loop", [])
        systems = (
            SystemDeducer()
            .deduce(context, {"nodes": [], "edges": []})
            .get("systems", [])
        )
        missing_node_ids = [
            text(node_id)
            for node_id in context.get("missing_node_ids", [])
            if text(node_id)
        ]
        request = SupplementRequest(
            project_name=self._project_name(context),
            genre=genre,
            core_loop=[text(item) for item in core_loop if text(item)],
            systems=[
                {
                    "id": text(system.get("id")),
                    "name": text(system.get("name")),
                    "responsibility": text(system.get("responsibility")),
                }
                for system in systems
                if isinstance(system, dict)
            ],
            existing_entities=[
                {
                    "label": text(entity.get("label")),
                    "kind": text(entity.get("kind")),
                    "status": text(entity.get("status")),
                    "schema": text(entity.get("schema")),
                    "node_id": text(entity.get("node_id")),
                }
                for entity in entities[:20]
            ],
            l4_decisions=self._l4_decisions(selections),
            target_kinds=list(DEFAULT_TARGET_KINDS),
            min_per_kind=dict(DEFAULT_MIN_PER_KIND),
            missing_node_ids=missing_node_ids,
            known_node_ids=self._known_node_ids(entities, systems, context),
        )
        request.request_hash = self._compute_hash(request, context)
        return request

    def _load_cache(
        self,
        request_hash: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]] | None:
        """Return cached supplement entities for a matching request hash."""
        payload = payload or self._cache_payload()
        if payload.get("request_hash") != request_hash:
            return None
        entities = payload.get("entities", [])
        if not isinstance(entities, list):
            return None
        valid = [
            self._normalize_entity(entity)
            for entity in entities
            if self._validate_entity(entity)
        ]
        return valid or None

    def _save_cache(
        self,
        request_hash: str,
        entities: list[dict[str, Any]],
        *,
        fallback_used: bool,
        error: str = "",
    ) -> None:
        """Persist supplement entities for deterministic reruns."""
        payload = {
            "schema_version": 1,
            "generated_at": now_iso(),
            "request_hash": request_hash,
            "adapter": self.adapter_name,
            "fallback_used": fallback_used,
            "entities": entities,
        }
        if error:
            payload["error"] = error
        write_json(self.cache_path, payload)

    def _compute_hash(self, request: SupplementRequest, context: dict[str, Any]) -> str:
        """Return a short deterministic cache key for the request."""
        key_data = {
            "source_sha256": text(context.get("source_sha256")),
            "genre": request.genre,
            "core_loop": sorted(request.core_loop),
            "systems": sorted(system.get("name", "") for system in request.systems),
            "existing_entities": sorted(
                f"{item.get('kind')}::{item.get('label')}::{item.get('status')}"
                for item in request.existing_entities
            ),
            "missing_node_ids": sorted(request.missing_node_ids),
            "min_per_kind": request.min_per_kind,
        }
        digest = hashlib.sha256(
            json.dumps(key_data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest[:16]

    def _validate_entity(self, entity: dict[str, Any]) -> bool:
        """Return True when a generated entity has required L5 fields."""
        if not isinstance(entity, dict):
            return False
        return validate_entity(entity)

    def _fallback(
        self,
        entities: list[dict[str, Any]],
        context: dict[str, Any],
        *,
        request: SupplementRequest | None = None,
    ) -> list[dict[str, Any]]:
        """Return deterministic genre fallback entities when AI is unavailable."""
        if request is None:
            request = self._build_request(entities, context)
        library = read_json(FALLBACK_ENTITIES_PATH, {})
        if not isinstance(library, dict):
            library = {}
        raw_entities = library.get(request.genre) or library.get("generic") or []
        supplemented = self._missing_node_fallback_entities(request)
        for index, raw in enumerate(raw_entities, 1):
            if not isinstance(raw, dict):
                continue
            entity = dict(raw)
            entity.setdefault(
                "supplement_basis", f"{request.genre} 品类降级实体 #{index}"
            )
            entity.setdefault("source", "ai_supplement_fallback")
            normalized = self._normalize_entity(entity)
            if self._validate_entity(normalized):
                supplemented.append(normalized)
        return supplemented

    def _missing_node_fallback_entities(
        self, request: SupplementRequest
    ) -> list[dict[str, Any]]:
        """Create deterministic fallback entities for real missing node ids."""
        supplemented: list[dict[str, Any]] = []
        for index, node_id in enumerate(
            request.missing_node_ids[:MISSING_NODE_FALLBACK_LIMIT], 1
        ):
            kind = self._kind_for_missing_node(node_id)
            entity = {
                "label": self._label_for_missing_node(node_id, kind),
                "kind": kind,
                "schema": f"{kind}.v1",
                "node_id": node_id,
                "source": "ai_supplement_missing_node_fallback",
                "supplement_basis": (
                    f"{request.genre or 'generic'} missing-node fallback #{index}: "
                    f"{node_id}"
                ),
            }
            normalized = self._normalize_entity(entity)
            if self._validate_entity(normalized):
                supplemented.append(normalized)
        return supplemented

    def _kind_for_missing_node(self, node_id: str) -> str:
        text_lower = text(node_id).lower()
        if any(token in text_lower for token in ("weapon", "attack")):
            return "weapon"
        if any(token in text_lower for token in ("enemy", "boss")):
            return "enemy"
        if any(
            token in text_lower for token in ("ability", "skill", "action", "input")
        ):
            return "ability"
        if any(
            token in text_lower for token in ("room", "level", "encounter", "biome")
        ):
            return "room"
        if any(token in text_lower for token in ("resource", "currency", "economy")):
            return "resource"
        if any(token in text_lower for token in ("ui", "hud", "interface")):
            return "ui"
        if any(token in text_lower for token in ("audio", "sound", "music")):
            return "audio"
        if any(
            token in text_lower for token in ("scene", "environment", "art", "visual")
        ):
            return "scene"
        if any(token in text_lower for token in ("character", "avatar", "npc")):
            return "character"
        if any(token in text_lower for token in ("system", "loop", "runtime")):
            return "system"
        return "config"

    def _label_for_missing_node(self, node_id: str, kind: str) -> str:
        base = text(node_id).removesuffix("_decision").replace("_", " ").strip()
        label = " ".join(part.capitalize() for part in base.split()) or "Design Node"
        return f"{label} {kind}"

    def _merge_entities(
        self,
        original: list[dict[str, Any]],
        supplemented: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, int]:
        """Merge generated entities without replacing precise user entities."""
        return merge_entities(original, supplemented)

    def _call_ai(self, request: SupplementRequest) -> list[dict[str, Any]]:
        """Call the configured model adapter and parse supplemented entities."""
        if self.adapter_name == "none":
            return []
        prompt = self._render_prompt(request)
        task = ModelTask(
            task_id="step02_l5_entity_supplement",
            prompt=prompt,
            timeout_seconds=self.timeout_seconds,
            sandbox="read-only",
        )
        try:
            adapter = self.model_adapter or self._model_adapter()
        except (ValueError, ImportError):
            raise
        except Exception:
            return []
        for _attempt in range(2):
            try:
                result = adapter.generate(task)
            except Exception:
                continue
            if result.status != "success" or result.errors:
                continue
            entities = self._parse_response(result.text)
            if entities:
                return entities
        return []

    def _model_adapter(self) -> ModelAdapter:
        """Load the configured model adapter lazily."""
        from core.adapters.registry import get_adapter

        return get_adapter(self.adapter_name)

    def _render_prompt(self, request: SupplementRequest) -> str:
        """Render the supplement prompt template with request JSON."""
        template = PROMPT_PATH.read_text(encoding="utf-8")
        payload = json.dumps(asdict(request), ensure_ascii=False, indent=2)
        return template.replace("{{REQUEST_JSON}}", payload)

    def _parse_response(self, text: str) -> list[dict[str, Any]]:
        """Parse JSON model output into validated supplement entities."""
        return parse_response_entities(text)

    def _cache_payload(self) -> dict[str, Any]:
        """Read the supplement cache payload if it exists and is valid JSON."""
        payload = read_json(self.cache_path, {})
        return payload if isinstance(payload, dict) else {}

    def _normalize_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Normalize generated entity fields for downstream Step 03/04 use."""
        return normalize_entity(entity)

    def _project_name(self, context: dict[str, Any]) -> str:
        """Infer project name from parsed source text."""
        raw_text = text(context.get("raw_text"))
        title = re.search(r"^#\s+(.+?)(?:\s+[—-]\s+.+)?$", raw_text, flags=re.MULTILINE)
        if title:
            return title.group(1).strip()
        source = Path(text(context.get("source"))).stem
        return source or "未命名游戏项目"

    def _l4_decisions(self, selections: list[Any]) -> dict[str, Any]:
        """Collect a compact summary of important non-L5 decisions."""
        result: dict[str, Any] = {}
        for item in selections:
            if text(field(item, "item_type")) == "L5实体":
                continue
            key = text(field(item, "item_type")) or f"decision_{len(result) + 1}"
            value = text(field(item, "option")) or selection_label(item)
            if key and value:
                result[key] = value
            if len(result) >= 8:
                break
        return result

    def _known_node_ids(
        self,
        entities: list[dict[str, Any]],
        systems: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, str]:
        """Build a compact node id reference table for AI output."""
        known = dict(NODE_BY_KIND)
        for node_id in context.get("expected_node_ids", []):
            clean_node_id = text(node_id)
            if clean_node_id:
                known.setdefault(clean_node_id, clean_node_id)
        for system in systems:
            if not isinstance(system, dict):
                continue
            node_id = text(system.get("id"))
            if node_id:
                known[node_id] = text(system.get("name")) or node_id
        for entity in entities:
            node_id = text(entity.get("node_id"))
            if node_id:
                known[node_id] = text(entity.get("label")) or node_id
        return known
