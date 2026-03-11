"""API routes for the Misinformation module."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from api.v1.routes.auth import get_current_user

from ..analyzers.bias_analyzer import BiasAnalyzer
from ..analyzers.credibility_scorer import CredibilityScorer
from ..connectors.content_verification.metadata_extractor import MetadataExtractor
from ..connectors.content_verification.reverse_image_search import ReverseImageSearch
from ..connectors.factcheck.google_factcheck import GoogleFactCheck
from ..config import misinfo_settings
from ..detectors.bot_detector import BotDetector
from ..detectors.claim_detector import ClaimDetector
from ..detectors.narrative_detector import NarrativeDetector
from ..models.claim import Claim
from ..models.source_rating import SourceRating
from ..nlp.propaganda_detector import PropagandaDetector
from .schemas import (
    BotDetectRequest,
    ClaimDetectRequest,
    ClaimVerifyRequest,
    ContentVerifyRequest,
    MisinformationResponse,
    NarrativeTrackRequest,
    SourceRateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()


def _response(
    data: Any,
    message: str,
    status_str: str = "success",
) -> MisinformationResponse:
    return MisinformationResponse(
        id=str(uuid.uuid4()),
        status=status_str,
        data=data if isinstance(data, dict) else ({"result": data} if data is not None else None),
        message=message,
        processed_at=datetime.now(timezone.utc),
    )


@router.post("/claims/detect", response_model=MisinformationResponse)
async def detect_claims(
    request: ClaimDetectRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Detect checkworthy claims in text; also run propaganda and bias analysis."""
    try:
        detector = ClaimDetector()
        propaganda = PropagandaDetector()
        bias = BiasAnalyzer()

        claims = await detector.detect(request.text)
        propaganda_result = await propaganda.detect(request.text)
        bias_result = bias.analyze(request.text)

        data: Dict[str, Any] = {
            "claims": [c.model_dump(mode="json") for c in claims],
            "claim_count": len(claims),
            "propaganda_analysis": propaganda_result,
            "bias_analysis": bias_result,
        }
        return _response(data, f"Detected {len(claims)} checkworthy claim(s).")
    except Exception as exc:
        logger.exception("Error during claim detection")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claim detection failed: {exc}",
        ) from exc


@router.post("/claims/verify", response_model=MisinformationResponse)
async def verify_claim(
    request: ClaimVerifyRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Search Google Fact Check Tools for existing fact-checks on this claim."""
    try:
        checker = GoogleFactCheck(
            api_key=misinfo_settings.GOOGLE_FACTCHECK_API_KEY,
            base_url=misinfo_settings.GOOGLE_FACTCHECK_BASE_URL,
        )
        factchecks = await checker.search(request.claim_text)
        data: Dict[str, Any] = {
            "claim_id": request.claim_id,
            "claim_text": request.claim_text,
            "factchecks": [fc.model_dump(mode="json") for fc in factchecks],
            "factcheck_count": len(factchecks),
        }
        return _response(data, f"Found {len(factchecks)} fact-check(s) for this claim.")
    except Exception as exc:
        logger.exception("Error during claim verification")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claim verification failed: {exc}",
        ) from exc


@router.get("/factchecks/{claim_id}", response_model=MisinformationResponse)
async def get_factchecks(
    claim_id: str,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Retrieve stored fact-checks for a claim by ID (not yet implemented)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Fact-check retrieval by claim ID is not yet implemented. "
               "Results are returned inline at verification time.",
    )


@router.post("/sources/rate", response_model=MisinformationResponse)
async def rate_source(
    request: SourceRateRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Create a SourceRating and compute a credibility score for the domain."""
    try:
        source_rating = SourceRating(domain=request.domain, name=request.name)
        scorer = CredibilityScorer()
        credibility = scorer.score(
            source_domain=request.domain,
            source_rating=source_rating,
        )
        data: Dict[str, Any] = {
            "source_rating": source_rating.model_dump(mode="json"),
            "credibility_score": credibility,
        }
        return _response(data, f"Source '{request.domain}' rated with credibility {credibility}.")
    except Exception as exc:
        logger.exception("Error during source rating")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Source rating failed: {exc}",
        ) from exc


@router.post("/narratives/track", response_model=MisinformationResponse)
async def track_narratives(
    request: NarrativeTrackRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Detect narratives from a list of claim texts."""
    try:
        claim_objects = [Claim(text=text) for text in request.claims]
        detector = NarrativeDetector()
        narratives = await detector.detect(claim_objects, keywords=request.keywords)
        data: Dict[str, Any] = {
            "narratives": [n.model_dump(mode="json") for n in narratives],
            "narrative_count": len(narratives),
        }
        return _response(data, f"Detected {len(narratives)} narrative(s).")
    except Exception as exc:
        logger.exception("Error during narrative tracking")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Narrative tracking failed: {exc}",
        ) from exc


@router.post("/content/verify", response_model=MisinformationResponse)
async def verify_content(
    request: ContentVerifyRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Extract metadata from a URL; also perform reverse image search for images."""
    try:
        extractor = MetadataExtractor()
        metadata = await extractor.extract(request.url)

        data: Dict[str, Any] = {
            "url": request.url,
            "content_type": request.content_type,
            "metadata": metadata,
        }

        if request.content_type == "image":
            image_search = ReverseImageSearch()
            image_result = await image_search.search(request.url)
            data["reverse_image_search"] = image_result

        return _response(data, f"Content verification completed for {request.url}.")
    except Exception as exc:
        logger.exception("Error during content verification")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content verification failed: {exc}",
        ) from exc


@router.get("/campaigns/{campaign_id}", response_model=MisinformationResponse)
async def get_campaign(
    campaign_id: str,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Retrieve a misinformation campaign by ID (not yet implemented)."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Campaign retrieval is not yet implemented.",
    )


@router.post("/bots/detect", response_model=MisinformationResponse)
async def detect_bot(
    request: BotDetectRequest,
    _current_user=Depends(get_current_user),
) -> MisinformationResponse:
    """Analyse a social media profile for bot-like behaviour."""
    try:
        bot_detector = BotDetector()
        result = await bot_detector.analyze(request.profile_data)
        return _response(result, "Bot detection analysis completed.")
    except Exception as exc:
        logger.exception("Error during bot detection")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bot detection failed: {exc}",
        ) from exc
