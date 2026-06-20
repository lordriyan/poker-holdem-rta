import itertools
import collections
import random
import time

# Mapping string to int
rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
suit_map = {'s': 0, 'h': 1, 'd': 2, 'c': 3}

# All possible cards
ALL_CARDS = [r + s for r in rank_map.keys() for s in suit_map.keys()]

def evaluate_five(cards):
    """
    Evaluates exactly 5 cards and returns a tuple ranking.
    Higher tuple means better hand.
    Tuple format: (Rank, tie_breaker_1, tie_breaker_2, ...)
    """
    ranks = sorted([rank_map[c[0]] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    
    is_flush = len(set(suits)) == 1
    
    # Check straight
    is_straight = False
    straight_high = 0
    if ranks == [14, 5, 4, 3, 2]: # A-5 straight (Wheel)
        is_straight = True
        straight_high = 5
    else:
        # Check if consecutive
        if ranks[0] - ranks[4] == 4 and len(set(ranks)) == 5:
            is_straight = True
            straight_high = ranks[0]
            
    # Count frequencies
    rank_counts = collections.Counter(ranks)
    counts = collections.defaultdict(list)
    for r, count in rank_counts.items():
        counts[count].append(r)
        
    for count in counts:
        counts[count].sort(reverse=True)
        
    # Check hand types in descending order of value
    # 9: Royal Flush -> Special case of Straight Flush
    if is_straight and is_flush:
        if straight_high == 14:
            return (9,)
        return (8, straight_high)
        
    # 7: Quads
    if 4 in counts:
        return (7, counts[4][0], counts[1][0])
        
    # 6: Full House
    if 3 in counts and 2 in counts:
        return (6, counts[3][0], counts[2][0])
        
    # 5: Flush
    if is_flush:
        return (5, *ranks)
        
    # 4: Straight
    if is_straight:
        return (4, straight_high)
        
    # 3: Trips
    if 3 in counts:
        return (3, counts[3][0], counts[1][0], counts[1][1])
        
    # 2: Two Pair
    if 2 in counts and len(counts[2]) == 2:
        return (2, counts[2][0], counts[2][1], counts[1][0])
        
    # 1: Pair
    if 2 in counts and len(counts[2]) == 1:
        return (1, counts[2][0], counts[1][0], counts[1][1], counts[1][2])
        
    # 0: High Card
    return (0, *ranks)

def evaluate_seven(cards):
    """
    Evaluates up to 7 cards and returns the best 5-card hand ranking.
    """
    if len(cards) < 5:
        return (0,)
        
    best_rank = (-1,)
    for combo in itertools.combinations(cards, 5):
        rank = evaluate_five(combo)
        if rank > best_rank:
            best_rank = rank
            
    return best_rank


class EquityCalculator:
    def __init__(self):
        pass
        
    def _get_deck(self, dead_cards):
        return [c for c in ALL_CARDS if c not in dead_cards]

    def monte_carlo(self, players, board, max_time=0.1, iterations=10000):
        return self._calculate(players, board, mode="monte_carlo", max_time=max_time, iterations=iterations)
        
    def exhaustive(self, players, board, max_time=0.1):
        return self._calculate(players, board, mode="exhaustive", max_time=max_time, iterations=0)

    def _calculate(self, players, board, mode="monte_carlo", max_time=0.1, iterations=10000):
        if not players:
            return {"hero": 0.0, "villain": 0.0, "tie": 0.0, "runs": 0}
            
        hero_cards = players[0]
        if len(hero_cards) < 2:
            return {"hero": 0.0, "villain": 0.0, "tie": 0.0, "runs": 0}
            
        known_villains = [p for p in players[1:] if len(p) == 2]
        num_random_villains = len(players) - 1 - len(known_villains)
        if num_random_villains < 0:
            num_random_villains = 0
            
        # If only hero is provided, simulate 1 random villain
        if len(players) == 1:
            num_random_villains = 1
            
        dead_cards = hero_cards + board + [c for p in known_villains for c in p]
        deck = self._get_deck(dead_cards)
        
        cards_to_deal_board = 5 - len(board)
        total_players = 1 + len(known_villains) + num_random_villains
        
        scores = [0.0] * total_players
        ties = 0
        total_runs = 0
        
        start_time = time.time()
        
        if mode == "exhaustive":
            # Exhaustive is feasible when we only need to deal board cards (no random villains)
            if num_random_villains == 0:
                for b_combo in itertools.combinations(deck, cards_to_deal_board):
                    current_board = board + list(b_combo)
                    best_rank = (-1,)
                    best_players = []
                    
                    all_players = [hero_cards] + known_villains
                    for p_idx, p_cards in enumerate(all_players):
                        rank = evaluate_seven(p_cards + current_board)
                        if rank > best_rank:
                            best_rank = rank
                            best_players = [p_idx]
                        elif rank == best_rank:
                            best_players.append(p_idx)
                            
                    if len(best_players) == 1:
                        scores[best_players[0]] += 1.0
                    else:
                        ties += 1
                        share = 1.0 / len(best_players)
                        for p in best_players:
                            scores[p] += share
                            
                    total_runs += 1
                    if time.time() - start_time > max_time:
                        break
            else:
                # Fallback to monte carlo if random villains exist (combination space too huge)
                mode = "monte_carlo"
                if iterations <= 0:
                    iterations = 10000
                
        if mode == "monte_carlo":
            for _ in range(iterations):
                random.shuffle(deck)
                idx = 0
                
                current_players = [hero_cards] + known_villains
                for _ in range(num_random_villains):
                    current_players.append([deck[idx], deck[idx+1]])
                    idx += 2
                    
                current_board = board + deck[idx:idx+cards_to_deal_board]
                
                best_rank = (-1,)
                best_players = []
                
                for p_idx, p_cards in enumerate(current_players):
                    rank = evaluate_seven(p_cards + current_board)
                    if rank > best_rank:
                        best_rank = rank
                        best_players = [p_idx]
                    elif rank == best_rank:
                        best_players.append(p_idx)
                        
                if len(best_players) == 1:
                    scores[best_players[0]] += 1.0
                else:
                    ties += 1
                    share = 1.0 / len(best_players)
                    for p in best_players:
                        scores[p] += share
                        
                total_runs += 1
                if time.time() - start_time > max_time:
                    break
                    
        if total_runs == 0:
            return {"hero": 0.0, "villain": 0.0, "tie": 0.0, "runs": 0}
            
        hero_equity = (scores[0] / total_runs) * 100.0
        # If there's 1 villain, villain equity is their score
        villain_equity = (scores[1] / total_runs) * 100.0 if total_players > 1 else 0.0
        tie_percent = (ties / total_runs) * 100.0
        
        return {
            "hero": hero_equity,
            "villain": villain_equity,
            "tie": tie_percent,
            "runs": total_runs
        }

if __name__ == "__main__":
    # Simple test for evaluation correctness
    assert evaluate_seven(["As","Ah","Ad","Ks","Kh","Jc","Tc"])[0] == 6 # Full House
    
    # Simple test for equity calculation
    calc = EquityCalculator()
    # Hero has AA, Villain has KK
    res = calc.exhaustive(players=[["As", "Ah"], ["Ks", "Kh"]], board=[])
    print("AA vs KK preflop:", res)
    
    # Hero has AA, Board is 2c 7d Js, Villain random
    res_mc = calc.monte_carlo(players=[["As", "Ah"]], board=["2c", "7d", "Js"], iterations=5000)
    print("AA vs Random on 2c 7d Js:", res_mc)
