
"""Interfaz de consola del motor de recuperación FiQA."""

import argparse
import json

from dataclasses import asdict

from ri_fiqa.search_service import SearchService


def mostrar_resultados(hits, json_output=False):
    if json_output:
        print(json.dumps(
            [asdict(hit) for hit in hits],
            indent=2,
            ensure_ascii=False,
        ))
        return

    print(f"\nDocumentos recuperados: {len(hits)}")

    for hit in hits:
        print(f"\n--- RESULTADO {hit.rank} ---")
        print(f"Documento: {hit.doc_id}")
        print(f"Puntuación: {hit.score:.6f}")
        print(f"Texto: {hit.preview}")


def main():
    parser = argparse.ArgumentParser(
        description="Motor de Recuperación de Información FiQA."
    )

    parser.add_argument(
        "--model",
        choices=SearchService.MODELS,
        default="bge",
    )

    parser.add_argument(
        "--query",
        type=str,
    )

    parser.add_argument(
        "--top",
        type=int,
        default=5,
    )

    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda"],
        default="auto",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    if not args.interactive and not args.query:
        parser.error(
            "Indica --query o utiliza --interactive."
        )

    service = SearchService(device=args.device)

    def ejecutar(query):
        hits = service.search(
            query=query,
            model=args.model,
            top_k=args.top,
        )

        mostrar_resultados(hits, args.json)

    if args.interactive:
        print("\n=== MOTOR FIQA ===")
        print("Modelo seleccionado:", args.model)
        print("Escribe 'salir' para terminar.\n")

        while True:
            try:
                query = input("Consulta > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSaliendo...")
                break

            if query.lower() in ("salir", "exit", "quit"):
                break

            if not query:
                continue

            try:
                ejecutar(query)
            except (ValueError, FileNotFoundError) as exc:
                print("Error:", exc)

    else:
        ejecutar(args.query)


if __name__ == "__main__":
    main()
