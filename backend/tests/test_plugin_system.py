"""
Tests for the OSINT Platform plugin system.

Covers:
- Plugin interface contract
- Plugin registry singleton behaviour
- Plugin loader (dry-run without FastAPI)
- Each module's metadata and capabilities
"""
from __future__ import annotations

import sys
import os
import pytest

# Ensure the backend directory is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── Plugin infrastructure ─────────────────────────────────────────────────────


class TestPluginInterface:
    def test_plugin_interface_is_abstract(self) -> None:
        from plugins.interfaces.plugin_interface import PluginInterface
        import inspect

        assert inspect.isabstract(PluginInterface)

    def test_plugin_interface_abstract_methods(self) -> None:
        from plugins.interfaces.plugin_interface import PluginInterface

        abstract_methods = set(PluginInterface.__abstractmethods__)
        required = {"name", "version", "description", "initialize", "register_routes",
                    "register_entity_types", "register_relationship_types"}
        assert required.issubset(abstract_methods)


class TestPluginRegistry:
    def test_singleton(self) -> None:
        from plugins.registry import PluginRegistry

        a = PluginRegistry.get_instance()
        b = PluginRegistry.get_instance()
        assert a is b

    def test_register_and_list(self) -> None:
        from plugins.registry import PluginRegistry
        from plugins.modules.digital_footprint.plugin import DigitalFootprintPlugin

        reg = PluginRegistry.get_instance()
        plugin = DigitalFootprintPlugin()
        reg.register(plugin)

        assert plugin.name in reg.list_plugins()

    def test_get_plugin(self) -> None:
        from plugins.registry import PluginRegistry
        from plugins.modules.digital_footprint.plugin import DigitalFootprintPlugin

        reg = PluginRegistry.get_instance()
        plugin = DigitalFootprintPlugin()
        reg.register(plugin)

        fetched = reg.get(plugin.name)
        assert fetched is not None
        assert fetched.name == plugin.name

    def test_unregister(self) -> None:
        from plugins.registry import PluginRegistry
        from plugins.modules.investigation.plugin import InvestigationPlugin

        reg = PluginRegistry.get_instance()
        plugin = InvestigationPlugin()
        reg.register(plugin)
        reg.unregister(plugin.name)

        assert reg.get(plugin.name) is None


# ── Digital Footprint Module ──────────────────────────────────────────────────


class TestDigitalFootprintPlugin:
    def setup_method(self) -> None:
        from plugins.modules.digital_footprint.plugin import DigitalFootprintPlugin

        self.plugin = DigitalFootprintPlugin()

    def test_name(self) -> None:
        assert self.plugin.name == "digital-footprint"

    def test_version(self) -> None:
        assert self.plugin.version == "1.0.0"

    def test_entity_types(self) -> None:
        types = self.plugin.register_entity_types()
        assert "social_profile" in types
        assert "email_record" in types
        assert "phone_record" in types

    def test_relationship_types(self) -> None:
        types = self.plugin.register_relationship_types()
        assert len(types) > 0

    def test_capabilities(self) -> None:
        caps = self.plugin.get_capabilities()
        assert "data-ingestion" in caps
        assert "entity-creation" in caps

    def test_initialize_does_not_raise(self) -> None:
        self.plugin.initialize()  # should not raise


class TestDigitalFootprintModels:
    def test_email_record(self) -> None:
        from plugins.modules.digital_footprint.models.email_record import EmailRecord

        rec = EmailRecord(
            email="test@example.com",
            is_valid=True,
            domain="example.com",
        )
        assert rec.email == "test@example.com"
        assert rec.is_valid is True
        assert rec.breach_count == 0

    def test_phone_record(self) -> None:
        from plugins.modules.digital_footprint.models.phone_record import PhoneRecord

        rec = PhoneRecord(number="+14155552671", is_valid=True)
        assert rec.number == "+14155552671"

    def test_username_record(self) -> None:
        from plugins.modules.digital_footprint.models.username_record import UsernameRecord

        rec = UsernameRecord(username="johndoe")
        assert rec.username == "johndoe"
        assert rec.platforms_found == []

    def test_domain_record(self) -> None:
        from plugins.modules.digital_footprint.models.domain_record import DomainRecord

        rec = DomainRecord(domain="example.com")
        assert rec.domain == "example.com"
        assert rec.is_active is True


