"""Check installed model and optionally test structured local inference."""

import argparse
from config import Settings
from llm.client import LLMError, OllamaClient
from memory.hindsight_client import MockHindsightClient
from memory.memory_writer import load_datasets, seed_memory
from services.incident_service import investigate_incident


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    client = OllamaClient(settings)
    try:
        print(client.check())
        if args.generate:
            _, history, cases = load_datasets(settings.data_dir)
            memory = MockHindsightClient()
            seed_memory(memory, history)
            result = investigate_incident(cases[0].incident, memory, client)
            print(result.model_dump_json(indent=2))
            if result.method != "llm_grounded" or result.recommended_action is None:
                parser.exit(1, "Local inference did not yield a grounded recommendation.\n")
    except LLMError as exc:
        parser.exit(1, f"Ollama check failed: {exc}. Start Ollama and pull {settings.llm_model}.\n")


if __name__ == "__main__":
    main()
