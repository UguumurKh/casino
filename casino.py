from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
VALUES = {rank: index for index, rank in enumerate(RANKS, start=1)}


@dataclass(frozen=True)
class Move:
    hand: frozenset[str]
    table: frozenset[str]


@dataclass
class State:
    hands: tuple[tuple[str, ...], tuple[str, ...]]
    table: tuple[str, ...]
    talon: tuple[str, ...]
    piles: tuple[tuple[str, ...], tuple[str, ...]]
    sweeps: tuple[int, int]
    player: int
    double_move: bool = False
    last_capturer: int | None = None


def value(card: str) -> int:
    if not isinstance(card, str) or len(card) < 2:
        raise ValueError(f"invalid card: {card!r}")
    rank = card[:-1]
    if rank not in VALUES:
        raise ValueError(f"invalid card: {card!r}")
    return VALUES[rank]


def _sort_key(card: str) -> tuple[int, str]:
    return (VALUES[card[:-1]], card[-1])


def _capture_moves(available: tuple[str, ...], table: tuple[str, ...]) -> set[Move]:
    moves: set[Move] = set()
    for hand_size in range(1, len(available) + 1):
        for hand_subset in combinations(available, hand_size):
            hand_total = sum(value(card) for card in hand_subset)
            for table_size in range(1, len(table) + 1):
                for table_subset in combinations(table, table_size):
                    if sum(value(card) for card in table_subset) == hand_total:
                        moves.add(Move(frozenset(hand_subset), frozenset(table_subset)))
    return moves


def new_deal(deck, first: int = 0) -> State:
    deck = tuple(deck)
    if first not in (0, 1):
        raise ValueError("first must be 0 or 1")
    hands = (tuple(deck[:3]), tuple(deck[3:6]))
    if first == 1:
        hands = (hands[1], hands[0])
    return State(
        hands=hands,
        table=tuple(deck[6:10]),
        talon=tuple(deck[10:]),
        piles=((), ()),
        sweeps=(0, 0),
        player=first,
    )


def legal_moves(state: State) -> list[Move]:
    player = state.player
    hand = state.hands[player]
    moves: set[Move] = set(_capture_moves(hand, state.table))
    if not hand and state.table:
        moves.add(Move(frozenset(), frozenset(state.table)))
    for card in hand:
        moves.add(Move(frozenset({card}), frozenset()))
    return sorted(moves, key=lambda move: (len(move.table), sorted(move.table), sorted(move.hand)))


def play(state: State, move: Move) -> State:
    player = state.player
    if move not in legal_moves(state):
        raise ValueError("illegal move")

    hands = [list(hand) for hand in state.hands]
    table = list(state.table)
    talon = list(state.talon)
    piles = [list(pile) for pile in state.piles]
    sweeps = list(state.sweeps)
    next_player = 1 - player
    extra_turn = bool(state.double_move)
    last_capturer = state.last_capturer

    if move.table:
        captures = set(move.table)
        if move.hand:
            hands[player] = [card for card in hands[player] if card not in move.hand]
            captures |= set(move.hand)
        # if the move is a table-empty capture, the table is removed entirely
        table = [card for card in table if card not in move.table]
        piles[player].extend(sorted(captures, key=_sort_key))
        last_capturer = player
        if not table:
            sweeps[player] += 1
            next_player = 1 - player
            extra_turn = True
        else:
            next_player = 1 - player
            extra_turn = False
    else:
        card = next(iter(move.hand))
        hands[player] = [held for held in hands[player] if held != card]
        table.append(card)
        if extra_turn:
            next_player = player
            extra_turn = False
        else:
            next_player = 1 - player

    # Handle end-of-round replenishment before the next turn is considered.
    if not hands[0] and not hands[1]:
        if len(talon) >= 6:
            drawn = talon[:6]
            hands = [list(drawn[:3]), list(drawn[3:6])]
            talon = talon[6:]
            next_player = last_capturer if last_capturer is not None else player
            extra_turn = False
        elif not talon and table and last_capturer is not None:
            piles[last_capturer].extend(sorted(table, key=_sort_key))
            table = []
            next_player = last_capturer
            extra_turn = False
    elif not hands[next_player] and len(talon) >= 3:
        hands[next_player].extend(talon[:3])
        talon = talon[3:]
        extra_turn = False

    return State(
        hands=(tuple(hands[0]), tuple(hands[1])),
        table=tuple(table),
        talon=tuple(talon),
        piles=(tuple(piles[0]), tuple(piles[1])),
        sweeps=(sweeps[0], sweeps[1]),
        player=next_player,
        double_move=extra_turn,
        last_capturer=last_capturer,
    )


def deal_over(state: State) -> bool:
    cards_in_play = (
        len(state.hands[0])
        + len(state.hands[1])
        + len(state.table)
        + len(state.talon)
        + len(state.piles[0])
        + len(state.piles[1])
    )
    return cards_in_play == 52 and not state.hands[0] and not state.hands[1] and not state.table and not state.talon


def score(state: State) -> tuple[int, int]:
    results = []
    for player in (0, 1):
        pile = state.piles[player]
        total = 0
        total += 3 if len(pile) >= 27 else 0
        total += 2 if sum(1 for card in pile if card.endswith("S")) >= 7 else 0
        total += sum(1 for card in pile if card.startswith("A"))
        total += 2 if "10D" in pile else 0
        total += 1 if "2S" in pile else 0
        total += state.sweeps[player]
        results.append(total)
    return tuple(results)


__all__ = ["Move", "State", "value", "new_deal", "legal_moves", "play", "deal_over", "score"]