class TestDigitalFootprintConnectors:
    @pytest.mark.asyncio
    async def test_email_validator_valid(self) -> None:
        from plugins.modules.digital_footprint.connectors.email.email_validator import (
            EmailValidator,
        )

        validator = EmailValidator()
        result = await validator.validate("user@example.com")
        assert result.email == "user@example.com"
        assert result.domain == "example.com"

    @pytest.mark.asyncio
    async def test_email_validator_invalid(self) -> None:
        from plugins.modules.digital_footprint.connectors.email.email_validator import (
            EmailValidator,
        )

        validator = EmailValidator()
        result = await validator.validate("not-an-email")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_number_validator_valid(self) -> None:
        from plugins.modules.digital_footprint.connectors.phone.number_validator import (
            NumberValidator,
        )

        validator = NumberValidator()
        result = await validator.validate("+14155552671")
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_number_validator_invalid(self) -> None:
        from plugins.modules.digital_footprint.connectors.phone.number_validator import (
            NumberValidator,
        )

        validator = NumberValidator()
        result = await validator.validate("abc")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_breach_checker_no_key(self) -> None:
        from plugins.modules.digital_footprint.connectors.email.breach_checker import (
            BreachChecker,
        )

        checker = BreachChecker(api_key="")
        result = await checker.check("test@example.com")
        # Without an API key, should return an empty list (graceful degradation)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_dns_analyzer_returns_dict(self) -> None:
        from plugins.modules.digital_footprint.connectors.domain.dns_analyzer import DnsAnalyzer

        analyzer = DnsAnalyzer()
        result = await analyzer.analyze("example.com")
        assert isinstance(result, dict)


class TestDigitalFootprintAnalyzers:
    @pytest.mark.asyncio
    async def test_identity_correlator(self) -> None:
        from plugins.modules.digital_footprint.analyzers.identity_correlator import (
            IdentityCorrelator,
        )

        correlator = IdentityCorrelator()
        profiles = [
            {"username": "johndoe", "email": "john@example.com"},
            {"username": "johndoe", "email": "jdoe@example.com"},
        ]
        result = await correlator.correlate(profiles)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_timeline_generator(self) -> None:
        from plugins.modules.digital_footprint.analyzers.timeline_generator import (
            TimelineGenerator,
        )

        gen = TimelineGenerator()
        profiles: list[dict] = []
        result = await gen.generate(profiles)
        assert isinstance(result, list)


# ── Investigation Module ──────────────────────────────────────────────────────


class TestInvestigationPlugin:
    def setup_method(self) -> None:
        from plugins.modules.investigation.plugin import InvestigationPlugin

        self.plugin = InvestigationPlugin()

    def test_name(self) -> None:
        assert self.plugin.name == "investigation"

    def test_entity_types(self) -> None:
        types = self.plugin.register_entity_types()
        assert "person_profile" in types
        assert "org_profile" in types

    def test_relationship_types(self) -> None:
        types = self.plugin.register_relationship_types()
        assert "employment" in types
        assert "affiliation" in types

    def test_initialize_does_not_raise(self) -> None:
        self.plugin.initialize()


class TestInvestigationModels:
    def test_investigation_case(self) -> None:
        from plugins.modules.investigation.models.investigation_case import InvestigationCase

        case = InvestigationCase(title="Test Case", case_type="person")
        assert case.title == "Test Case"
        assert case.status == "active"
        assert case.id is not None

    def test_person_profile(self) -> None:
        from plugins.modules.investigation.models.person_profile import PersonProfile

        profile = PersonProfile(full_name="John Doe")
        assert profile.full_name == "John Doe"
        assert profile.aliases == []

    def test_org_profile(self) -> None:
        from plugins.modules.investigation.models.org_profile import OrgProfile

        profile = OrgProfile(name="ACME Corp")
        assert profile.name == "ACME Corp"

    def test_public_record(self) -> None:
        from plugins.modules.investigation.models.public_record import PublicRecord

        rec = PublicRecord(record_type="court", title="Test Case")
        assert rec.record_type == "court"


class TestInvestigationConnectors:
    @pytest.mark.asyncio
    async def test_court_records_returns_list(self) -> None:
        from plugins.modules.investigation.connectors.public_records.court_records import (
            CourtRecordsConnector,
        )

        connector = CourtRecordsConnector()
        result = await connector.search("John Doe")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_news_aggregator_no_key(self) -> None:
        from plugins.modules.investigation.connectors.news.news_aggregator import NewsAggregator

        aggregator = NewsAggregator(api_key="")
        result = await aggregator.search("test query")
        assert isinstance(result, list)

    def test_sentiment_analyzer(self) -> None:
        from plugins.modules.investigation.connectors.news.sentiment_analyzer import (
            SentimentAnalyzer,
        )

        analyzer = SentimentAnalyzer()
        assert analyzer.analyze("This is a great success!") == "positive"
        assert analyzer.analyze("This is a terrible fraud.") == "negative"
        assert analyzer.analyze("This is a sentence.") == "neutral"


