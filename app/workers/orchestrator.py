"""
ROVON.UZ - End-to-End News Pipeline Orchestrator
Coordinates the 4-AI lifecycle:
Ingestion -> AI-1 (Investigator) -> AI-2 (Auditor) -> Human Gate -> AI-3 (Editor) -> Canvas -> AI-4 (Strategist) -> Dispatch
"""

import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sqlalchemy import or_
from sqlalchemy.future import select

from app.db.session import AsyncSessionLocal
from app.db.models.raw_article import RawArticle
from app.db.models.fact_audit import AI1Investigation, AI2Audit
from app.db.models.editorial import AI3Editorial
from app.db.models.publishing import AI4PublishingQueue

from app.ai_brain.ai1_investigator.investigator import RovonInvestigator
from app.ai_brain.ai2_auditor.auditor import RovonAuditor
from app.ai_brain.ai2_auditor.schemas import AuditResult, DiscrepancyItem
from app.ai_brain.ai3_editor.editor import RovonEditor
from app.ai_brain.ai4_strategist.strategist import RovonStrategist
from app.media_studio.canvas_generator import CanvasGenerator
from app.media_studio.image_finder import news_image_finder
from app.telegram_gateway.bot_dispatcher import TelegramDispatcher
from app.core.redis_bus import event_bus


