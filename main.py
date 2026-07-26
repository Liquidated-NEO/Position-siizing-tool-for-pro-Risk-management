from __future__ import annotations


def main() -> int:
    try:
        from ui import CryptoSizerApp
    except ImportError as exc:
        if "customtkinter" in str(exc).lower():
            print("CustomTkinter is not installed. Run: pip install -r requirements.txt")
            return 1
        raise

    app = CryptoSizerApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
