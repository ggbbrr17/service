import sys
import argparse
from interfaces.gui import AgentGUI
from interfaces import server
import tkinter as tk

def main():
    parser = argparse.ArgumentParser(description="Glyph Assistant Launcher")
    parser.add_argument("--mode", choices=["gui", "server", "cli"], default="gui")
    args = parser.parse_args()

    if args.mode == "gui":
        root = tk.Tk()
        app = AgentGUI(root)
        root.mainloop()
    elif args.mode == "server":
        server.app.run(port=5000)
    elif args.mode == "cli":
        from interfaces import cli
        cli.main()

if __name__ == "__main__":
    main()