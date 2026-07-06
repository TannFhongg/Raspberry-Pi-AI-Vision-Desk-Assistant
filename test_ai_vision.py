"""Command-line test script for the OpenAI vision Phase 1 MVP."""

from __future__ import annotations

import argparse
import sys

from ai.openai_client import OpenAIVisionClient, VisionClientError
from ai.prompts import get_available_modes


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    available_modes = get_available_modes()

    parser = argparse.ArgumentParser(
        description="Send a local image to OpenAI Vision and print a concise answer."
    )
    parser.add_argument(
        "--image",
        required=True,
        help="Path to the image file you want to analyze.",
    )
    parser.add_argument(
        "--mode",
        default="read_text",
        choices=available_modes,
        help="AI mode to use for the analysis.",
    )
    parser.add_argument(
        "--question",
        help="Optional extra instruction to guide the analysis.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override. Defaults to OPENAI_MODEL from .env.",
    )
    return parser


def main() -> int:
    """Load configuration, call the vision client, and print the result."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Activate your virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    load_dotenv()

    print("Starting OpenAI Vision test...")
    print(f"Image: {args.image}")
    print(f"Mode: {args.mode}")
    if args.model:
        print(f"Model override: {args.model}")

    try:
        client = OpenAIVisionClient(default_model=args.model)
        print("Sending image to OpenAI...")
        answer = client.analyze_image(
            image_path=args.image,
            mode=args.mode,
            extra_instruction=args.question,
            model=args.model,
        )
    except VisionClientError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("\nAI Answer:\n")
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
