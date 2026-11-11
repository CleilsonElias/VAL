"""Host-side integration using already-computed embeddings and domain scores."""
from val_memory import Observation, VALConfig, VALMemory, SQLiteStore


def main():
    engine = VALMemory(VALConfig(("math", "biology", "other"), (0.05, 0.1, 0.9)))
    # Replace these numbers with the host's FIXED encoder and calibrated scores.
    decision = engine.observe(Observation(
        id="example-1", text="Example only: graph representations of metabolism.",
        vector=(0.7, 0.5, 0.1), routing=(0.45, 0.5, 0.05), entropy=0.6))
    print(decision)
    print(engine.query((0.7, 0.5, 0.1), (0.45, 0.5, 0.05), entropy=0.7))
    # In an application, load the existing revision, then save with its CAS guard.
    # store = SQLiteStore("host-memory.sqlite")
    # revision = store.save(engine, expected_revision=0)
    # engine, revision = store.load()


if __name__ == "__main__":
    main()