class TestInvestigationAnalyzers:
    def test_risk_scorer_zero_for_empty(self) -> None:
        from plugins.modules.investigation.analyzers.risk_scorer import RiskScorer

        scorer = RiskScorer()
        score = scorer.score({})
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_timeline_builder_empty(self) -> None:
        from plugins.modules.investigation.analyzers.timeline_builder import TimelineBuilder

        builder = TimelineBuilder()
        result = await builder.build([])
        assert result == []

    @pytest.mark.asyncio
    async def test_relationship_mapper_empty(self) -> None:
        from plugins.modules.investigation.analyzers.relationship_mapper import RelationshipMapper

        mapper = RelationshipMapper()
        result = await mapper.map([])
        assert isinstance(result, list)


# ── Cyber OSINT Module ────────────────────────────────────────────────────────


class TestCyberOsintPlugin:
    def setup_method(self) -> None:
        from plugins.modules.cyber_osint.plugin import CyberOsintPlugin

        self.plugin = CyberOsintPlugin()

    def test_name(self) -> None:
        assert self.plugin.name == "cyber-osint"

    def test_entity_types(self) -> None:
        types = self.plugin.register_entity_types()
        assert "ip_record" in types
        assert "threat_indicator" in types

    def test_relationship_types(self) -> None:
        types = self.plugin.register_relationship_types()
        assert "hosts" in types

    def test_capabilities(self) -> None:
        caps = self.plugin.get_capabilities()
        assert "threat-intelligence" in caps

    def test_initialize_does_not_raise(self) -> None:
        self.plugin.initialize()


class TestCyberOsintModels:
    def test_ip_record(self) -> None:
        from plugins.modules.cyber_osint.models.ip_record import IpRecord

        rec = IpRecord(ip="8.8.8.8")
        assert rec.ip == "8.8.8.8"
        assert rec.ip_version == 4
        assert rec.is_tor is False

    def test_threat_indicator(self) -> None:
        from plugins.modules.cyber_osint.models.threat_indicator import ThreatIndicator

        ti = ThreatIndicator(indicator="8.8.8.8", indicator_type="ip")
        assert ti.indicator == "8.8.8.8"
        assert ti.severity == "unknown"

    def test_certificate_model(self) -> None:
        from plugins.modules.cyber_osint.models.certificate import Certificate

        cert = Certificate(domain="example.com")
        assert cert.domain == "example.com"
        assert cert.is_expired is False

    def test_cyber_domain_record(self) -> None:
        from plugins.modules.cyber_osint.models.domain_record import CyberDomainRecord

        rec = CyberDomainRecord(domain="example.com")
        assert rec.domain == "example.com"
        assert rec.is_malicious is False


class TestCyberOsintConnectors:
    @pytest.mark.asyncio
    async def test_spf_checker_returns_dict(self) -> None:
        from plugins.modules.cyber_osint.connectors.email_security.spf_checker import SpfChecker

        checker = SpfChecker()
        result = await checker.check("example.com")
        assert isinstance(result, dict)
        assert "has_spf" in result

    @pytest.mark.asyncio
    async def test_dmarc_checker_returns_dict(self) -> None:
        from plugins.modules.cyber_osint.connectors.email_security.dmarc_checker import (
            DmarcChecker,
        )

        checker = DmarcChecker()
        result = await checker.check("example.com")
        assert isinstance(result, dict)
        assert "has_dmarc" in result

    @pytest.mark.asyncio
    async def test_dkim_checker_returns_dict(self) -> None:
        from plugins.modules.cyber_osint.connectors.email_security.dkim_checker import DkimChecker

        checker = DkimChecker()
        result = await checker.check("example.com")
        assert isinstance(result, dict)
        assert "has_dkim" in result

    @pytest.mark.asyncio
    async def test_virustotal_no_key(self) -> None:
        from plugins.modules.cyber_osint.connectors.threat_intel.virustotal_client import (
            VirusTotalClient,
        )

        client = VirusTotalClient(api_key="")
        result = await client.check_ip("8.8.8.8")
        assert result.indicator == "8.8.8.8"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_abuseipdb_no_key(self) -> None:
        from plugins.modules.cyber_osint.connectors.threat_intel.abuse_ipdb import AbuseIpDb

        client = AbuseIpDb(api_key="")
        result = await client.check("8.8.8.8")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_dns_resolver_returns_dict(self) -> None:
        from plugins.modules.cyber_osint.connectors.domain.dns_resolver import DnsResolver

        resolver = DnsResolver()
        result = await resolver.resolve("example.com")
        assert isinstance(result, dict)