class PipelineOrchestrator:
    """Master orchestrator connecting all 4 AI agents and dispatch."""

    def __init__(self):
        self.investigator = RovonInvestigator()
        self.auditor = RovonAuditor()
        self.editor = RovonEditor()
        self.strategist = RovonStrategist()
        self.canvas = CanvasGenerator()
        self.dispatcher = TelegramDispatcher()

    async def ingest_and_process_article(self, article_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the full pipeline for an incoming article:
        """
        content_hash = article_data.get("content_hash")
        if not content_hash:
            return {"status": "error", "message": "Missing content_hash"}

        # Check Newsroom Worthiness (Reject bureaucratic PhD notices, tenders, vacancies)
        from app.ingestion.sanitizer import is_news_worthy
        title = article_data.get("title", "")
        body = article_data.get("body_clean", "") or article_data.get("body_raw", "")
        if not is_news_worthy(title, body):
            print(f"[Newsroom Filter] Skipped low-value/bureaucratic notice: {title[:60]}")
            return {"status": "filtered_low_value", "message": "Filtered out non-news notice"}

        # 1. Acquire Distributed Lock for Idempotency
        lock_acquired = await event_bus.acquire_lock(f"process:{content_hash}", expire_seconds=300)
        if not lock_acquired:
            return {"status": "duplicate_skipped", "message": "Already processing this article"}

        try:
            async with AsyncSessionLocal() as session:
                # 2. Check if article already exists in DB by hash or source URL
                source_url = article_data.get("source_url", "")
                existing = await session.execute(
                    select(RawArticle).filter(
                        or_(
                            RawArticle.content_hash == content_hash,
                            RawArticle.source_url == source_url
                        )
                    )
                )
                if existing.scalars().first():
                    return {"status": "already_exists", "message": "Article already exists in database"}

                # 3. Save Raw Article to DB
                raw_article = RawArticle(
                    source_url=article_data["source_url"],
                    source_identifier=article_data["source_identifier"],
                    source_type=article_data["source_type"],
                    title=article_data.get("title", ""),
                    body_raw=article_data["body_raw"],
                    body_clean=article_data["body_clean"],
                    category_predicted=article_data.get("category", "YANGILIK"),
                    content_hash=content_hash,
                    media_urls=article_data.get("media_urls", []),
                    published_at=article_data.get("published_at", datetime.now(timezone.utc)),
                )
                session.add(raw_article)
                await session.flush()  # Populates raw_article.id

                # 4. AI-1: Run Investigation
                inv_payload = await self.investigator.investigate_article({
                    "id": raw_article.id,
                    "title": raw_article.title,
                    "body_clean": raw_article.body_clean,
                    "source_identifier": raw_article.source_identifier,
                    "source_url": raw_article.source_url,
                })

                ai1_record = AI1Investigation(
                    article_id=raw_article.id,
                    extracted_entities=inv_payload.entities.model_dump(),
                    claims_decomposed=[c.model_dump() for c in inv_payload.claims],
                    primary_source_url=inv_payload.primary_source_url,
                    primary_source_authority=inv_payload.primary_source_authority,
                    cross_sources=[s.model_dump() for s in inv_payload.cross_references],
                    is_recycled=inv_payload.is_recycled_news,
                )
                session.add(ai1_record)
                await session.flush()

                # 5. AI-2: Run Critical Audit
                audit_result = await self.auditor.audit_investigation(inv_payload, raw_article.body_clean)

                ai2_record = AI2Audit(
                    investigation_id=ai1_record.id,
                    verdict=audit_result.verdict,
                    bayesian_score=audit_result.bayesian_score,
                    risk_tier=audit_result.risk_tier,
                    discrepancies=[d.model_dump() for d in audit_result.discrepancies],
                    human_gate_required=audit_result.human_gate_required,
                )
                session.add(ai2_record)
                await session.flush()

                # 6. Human Gate Check: If required, stop and alert editor
                if audit_result.human_gate_required:
                    await session.commit()
                    return {
                        "status": "human_gate_required",
                        "article_id": str(raw_article.id),
                        "verdict": audit_result.verdict,
                        "risk": audit_result.risk_tier,
                        "score": audit_result.bayesian_score,
                        "message": "Sent to Editorial Cockpit for mandatory human review."
                    }

                # 7. AI-3: Run Editorial Packaging (if verified)
                editorial_pkg = await self.editor.craft_editorial_package(
                    audit=audit_result,
                    title=raw_article.title or "Muhim xabar",
                    clean_body=raw_article.body_clean,
                    category=raw_article.category_predicted or "YANGILIK",
                    media_urls=raw_article.media_urls,
                )

                # Generate 16:9 Branded Card via Pillow
                card_filename = f"storage/cards/{raw_article.id}.jpg"
                temp_download = None
                try:
                    if raw_article.media_urls and isinstance(raw_article.media_urls, list) and len(raw_article.media_urls) > 0:
                        img_url = raw_article.media_urls[0]
                        if img_url.startswith("http"):
                            temp_download = f"storage/cards/temp_{raw_article.id}.jpg"
                            try:
                                import httpx
                                resp = httpx.get(img_url, timeout=5.0)
                                if resp.status_code == 200:
                                    with open(temp_download, "wb") as f:
                                        f.write(resp.content)
                                    # Validate image: reject tiny passport headshots in favor of cinematic news photos
                                    try:
                                        from PIL import Image as PILImage
                                        with PILImage.open(temp_download) as test_img:
                                            w, h = test_img.size
                                            if w < 350 or h > 1.25 * w:
                                                temp_download = None
                                    except Exception:
                                        pass
                                else:
                                    temp_download = None
                            except Exception:
                                temp_download = None

                    # If source post has no photo, automatically find a relevant image from the web!
                    if not temp_download or not os.path.exists(temp_download):
                        temp_download = await news_image_finder.find_and_download_image(
                            headline=editorial_pkg.headline_selected,
                            category=editorial_pkg.visual_card_directive.badge_text,
                            body=raw_article.body_clean,
                            article_id=str(raw_article.id),
                        )

                    self.canvas.generate_news_card(
                        headline=editorial_pkg.headline_selected,
                        summary_text=editorial_pkg.telegram_clean_text,
                        badge_text=editorial_pkg.visual_card_directive.badge_text,
                        badge_color=editorial_pkg.visual_card_directive.badge_color,
                        base_image_path=temp_download,
                        output_path=card_filename,
                    )
                except Exception as e:
                    print(f"[Canvas Gen Error] {e}")
                    card_filename = None
                finally:
                    if temp_download and os.path.exists(temp_download):
                        try:
                            os.remove(temp_download)
                        except Exception:
                            pass

                ai3_record = AI3Editorial(
                    audit_id=ai2_record.id,
                    headline_selected=editorial_pkg.headline_selected,
                    headline_alternatives=editorial_pkg.headline_alternatives,
                    telegram_clean_text=editorial_pkg.telegram_clean_text,
                    character_count=editorial_pkg.character_count,
                    visual_card_config=editorial_pkg.visual_card_directive.model_dump(),
                    generated_card_url=card_filename,
                )
                session.add(ai3_record)
                await session.flush()

                # 8. AI-4: Run Scheduling & Priority Optimization
                schedule_decision = await self.strategist.schedule_editorial(
                    editorial=editorial_pkg,
                    category=raw_article.category_predicted or "YANGILIK",
                    published_at=raw_article.published_at,
                )

                ai4_record = AI4PublishingQueue(
                    editorial_id=ai3_record.id,
                    hawkes_priority_score=schedule_decision.hawkes_priority_score,
                    priority_tier=schedule_decision.priority_tier,
                    scheduled_slot=schedule_decision.scheduled_slot,
                    anti_fatigue_passed=schedule_decision.anti_fatigue_passed,
                    dispatch_status="WAITING",
                    idempotency_key=schedule_decision.idempotency_key,
                )
                session.add(ai4_record)
                await session.commit()

                return {
                    "status": "scheduled",
                    "article_id": str(raw_article.id),
                    "headline": editorial_pkg.headline_selected,
                    "priority": schedule_decision.priority_tier,
                    "slot": schedule_decision.scheduled_slot.isoformat(),
                    "card": card_filename,
                }

        finally:
            await event_bus.release_lock(f"process:{content_hash}")

    async def approve_and_schedule_audit(self, audit_id: Any) -> Dict[str, Any]:
        """
        Manually approved by human editor: packages with AI-3 and schedules via AI-4.
        """
        if isinstance(audit_id, str):
            audit_id = uuid.UUID(audit_id)

        async with AsyncSessionLocal() as session:
            audit = await session.get(AI2Audit, audit_id)
            if not audit:
                return {"status": "error", "message": "Audit not found"}

            investigation = await session.get(AI1Investigation, audit.investigation_id)
            if not investigation:
                return {"status": "error", "message": "Investigation not found"}

            raw_article = await session.get(RawArticle, investigation.article_id)
            if not raw_article:
                return {"status": "error", "message": "Article not found"}

            # Reconstruct AuditResult
            audit_result = AuditResult(
                verdict=audit.verdict,
                bayesian_score=audit.bayesian_score,
                risk_tier=audit.risk_tier,
                discrepancies=[],
                human_gate_required=False,
            )

            # AI-3 Packaging
            editorial_pkg = await self.editor.craft_editorial_package(
                audit=audit_result,
                title=raw_article.title or "Muhim xabar",
                clean_body=raw_article.body_clean,
                category=raw_article.category_predicted or "YANGILIK",
                media_urls=raw_article.media_urls,
            )

            # Generate Card
            os.makedirs("storage/cards", exist_ok=True)
            card_filename = f"storage/cards/{raw_article.id}.jpg"
            temp_download = None
            try:
                if raw_article.media_urls and isinstance(raw_article.media_urls, list) and len(raw_article.media_urls) > 0:
                    img_url = raw_article.media_urls[0]
                    if img_url.startswith("http"):
                        temp_download = f"storage/cards/temp_{raw_article.id}.jpg"
                        try:
                            import httpx
                            resp = httpx.get(img_url, timeout=5.0)
                            if resp.status_code == 200:
                                with open(temp_download, "wb") as f:
                                    f.write(resp.content)
                            else:
                                temp_download = None
                        except Exception:
                            temp_download = None

                # If source post has no photo, automatically find a relevant image from the web!
                if not temp_download or not os.path.exists(temp_download):
                    temp_download = await news_image_finder.find_and_download_image(
                        headline=editorial_pkg.headline_selected,
                        category=editorial_pkg.visual_card_directive.badge_text,
                        body=raw_article.body_clean,
                        article_id=str(raw_article.id),
                    )

                self.canvas.generate_news_card(
                    headline=editorial_pkg.headline_selected,
                    summary_text=editorial_pkg.telegram_clean_text,
                    badge_text=editorial_pkg.visual_card_directive.badge_text,
                    badge_color=editorial_pkg.visual_card_directive.badge_color,
                    base_image_path=temp_download,
                    output_path=card_filename,
                )
            except Exception as e:
                print(f"[Canvas Gen Error] {e}", flush=True)
                card_filename = None
            finally:
                if temp_download and os.path.exists(temp_download):
                    try:
                        os.remove(temp_download)
                    except Exception:
                        pass

            ai3_record = AI3Editorial(
                audit_id=audit.id,
                headline_selected=editorial_pkg.headline_selected,
                headline_alternatives=editorial_pkg.headline_alternatives,
                telegram_clean_text=editorial_pkg.telegram_clean_text,
                character_count=editorial_pkg.character_count,
                visual_card_config=editorial_pkg.visual_card_directive.model_dump(),
                generated_card_url=card_filename,
            )
            session.add(ai3_record)
            await session.flush()

            # AI-4 Scheduling
            schedule_decision = await self.strategist.schedule_editorial(
                editorial=editorial_pkg,
                category=raw_article.category_predicted or "YANGILIK",
                published_at=raw_article.published_at,
            )

            ai4_record = AI4PublishingQueue(
                editorial_id=ai3_record.id,
                hawkes_priority_score=schedule_decision.hawkes_priority_score,
                priority_tier=schedule_decision.priority_tier,
                scheduled_slot=schedule_decision.scheduled_slot,
                anti_fatigue_passed=schedule_decision.anti_fatigue_passed,
                dispatch_status="WAITING",
                idempotency_key=schedule_decision.idempotency_key,
            )
            session.add(ai4_record)
            await session.commit()

            return {
                "status": "scheduled",
                "queue_id": str(ai4_record.id),
                "headline": editorial_pkg.headline_selected,
                "priority": schedule_decision.priority_tier,
                "slot": schedule_decision.scheduled_slot.isoformat(),
                "card": card_filename,
            }
