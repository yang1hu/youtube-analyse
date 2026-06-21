from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from creator_agent.config import Settings
from creator_agent.services.transcript_store import TranscriptStore
from creator_agent.services.workspace_store import WorkspaceStore


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class StoryWorkbenchService:
    def __init__(self, settings: Settings | None = None, store: WorkspaceStore | None = None) -> None:
        self.settings = settings or Settings()
        self.store = store or WorkspaceStore(self.settings)

    def get_for_report(self, report_id: str) -> dict[str, Any]:
        data = self.store.load()
        report = self._find_report(data, report_id)
        if not report:
            raise ValueError("Report not found.")
        existing = self._find_item(data, report_id)
        if existing:
            return {"story_workbench": self._normalize_existing_item(existing)}
        item = self._build_item(report, cleaned_text=None)
        return {"story_workbench": item}

    def save_cleaned_script(self, report_id: str, cleaned_text: str) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def save(data: dict[str, Any]) -> None:
            report = self._find_report(data, report_id)
            if not report:
                raise ValueError("Report not found.")
            item = self._build_item(report, cleaned_text=cleaned_text)
            item["updated_at"] = utc_now_iso()
            existing_index = self._find_item_index(data, report_id)
            if existing_index is None:
                item["cleaned_versions"] = [self._version_from_item(item, version=1, source="manual")]
                data["story_workbench_items"].insert(0, item)
            else:
                existing = self._normalize_existing_item(data["story_workbench_items"][existing_index])
                item["created_at"] = existing.get("created_at") or item["created_at"]
                item["cleaned_versions"] = self._append_cleaned_version(existing, item)
                data["story_workbench_items"][existing_index] = item
            holder["item"] = item

        self.store.update(save)
        return {"story_workbench": holder["item"]}

    def restore_cleaned_version(self, report_id: str, version_id: str) -> dict[str, Any]:
        holder: dict[str, Any] = {}

        def restore(data: dict[str, Any]) -> None:
            report = self._find_report(data, report_id)
            if not report:
                raise ValueError("Report not found.")
            existing_index = self._find_item_index(data, report_id)
            if existing_index is None:
                raise ValueError("Story workbench item not found.")
            existing = self._normalize_existing_item(data["story_workbench_items"][existing_index])
            version = self._find_version(existing, version_id)
            if not version:
                raise ValueError("Cleaned script version not found.")

            item = self._build_item(report, cleaned_text=str(version.get("cleaned_text") or ""))
            item["created_at"] = existing.get("created_at") or item["created_at"]
            item["updated_at"] = utc_now_iso()
            item["cleaned_versions"] = self._append_cleaned_version(
                existing,
                item,
                source=f"restore:{version.get('version') or version_id}",
            )
            data["story_workbench_items"][existing_index] = item
            holder["item"] = item
            holder["restored_version"] = version

        self.store.update(restore)
        return {"story_workbench": holder["item"], "restored_version": holder["restored_version"]}

    def update_analysis(self, report_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        allowed_text_fields = {
            "opening_5s_hook",
            "first_30s_retention",
            "protagonist_position",
            "status_gap",
            "first_payoff",
            "middle_escalation",
            "opposition_design",
            "public_reversal",
            "ending_suspense",
            "structure_confidence",
        }
        allowed_list_fields = {"reusable_template", "non_reusable_content"}
        holder: dict[str, Any] = {}

        def update(data: dict[str, Any]) -> None:
            report = self._find_report(data, report_id)
            if not report:
                raise ValueError("Report not found.")
            existing_index = self._find_item_index(data, report_id)
            if existing_index is None:
                item = self._build_item(report, cleaned_text=None)
                data["story_workbench_items"].insert(0, item)
                existing_index = 0
            item = self._normalize_existing_item(data["story_workbench_items"][existing_index])
            analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
            if not analysis:
                analysis = self._analyze_story_structure(
                    report,
                    str(item.get("cleaned_text") or ""),
                    item.get("segments") if isinstance(item.get("segments"), list) else [],
                )

            for field in allowed_text_fields:
                if field in patch:
                    analysis[field] = str(patch.get(field) or "").strip()
            for field in allowed_list_fields:
                if field in patch:
                    analysis[field] = self._clean_list(patch.get(field))
            analysis["analysis_basis"] = str(analysis.get("analysis_basis") or "cleaned_transcript")
            analysis["manual_override"] = True
            analysis["manual_updated_at"] = utc_now_iso()
            item["analysis"] = analysis
            item["updated_at"] = utc_now_iso()
            data["story_workbench_items"][existing_index] = item
            holder["item"] = item

        self.store.update(update)
        return {"story_workbench": holder["item"]}

    def _build_item(self, report: dict[str, Any], cleaned_text: str | None) -> dict[str, Any]:
        transcript = self._transcript_for_report(report)
        raw_text = str(transcript.get("raw_text") or "") if transcript else ""
        cleaned = cleaned_text.strip() if cleaned_text is not None else self._clean_script(raw_text)
        segments = self._segments(cleaned)
        analysis = self._analyze_story_structure(report, cleaned, segments)
        return {
            "report_id": report.get("id") or "",
            "video_id": report.get("youtube_video_id") or "",
            "video_title": report.get("video_title") or "",
            "video_url": report.get("video_url") or "",
            "raw_text": raw_text,
            "raw_length": len(raw_text),
            "cleaned_text": cleaned,
            "cleaned_length": len(cleaned),
            "cleanup_stats": self._cleanup_stats(raw_text, cleaned, segments),
            "cleanup_changes": self._cleanup_changes(raw_text, cleaned),
            "segments": segments,
            "analysis": analysis,
            "cleaned_versions": [],
            "created_at": utc_now_iso(),
        }

    def _normalize_existing_item(self, item: dict[str, Any]) -> dict[str, Any]:
        normalized = {**item}
        versions = item.get("cleaned_versions") if isinstance(item.get("cleaned_versions"), list) else []
        normalized["cleaned_versions"] = [
            version
            for version in versions
            if isinstance(version, dict) and str(version.get("cleaned_text") or "").strip()
        ]
        if not normalized["cleaned_versions"] and str(item.get("cleaned_text") or "").strip():
            normalized["cleaned_versions"] = [self._version_from_item(item, version=1, source="manual")]
        if not isinstance(normalized.get("cleanup_stats"), dict):
            normalized["cleanup_stats"] = self._cleanup_stats(
                str(normalized.get("raw_text") or ""),
                str(normalized.get("cleaned_text") or ""),
                normalized.get("segments") if isinstance(normalized.get("segments"), list) else [],
            )
        else:
            recalculated = self._cleanup_stats(
                str(normalized.get("raw_text") or ""),
                str(normalized.get("cleaned_text") or ""),
                normalized.get("segments") if isinstance(normalized.get("segments"), list) else [],
            )
            normalized["cleanup_stats"] = {**recalculated, **normalized["cleanup_stats"]}
        if not isinstance(normalized.get("cleanup_changes"), dict):
            normalized["cleanup_changes"] = self._cleanup_changes(
                str(normalized.get("raw_text") or ""),
                str(normalized.get("cleaned_text") or ""),
            )
        return normalized

    def _append_cleaned_version(self, existing: dict[str, Any], item: dict[str, Any], *, source: str = "manual") -> list[dict[str, Any]]:
        versions = list(existing.get("cleaned_versions") or [])
        latest_text = str(versions[0].get("cleaned_text") or "") if versions else str(existing.get("cleaned_text") or "")
        next_text = str(item.get("cleaned_text") or "")
        if latest_text.strip() == next_text.strip():
            return versions[:10]
        next_version = max([self._as_int(version.get("version")) for version in versions] or [0]) + 1
        return [self._version_from_item(item, version=next_version, source=source), *versions][:10]

    def _version_from_item(self, item: dict[str, Any], *, version: int, source: str) -> dict[str, Any]:
        cleaned_text = str(item.get("cleaned_text") or "")
        cleanup_stats = item.get("cleanup_stats") if isinstance(item.get("cleanup_stats"), dict) else {}
        return {
            "id": f"{item.get('report_id') or 'story'}-cleaned-v{version}",
            "version": version,
            "source": source,
            "cleaned_text": cleaned_text,
            "cleaned_length": len(cleaned_text),
            "segment_count": len(item.get("segments") or []),
            "structure_confidence": (item.get("analysis") or {}).get("structure_confidence", ""),
            "quality_score": cleanup_stats.get("quality_score"),
            "quality_status": cleanup_stats.get("quality_status", ""),
            "created_at": item.get("updated_at") or item.get("created_at") or utc_now_iso(),
        }

    def _clean_script(self, raw_text: str) -> str:
        text = raw_text.strip()
        if not text:
            return ""
        text = re.sub(r"\[[^\]]+\]", " ", text)
        text = re.sub(r"\(\s*\d{1,2}:\d{2}(?::\d{2})?\s*\)", " ", text)
        text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？!?])\s+", text) if sentence.strip()]
        if not sentences:
            sentences = self._fallback_sentence_split(text)
        deduped: list[str] = []
        previous = ""
        for sentence in sentences:
            normalized = self._normalize_for_dedupe(sentence)
            if normalized and normalized == previous:
                continue
            deduped.append(sentence)
            previous = normalized
        paragraphs: list[str] = []
        current: list[str] = []
        for sentence in deduped:
            current.append(sentence)
            if len("".join(current)) >= 130:
                paragraphs.append("".join(current))
                current = []
        if current:
            paragraphs.append("".join(current))
        return "\n".join(paragraphs)

    def _cleanup_stats(self, raw_text: str, cleaned: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
        raw_length = len(raw_text)
        cleaned_length = len(cleaned)
        removed_characters = max(0, raw_length - cleaned_length)
        noise_marker_count = len(re.findall(r"\[[^\]]+\]|\b\d{1,2}:\d{2}(?::\d{2})?\b", raw_text))
        duplicate_sentence_count = self._duplicate_sentence_count(raw_text)
        paragraph_count = len([paragraph for paragraph in cleaned.splitlines() if paragraph.strip()])
        stats = {
            "raw_length": raw_length,
            "cleaned_length": cleaned_length,
            "removed_characters": removed_characters,
            "compression_percent": round((removed_characters / raw_length) * 100, 1) if raw_length else 0,
            "noise_marker_count": noise_marker_count,
            "duplicate_sentence_count": duplicate_sentence_count,
            "paragraph_count": paragraph_count,
            "segment_count": len(segments),
        }
        stats.update(self._cleanup_quality(stats))
        return stats

    def _cleanup_changes(self, raw_text: str, cleaned: str) -> dict[str, Any]:
        noise_matches = re.findall(r"\[[^\]]+\]|\(?\b\d{1,2}:\d{2}(?::\d{2})?\b\)?", raw_text)
        duplicate_sentences = self._duplicate_sentence_samples(raw_text)
        raw_paragraph_count = len([paragraph for paragraph in raw_text.splitlines() if paragraph.strip()])
        cleaned_paragraph_count = len([paragraph for paragraph in cleaned.splitlines() if paragraph.strip()])
        cleaned_sentence_count = len(self._readable_sentence_samples(cleaned))
        paragraph_changes: list[str] = []
        sentence_break_changes: list[str] = []

        if raw_text.strip() and cleaned.strip():
            if raw_paragraph_count <= 1 < cleaned_paragraph_count:
                paragraph_changes.append(f"原始字幕被整理为 {cleaned_paragraph_count} 个故事段落。")
            elif raw_paragraph_count > cleaned_paragraph_count:
                paragraph_changes.append(f"{raw_paragraph_count} 个原始段落被合并整理为 {cleaned_paragraph_count} 个故事段落。")
            elif cleaned_paragraph_count:
                paragraph_changes.append(f"清洗稿保留 {cleaned_paragraph_count} 个故事段落。")
            if cleaned_sentence_count:
                sentence_break_changes.append(f"清洗稿拆分出 {cleaned_sentence_count} 个可读句段，便于后续结构拆解。")

        return {
            "removed_noise": [{"text": text, "reason": "subtitle_noise"} for text in noise_matches[:8]],
            "removed_duplicates": [{"text": text, "reason": "duplicate_sentence"} for text in duplicate_sentences[:8]],
            "paragraph_changes": paragraph_changes,
            "sentence_break_changes": sentence_break_changes,
        }

    def _cleanup_quality(self, stats: dict[str, Any]) -> dict[str, Any]:
        raw_length = self._as_int(stats.get("raw_length"))
        cleaned_length = self._as_int(stats.get("cleaned_length"))
        compression_percent = float(stats.get("compression_percent") or 0)
        duplicate_sentence_count = self._as_int(stats.get("duplicate_sentence_count"))
        noise_marker_count = self._as_int(stats.get("noise_marker_count"))
        paragraph_count = self._as_int(stats.get("paragraph_count"))
        segment_count = self._as_int(stats.get("segment_count"))
        score = 100
        reasons: list[str] = []

        if raw_length and not cleaned_length:
            return {
                "quality_score": 0,
                "quality_status": "poor",
                "manual_review_reasons": ["清洗稿为空，需要人工粘贴或重新获取字幕。"],
            }
        if not raw_length and not cleaned_length:
            return {
                "quality_score": 0,
                "quality_status": "poor",
                "manual_review_reasons": ["缺少原始字幕和清洗稿，无法进行故事拆解。"],
            }
        if not raw_length and cleaned_length:
            score -= 15
            reasons.append("缺少原始字幕，只能基于人工清洗稿判断质量。")
        if raw_length and compression_percent < 3 and (noise_marker_count or duplicate_sentence_count):
            score -= 16
            reasons.append("原文存在噪声或重复，但清洗压缩幅度较低，建议人工检查是否残留字幕噪声。")
        if compression_percent > 72:
            score -= 18
            reasons.append("清洗压缩幅度过高，建议确认是否误删关键情节。")
        if duplicate_sentence_count:
            score -= min(20, duplicate_sentence_count * 6)
            reasons.append("检测到重复句，建议确认清洗稿是否已经去重。")
        if noise_marker_count >= 3:
            score -= min(15, noise_marker_count * 2)
            reasons.append("原文包含较多时间戳、音效或字幕噪声，建议人工浏览清洗结果。")
        if cleaned_length > 300 and paragraph_count <= 1:
            score -= 12
            reasons.append("清洗稿段落过少，建议补充分段，方便后续结构拆解。")
        if cleaned_length > 240 and segment_count < 3:
            score -= 10
            reasons.append("故事段落标签较少，可能影响钩子、爽点和反转识别。")
        if cleaned_length < 120:
            score -= 18
            reasons.append("清洗稿过短，结构分析置信度可能偏低。")

        score = max(0, min(100, score))
        if score >= 82:
            status = "ready"
        elif score >= 60:
            status = "needs_review"
        else:
            status = "poor"
        return {
            "quality_score": score,
            "quality_status": status,
            "manual_review_reasons": reasons,
        }

    def _duplicate_sentence_count(self, raw_text: str) -> int:
        text = re.sub(r"\[[^\]]+\]", " ", raw_text)
        text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？!?])\s+", text) if sentence.strip()]
        if not sentences:
            sentences = self._fallback_sentence_split(" ".join(text.split()))
        count = 0
        previous = ""
        for sentence in sentences:
            normalized = self._normalize_for_dedupe(sentence)
            if normalized and normalized == previous:
                count += 1
            previous = normalized
        return count

    def _duplicate_sentence_samples(self, raw_text: str) -> list[str]:
        text = re.sub(r"\[[^\]]+\]", " ", raw_text)
        text = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", " ", text)
        sentences = self._readable_sentence_samples(text)
        if not sentences:
            sentences = self._fallback_sentence_split(" ".join(text.split()))
        samples: list[str] = []
        previous = ""
        for sentence in sentences:
            normalized = self._normalize_for_dedupe(sentence)
            if normalized and normalized == previous:
                samples.append(sentence)
            previous = normalized
        return samples

    def _readable_sentence_samples(self, text: str) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        sentences = [sentence.strip() for sentence in re.split(r"(?<=[。！？.!?])\s+", normalized) if sentence.strip()]
        if len(sentences) <= 1 and " " in normalized:
            sentences = [sentence.strip() for sentence in normalized.split(" ") if sentence.strip()]
        return sentences

    def _fallback_sentence_split(self, text: str) -> list[str]:
        chunks = [text[index : index + 42].strip() for index in range(0, len(text), 42)]
        return [chunk for chunk in chunks if chunk]

    def _segments(self, cleaned: str) -> list[dict[str, Any]]:
        paragraphs = [paragraph.strip() for paragraph in cleaned.splitlines() if paragraph.strip()]
        labels = [
            ("opening_hook", "开场钩子"),
            ("setup", "主角处境"),
            ("information_gap", "信息差"),
            ("first_payoff", "第一次爽点"),
            ("escalation", "中段升级"),
            ("public_reversal", "公开兑现/反转"),
            ("ending_suspense", "结尾悬念"),
        ]
        if not paragraphs:
            return []
        result: list[dict[str, Any]] = []
        for index, paragraph in enumerate(paragraphs):
            label_key, label = labels[min(index, len(labels) - 1)]
            result.append(
                {
                    "index": index + 1,
                    "label_key": label_key,
                    "label": label,
                    "text": paragraph,
                    "length": len(paragraph),
                }
            )
        return result

    def _analyze_story_structure(
        self,
        report: dict[str, Any],
        cleaned: str,
        segments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        breakdown = report.get("creative_breakdown") if isinstance(report.get("creative_breakdown"), dict) else {}
        idea_cards = report.get("idea_cards") if isinstance(report.get("idea_cards"), list) else []
        first_idea = next((item for item in idea_cards if isinstance(item, dict)), {})
        first_segment = segments[0]["text"] if segments else ""
        second_segment = segments[1]["text"] if len(segments) > 1 else ""
        third_segment = segments[2]["text"] if len(segments) > 2 else ""
        last_segment = segments[-1]["text"] if segments else ""
        structure = self._clean_list(breakdown.get("structure"))
        emotional_curve = self._clean_list(breakdown.get("emotional_curve"))
        analysis = {
            "opening_5s_hook": self._shorten(first_segment or str(breakdown.get("opening_hook") or ""), 120),
            "first_30s_retention": self._shorten(" ".join([first_segment, second_segment]).strip() or str(breakdown.get("opening_hook") or ""), 220),
            "protagonist_position": self._infer_protagonist_position(cleaned, first_idea),
            "status_gap": self._infer_gap(cleaned, first_idea),
            "first_payoff": self._shorten(third_segment or self._first_matching(cleaned, ["奖励", "兑现", "反转", "打脸", "reward", "payoff"]), 180),
            "middle_escalation": self._shorten(" / ".join(structure[2:5]) if structure else self._middle_segment(segments), 220),
            "opposition_design": self._infer_opposition(cleaned),
            "public_reversal": self._shorten(self._first_matching(cleaned, ["所有人", "全场", "公开", "当众", "everyone", "public"]) or last_segment, 180),
            "ending_suspense": self._shorten(last_segment, 180),
            "reusable_template": self._reusable_template(structure, emotional_curve),
            "non_reusable_content": self._non_reusable_content(report, first_idea),
            "structure_confidence": self._confidence(cleaned, structure),
            "analysis_basis": "cleaned_transcript" if cleaned else "report_only",
        }
        analysis["evidence"] = self._analysis_evidence(analysis, segments, breakdown)
        return analysis

    def _analysis_evidence(
        self,
        analysis: dict[str, Any],
        segments: list[dict[str, Any]],
        breakdown: dict[str, Any],
    ) -> dict[str, Any]:
        segment_by_index = {int(segment.get("index") or 0): segment for segment in segments if isinstance(segment, dict)}
        field_indexes = {
            "opening_5s_hook": [1],
            "first_30s_retention": [1, 2],
            "protagonist_position": [1, 2],
            "status_gap": [2, 3],
            "first_payoff": [3, 4],
            "middle_escalation": [3, 4, 5],
            "opposition_design": [2, 3, 4],
            "public_reversal": [4, 5, len(segments)],
            "ending_suspense": [len(segments)],
        }
        evidence: dict[str, Any] = {}
        for field, indexes in field_indexes.items():
            excerpts = []
            for index in indexes:
                segment = segment_by_index.get(index)
                text = str(segment.get("text") or "").strip() if segment else ""
                if text and text not in excerpts:
                    excerpts.append(text)
            if not excerpts:
                fallback = str(analysis.get(field) or breakdown.get("opening_hook") or "").strip()
                if fallback:
                    excerpts.append(fallback)
            evidence[field] = {
                "segment_indexes": [index for index in indexes if index in segment_by_index],
                "excerpts": [self._shorten(text, 180) for text in excerpts[:3]],
            }
        return evidence

    def _reusable_template(self, structure: list[str], emotional_curve: list[str]) -> list[str]:
        template = structure[:8] or [
            "先展示主角处在低位或被误解的后果。",
            "抛出一个观众暂时不知道规则的信息差。",
            "让一个很小的行动触发第一次奖励或反转。",
            "通过旁观者误判放大冲突。",
            "安排公开兑现，让主角身份或价值被重新认识。",
            "结尾留下更高代价、更强敌人或下一次奖励。",
        ]
        if emotional_curve:
            template.append("情绪推进：" + " -> ".join(emotional_curve[:6]))
        return template

    def _non_reusable_content(self, report: dict[str, Any], idea: dict[str, Any]) -> list[str]:
        items = [
            "原视频中的角色名、地名、组织名、系统名和独特道具名。",
            "原字幕中的连续原句和高辨识度表达。",
            "原视频的具体事件顺序和连续桥段。",
        ]
        title = str(report.get("video_title") or "").strip()
        if title:
            items.append(f"不要直接复用或轻微改写原标题：{title}")
        risk = str(idea.get("risk_notes") or "").strip()
        if risk:
            items.append(risk)
        return items

    def _infer_protagonist_position(self, cleaned: str, idea: dict[str, Any]) -> str:
        angle = str(idea.get("angle") or "").strip()
        if angle:
            return angle
        if any(token in cleaned for token in ["实习", "低估", "废物", "穷", "被赶", "瞧不起"]):
            return "主角处在低位、被误解或被公开低估。"
        return "主角先处在压力或误解中，再通过隐藏优势完成反转。"

    def _infer_gap(self, cleaned: str, idea: dict[str, Any]) -> str:
        why = str(idea.get("why_it_works") or "").strip()
        if why:
            return why
        if any(token in cleaned for token in ["系统", "隐藏", "规则", "秘密"]):
            return "观众知道存在隐藏规则，但角色或旁观者暂时误判局势。"
        return "通过身份差、信息差或能力差制造继续看下去的理由。"

    def _infer_opposition(self, cleaned: str) -> str:
        if any(token in cleaned for token in ["反派", "敌人", "老板", "同学", "家族", "嘲笑"]):
            return "阻力来自公开质疑、身份压制或旁观者嘲笑。"
        return "需要设置一个能公开施压的人物或群体，让兑现更有爽感。"

    def _middle_segment(self, segments: list[dict[str, Any]]) -> str:
        if len(segments) <= 2:
            return ""
        middle = segments[2 : min(len(segments), 5)]
        return " / ".join(str(item.get("text") or "")[:80] for item in middle)

    def _first_matching(self, text: str, needles: list[str]) -> str:
        for paragraph in text.splitlines():
            if any(needle.lower() in paragraph.lower() for needle in needles):
                return paragraph
        return ""

    def _confidence(self, cleaned: str, structure: list[str]) -> str:
        if len(cleaned) > 1000 and len(structure) >= 4:
            return "high"
        if len(cleaned) > 300 or structure:
            return "medium"
        return "low"

    def _transcript_for_report(self, report: dict[str, Any]) -> dict[str, Any] | None:
        video_id = str(report.get("youtube_video_id") or "")
        if not video_id:
            return None
        return TranscriptStore(self.settings).get_transcript(video_id)

    def _find_report(self, data: dict[str, Any], report_id: str) -> dict[str, Any] | None:
        for report in data["reports"]:
            if str(report.get("id") or "") == report_id:
                return report
        return None

    def _find_item(self, data: dict[str, Any], report_id: str) -> dict[str, Any] | None:
        index = self._find_item_index(data, report_id)
        return data["story_workbench_items"][index] if index is not None else None

    def _find_item_index(self, data: dict[str, Any], report_id: str) -> int | None:
        for index, item in enumerate(data["story_workbench_items"]):
            if str(item.get("report_id") or "") == report_id:
                return index
        return None

    def _find_version(self, item: dict[str, Any], version_id: str) -> dict[str, Any] | None:
        for version in item.get("cleaned_versions") or []:
            if not isinstance(version, dict):
                continue
            if str(version.get("id") or "") == version_id or str(version.get("version") or "") == version_id:
                return version
        return None

    def _normalize_for_dedupe(self, value: str) -> str:
        return re.sub(r"\W+", "", value).lower()

    def _shorten(self, value: str, limit: int) -> str:
        normalized = " ".join(str(value or "").split())
        return normalized[:limit]

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _clean_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]