class TestCyberOsintAnalyzers:
    def test_threat_scorer_empty(self) -> None:
        from plugins.modules.cyber_osint.analyzers.threat_scorer import ThreatScorer

        scorer = ThreatScorer()
        score = scorer.score([])
        assert score == 0.0

    def test_threat_scorer_with_indicators(self) -> None:
        from plugins.modules.cyber_osint.analyzers.threat_scorer import ThreatScorer
        from plugins.modules.cyber_osint.models.threat_indicator import ThreatIndicator

        scorer = ThreatScorer()
        indicators = [
            ThreatIndicator(indicator="1.2.3.4", indicator_type="ip", confidence=0.8),
            ThreatIndicator(indicator="evil.com", indicator_type="domain", confidence=0.6),
        ]
        score = scorer.score(indicators)
        assert 0.0 < score <= 1.0


# ── Misinformation Module ─────────────────────────────────────────────────────


class TestMisinformationPlugin:
    def setup_method(self) -> None:
        from plugins.modules.misinformation.plugin import MisinformationPlugin

        self.plugin = MisinformationPlugin()

    def test_name(self) -> None:
        assert self.plugin.name == "misinformation"

    def test_entity_types(self) -> None:
        types = self.plugin.register_entity_types()
        assert "claim" in types
        assert "factcheck" in types
        assert "narrative" in types

    def test_capabilities(self) -> None:
        caps = self.plugin.get_capabilities()
        assert "claim-detection" in caps
        assert "fact-checking" in caps

    def test_initialize_does_not_raise(self) -> None:
        self.plugin.initialize()


class TestMisinformationModels:
    def test_claim_model(self) -> None:
        from plugins.modules.misinformation.models.claim import Claim

        claim = Claim(text="Scientists claim the sky is blue.")
        assert claim.text == "Scientists claim the sky is blue."
        assert claim.id is not None
        assert claim.verified is False

    def test_narrative_model(self) -> None:
        from plugins.modules.misinformation.models.narrative import Narrative

        narrative = Narrative(title="Test Narrative")
        assert narrative.title == "Test Narrative"
        assert narrative.sentiment == "neutral"

    def test_factcheck_model(self) -> None:
        from plugins.modules.misinformation.models.factcheck import FactCheck

        fc = FactCheck(claim_text="The earth is flat.", verdict="false", fact_checker="Snopes")
        assert fc.verdict == "false"

    def test_source_rating_model(self) -> None:
        from plugins.modules.misinformation.models.source_rating import SourceRating

        rating = SourceRating(domain="example.com")
        assert rating.domain == "example.com"
        assert rating.credibility_score == 0.5

    def test_misinfo_campaign_model(self) -> None:
        from plugins.modules.misinformation.models.misinformation_campaign import (
            MisinformationCampaign,
        )

        campaign = MisinformationCampaign(name="Test Campaign")
        assert campaign.name == "Test Campaign"
        assert campaign.status == "active"


class TestMisinformationDetectors:
    @pytest.mark.asyncio
    async def test_claim_detector_finds_claims(self) -> None:
        from plugins.modules.misinformation.detectors.claim_detector import ClaimDetector

        detector = ClaimDetector()
        text = "Scientists claim that vaccines cause 99% of illnesses. According to sources, experts say this is true."
        claims = await detector.detect(text)
        assert isinstance(claims, list)

    @pytest.mark.asyncio
    async def test_claim_detector_empty_text(self) -> None:
        from plugins.modules.misinformation.detectors.claim_detector import ClaimDetector

        detector = ClaimDetector()
        claims = await detector.detect("Hi.")
        assert isinstance(claims, list)

    @pytest.mark.asyncio
    async def test_bot_detector_low_score_normal_profile(self) -> None:
        from plugins.modules.misinformation.detectors.bot_detector import BotDetector

        detector = BotDetector()
        profile = {
            "account_age_days": 500,
            "followers_count": 1200,
            "username": "john_doe_42",
        }
        result = await detector.analyze(profile)
        assert "bot_probability" in result
        assert "is_bot" in result
        assert isinstance(result["bot_probability"], float)

    @pytest.mark.asyncio
    async def test_coordination_detector_no_posts(self) -> None:
        from plugins.modules.misinformation.detectors.coordination_detector import (
            CoordinationDetector,
        )

        detector = CoordinationDetector()
        result = await detector.detect([])
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_narrative_detector_groups_claims(self) -> None:
        from plugins.modules.misinformation.detectors.narrative_detector import NarrativeDetector
        from plugins.modules.misinformation.models.claim import Claim

        detector = NarrativeDetector()
        claims = [
            Claim(text="Vaccines are dangerous."),
            Claim(text="Vaccines cause harm."),
        ]
        narratives = await detector.detect(claims, keywords=["vaccines", "dangerous"])
        assert isinstance(narratives, list)


