import argparse
import json

from core.engine import run


def main():
    parser = argparse.ArgumentParser(description="Glyph CLI")
    parser.add_argument("--question", "-q", required=True, help="Pregunta o comando")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin ejecutar")

    args = parser.parse_args()

    result = run(args.question, dry_run=args.dry_run)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

    print("🔥 CLI ejecutándose")

if __name__ == "__main__":
    print("🔥 MAIN detectado")