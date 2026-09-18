from __future__ import annotations

import json
import random
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from casino import Move, deal_over, legal_moves, new_deal, play, score

HOST = "127.0.0.1"
PORT = 8000
ROOT = Path(__file__).parent
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
DECK = [rank + suit for suit in "SHDC" for rank in RANKS]


def start_game():
    cards = DECK[:]
    random.SystemRandom().shuffle(cards)
    return new_deal(cards)


state = start_game()


def move_label(move: Move) -> str:
    hand = ", ".join(sorted(move.hand))
    if move.table:
        return f"Play {hand} and take {', '.join(sorted(move.table))}"
    return f"Place {hand}"


def choose_computer_move(current):
    moves = legal_moves(current)
    left = len(current.hands[0]) + len(current.hands[1]) + len(current.talon)
    captures = [move for move in moves if move.table]
    if captures and left > 1:
        return max(captures, key=lambda move: (len(move.table), sorted(move.table), sorted(move.hand)))
    placements = [move for move in moves if not move.table]
    return min(placements, key=lambda move: sorted(move.hand)) if placements else moves[0]


def computer_turns():
    global state
    while not deal_over(state) and state.player == 1:
        state = play(state, choose_computer_move(state))


def snapshot():
    finished = deal_over(state)
    return {
        "hands": [list(state.hands[0]), list(state.hands[1])],
        "table": list(state.table),
        "talon": len(state.talon),
        "piles": [len(state.piles[0]), len(state.piles[1])],
        "sweeps": list(state.sweeps),
        "player": state.player,
        "finished": finished,
        "score": list(score(state)) if finished else None,
        "moves": [
            {"hand": sorted(move.hand), "table": sorted(move.table), "label": move_label(move)}
            for move in legal_moves(state)
        ] if not finished and state.player == 0 else [],
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            self.send_json(snapshot())
            return
        if parsed.path == "/":
            body = (ROOT / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)

    def do_POST(self):
        global state
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if parsed.path == "/api/new":
                state = start_game()
                self.send_json(snapshot())
                return
            if parsed.path == "/api/move":
                if state.player != 0 or deal_over(state):
                    self.send_error(409, "It is not your turn")
                    return
                move_index = int(payload["index"])
                moves = legal_moves(state)
                if move_index < 0 or move_index >= len(moves):
                    self.send_error(400, "Unknown move")
                    return
                state = play(state, moves[move_index])
                computer_turns()
                self.send_json(snapshot())
                return
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_error(400, "Invalid request")
            return
        self.send_error(404)

    def send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Cassino is running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
