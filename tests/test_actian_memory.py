import json
import math
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from intelligence.actian_memory import (
    ActianVectorMemory,
    LocalEpisodeMemory,
    ResilientEpisodeMemory,
    create_episode_memory,
)
from intelligence.learning_loop import IntelligenceEngine
from intelligence.scorer import rank_events
from shared.contracts import Event, EventEpisode, EventFeedback, UserProfile


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def semantic_test_embedding(text: str) -> list[float]:
    lowered = text.lower()
    values = [
        float(lowered.count("mixer")),
        float(lowered.count("network")),
        float(lowered.count("workshop")),
        float(lowered.count("agent")),
    ]
    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        return [0.0, 0.0, 0.0, 1.0]
    return [value / magnitude for value in values]


class FakeVectorParams:
    def __init__(self, *, size, distance):
        self.size = size
        self.distance = distance


class FakePointStruct:
    def __init__(self, *, id, vector, payload):
        self.id = id
        self.vector = vector
        self.payload = payload


class FakeField:
    def __init__(self, name):
        self.name = name

    def eq(self, value):
        return self.name, value


class FakeFilterBuilder:
    def __init__(self):
        self.conditions = []

    def must(self, condition):
        self.conditions.append(condition)
        return self

    def build(self):
        return tuple(self.conditions)


class FakeSDK:
    Distance = SimpleNamespace(Cosine="cosine")
    VectorParams = FakeVectorParams
    PointStruct = FakePointStruct
    Field = FakeField
    FilterBuilder = FakeFilterBuilder


class FakeActianStore:
    def __init__(self):
        self.points = {}
        self.collection = None
        self.vector_params = None
        self.flushes = 0


class FakeCollections:
    def __init__(self, store):
        self.store = store

    def get_or_create(self, *, name, vectors_config):
        self.store.collection = name
        self.store.vector_params = vectors_config


class FakePoints:
    def __init__(self, store):
        self.store = store

    def upsert(self, collection, *, points):
        if collection != self.store.collection:
            raise AssertionError("unexpected collection")
        for point in points:
            self.store.points[point.id] = point

    def search(
        self,
        collection,
        *,
        vector,
        limit,
        with_payload,
        filter,
        score_threshold=None,
    ):
        if collection != self.store.collection or not with_payload:
            raise AssertionError("unexpected search options")
        results = []
        for point in self.store.points.values():
            if any(
                point.payload.get(name) != expected
                for name, expected in filter
            ):
                continue
            score = sum(
                left * right for left, right in zip(vector, point.vector)
            )
            if score_threshold is not None and score < score_threshold:
                continue
            results.append(
                SimpleNamespace(payload=point.payload, score=score)
            )
        results.sort(key=lambda result: result.score, reverse=True)
        return results[:limit]


class FakeVDE:
    def __init__(self, store):
        self.store = store

    def flush(self, collection):
        if collection != self.store.collection:
            raise AssertionError("unexpected collection")
        self.store.flushes += 1

    def get_vector_count(self, collection):
        if collection != self.store.collection:
            raise AssertionError("unexpected collection")
        return len(self.store.points)


class FakeClient:
    def __init__(self, store):
        self.store = store
        self.collections = FakeCollections(store)
        self.points = FakePoints(store)
        self.vde = FakeVDE(store)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def health_check(self):
        return {"title": "Fake VectorAI", "version": "test"}


class FailingPrimary:
    provider = "actian_vectorai"
    mode = "connected"
    storage_mode = "live"
    status = "connected"
    last_retrieval_evidence = ()

    def record(self, episode, event=None):
        raise TimeoutError("secret provider detail")

    def retrieve_similar(self, user_id, event, limit=4):
        raise TimeoutError("secret provider detail")

    def close(self):
        return None


class ActianMemoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = [
            Event.from_dict(item)
            for item in load_json(ROOT / "shared" / "sample_events.json")
        ]
        cls.profile = UserProfile.from_dict(
            load_json(ROOT / "shared" / "sample_profile.json")
        )
        cls.feedback = EventFeedback.from_dict(
            load_json(ROOT / "shared" / "sample_feedback.json")
        )

    def connected_memory(self):
        store = FakeActianStore()
        memory = ActianVectorMemory(
            url="fake:6574",
            collection="event_copilot_test",
            dimension=4,
            score_threshold=0.1,
            embedder=semantic_test_embedding,
            sdk=FakeSDK,
            client_factory=lambda: FakeClient(store),
        )
        return memory, store

    def test_actian_stores_live_episode_and_retrieves_cross_event_match(self):
        memory, store = self.connected_memory()
        engine = IntelligenceEngine(memory)
        mixer = next(
            event for event in self.events if event.event_id == "evt_mixer_001"
        )
        recommendation = rank_events(
            self.events,
            self.profile,
            limit=None,
            run_id="run_actian_before_v1",
        )[0]

        episode = engine.record_event_outcome(
            self.profile,
            mixer,
            self.feedback,
            recommendation,
            episode_id="episode_actian_semantic_001",
            observed_at="2026-07-24T20:00:00-07:00",
        )
        future_mixer = replace(
            mixer,
            event_id="evt_future_networking_001",
            title="Founder Networking Night",
            description=(
                "A large mixer for founder networking and rapid introductions."
            ),
        )

        retrieved = memory.retrieve_similar(
            self.profile.user_id,
            future_mixer,
        )

        self.assertEqual(episode.storage_mode, "live")
        self.assertEqual([item.episode_id for item in retrieved], [episode.episode_id])
        self.assertEqual(memory.last_retrieval_evidence[0].provider, "actian_vectorai")
        self.assertGreater(memory.last_retrieval_evidence[0].relevance, 0.5)
        self.assertEqual(store.vector_params.size, 4)
        self.assertEqual(store.flushes, 1)
        point = next(iter(store.points.values()))
        self.assertEqual(point.payload["episode_id"], episode.episode_id)
        self.assertEqual(point.payload["episode"]["storage_mode"], "live")
        self.assertIn("format:", point.payload["event_fingerprint"])

    def test_actian_retrieval_is_isolated_by_user_id(self):
        memory, _ = self.connected_memory()
        engine = IntelligenceEngine(memory)
        mixer = next(
            event for event in self.events if event.event_id == "evt_mixer_001"
        )
        recommendation = rank_events(
            self.events,
            self.profile,
            limit=None,
            run_id="run_actian_isolation_v1",
        )[0]
        engine.record_event_outcome(
            self.profile,
            mixer,
            self.feedback,
            recommendation,
        )

        self.assertEqual(memory.retrieve_similar("another_user", mixer), [])

    def test_local_fallback_retrieves_a_similar_new_event(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = LocalEpisodeMemory(Path(directory) / "episodes.json")
            engine = IntelligenceEngine(memory)
            mixer = next(
                event for event in self.events if event.event_id == "evt_mixer_001"
            )
            recommendation = rank_events(
                self.events,
                self.profile,
                limit=None,
                run_id="run_local_cross_event_before_v1",
            )[0]
            episode = engine.record_event_outcome(
                self.profile,
                mixer,
                self.feedback,
                recommendation,
                episode_id="episode_local_cross_event_001",
            )
            live_prospect = replace(
                mixer,
                data_mode="live",
                event_id="evt_live_step_sf_20260827",
                title="Step SF 2026: The AI & Tech Startup Festival",
                description=(
                    "Founders, investors, and builders meet for AI product "
                    "showcases and networking."
                ),
                source_url="https://luma.com/StepSF26",
                source_name="Luma",
                start_time="2026-08-27T09:00:00-07:00",
                location="The Midway, San Francisco",
                format="conference",
                interaction_level=0.88,
                knowledge_depth=0.72,
                estimated_crowd_size=220,
                cost_usd=349,
            )

            retrieved = memory.retrieve_similar(
                self.profile.user_id,
                live_prospect,
            )

            self.assertEqual([item.episode_id for item in retrieved], [episode.episode_id])
            self.assertTrue(memory.event_metadata_path.exists())
            self.assertEqual(
                memory.last_retrieval_evidence[0].reason,
                "same user and deterministic structured event similarity",
            )
            self.assertGreaterEqual(
                memory.last_retrieval_evidence[0].relevance,
                0.55,
            )
            self.assertEqual(memory.retrieve_similar("another_user", live_prospect), [])

    def test_provider_failure_writes_truthful_local_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            fallback = LocalEpisodeMemory(Path(directory) / "episodes.json")
            memory = ResilientEpisodeMemory(FailingPrimary(), fallback)
            engine = IntelligenceEngine(memory)
            mixer = next(
                event for event in self.events if event.event_id == "evt_mixer_001"
            )
            recommendation = rank_events(
                self.events,
                self.profile,
                limit=None,
                run_id="run_actian_fallback_v1",
            )[0]

            episode = engine.record_event_outcome(
                self.profile,
                mixer,
                self.feedback,
                recommendation,
            )

            self.assertEqual(episode.storage_mode, "local_fallback")
            self.assertEqual(memory.mode, "demo_fallback")
            self.assertEqual(fallback.all()[0].episode_id, episode.episode_id)
            self.assertIn("TimeoutError", memory.status)
            self.assertNotIn("secret provider detail", memory.status)

    def test_factory_is_local_and_dependency_free_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {"ACTIAN_VECTORAI_ENABLED": "false"},
                clear=False,
            ):
                memory = create_episode_memory(
                    Path(directory) / "episodes.json"
                )

            self.assertIsInstance(memory, LocalEpisodeMemory)
            self.assertEqual(memory.mode, "demo_fallback")

    def test_factory_sanitizes_enabled_startup_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.dict(
                    os.environ,
                    {"ACTIAN_VECTORAI_ENABLED": "true"},
                    clear=False,
                ),
                patch(
                    "intelligence.actian_memory.ActianVectorMemory",
                    side_effect=RuntimeError("working secret"),
                ),
            ):
                memory = create_episode_memory(
                    Path(directory) / "episodes.json"
                )

            self.assertIsInstance(memory, LocalEpisodeMemory)
            self.assertIn("RuntimeError", memory.status)
            self.assertNotIn("working secret", memory.status)


if __name__ == "__main__":
    unittest.main()