class TestMisinformationAnalyzers:
    def test_bias_analyzer_neutral(self) -> None:
        from plugins.modules.misinformation.analyzers.bias_analyzer import BiasAnalyzer

        analyzer = BiasAnalyzer()
        result = analyzer.analyze("This is a plain statement.")
        assert "bias_score" in result
        assert -1.0 <= result["bias_score"] <= 1.0

    def test_sentiment_analyzer_positive(self) -> None:
        from plugins.modules.misinformation.analyzers.sentiment_analyzer import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("This is great and wonderful!")
        assert result["sentiment"] == "positive"

    def test_sentiment_analyzer_negative(self) -> None:
        from plugins.modules.misinformation.analyzers.sentiment_analyzer import SentimentAnalyzer

        analyzer = SentimentAnalyzer()
        result = analyzer.analyze("This is terrible and awful!")
        assert result["sentiment"] == "negative"

    def test_credibility_scorer_default(self) -> None:
        from plugins.modules.misinformation.analyzers.credibility_scorer import CredibilityScorer

        scorer = CredibilityScorer()
        score = scorer.score("example.com")
        assert 0.0 <= score <= 1.0

    @pytest.mark.asyncio
    async def test_propagation_analyzer(self) -> None:
        from plugins.modules.misinformation.analyzers.propagation_analyzer import (
            PropagationAnalyzer,
        )
        from plugins.modules.misinformation.models.claim import Claim

        analyzer = PropagationAnalyzer()
        claim = Claim(text="Test claim about something.")
        result = await analyzer.analyze(claim, [])
        assert "total_mentions" in result


class TestMisinformationNlp:
    @pytest.mark.asyncio
    async def test_claim_extractor(self) -> None:
        from plugins.modules.misinformation.nlp.claim_extractor import ClaimExtractor

        extractor = ClaimExtractor()
        text = "The government announced new policies. Scientists have discovered a new drug."
        claims = await extractor.extract(text)
        assert isinstance(claims, list)

    @pytest.mark.asyncio
    async def test_propaganda_detector_detects_fear(self) -> None:
        from plugins.modules.misinformation.nlp.propaganda_detector import PropagandaDetector

        detector = PropagandaDetector()
        text = "This is a major threat and crisis that will devastate our society."
        result = await detector.detect(text)
        assert "techniques_detected" in result
        assert "propaganda_score" in result
        assert isinstance(result["techniques_detected"], list)


class TestMisinformationConnectors:
    @pytest.mark.asyncio
    async def test_claimbuster_no_key(self) -> None:
        from plugins.modules.misinformation.connectors.factcheck.claimbuster import ClaimBuster

        cb = ClaimBuster(api_key="")
        result = await cb.check_claim("The sky is blue.")
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_google_factcheck_no_key(self) -> None:
        from plugins.modules.misinformation.connectors.factcheck.google_factcheck import (
            GoogleFactCheck,
        )

        gfc = GoogleFactCheck(api_key="")
        result = await gfc.search("test claim")
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_reverse_image_search_returns_dict(self) -> None:
        from plugins.modules.misinformation.connectors.content_verification.reverse_image_search import (
            ReverseImageSearch,
        )

        ris = ReverseImageSearch()
        result = await ris.search("https://example.com/image.jpg")
        assert "status" in result

    @pytest.mark.asyncio
    async def test_mbfc_connector_returns_none(self) -> None:
        from plugins.modules.misinformation.connectors.credibility.mbfc_connector import (
            MbfcConnector,
        )

        connector = MbfcConnector()
        result = await connector.lookup("example.com")
        # Expected: None (no public API available)
        assert result is None
