import numpy
import argparse
import os
from scipy import spatial
import csv
import re
import random
import math

#global to store all word scores so we don't need to duplicate
SCORES = None

def load_scores():
    global SCORES
    SCORES = {}
    with open("/tmp/scores.csv") as f_in:
        reader = csv.DictReader(f_in)
        for row in reader:
            SCORES[row["__word"]] = {k:row[k] for k in row if k != "__word"}


def readCL():
    parser = argparse.ArgumentParser()
    parser.add_argument("-l","--load")
    parser.add_argument("-s","--save",help="Directory to save information")
    parser.add_argument("-w","--word",help="Word to check for similar words against")
    parser.add_argument("--generate_scores", action="store_true")
    args = parser.parse_args()
    return args

def generate_scores(dictionary_size):
    wordlist = set()
    with open("wordlist.txt") as f_in:
        for l in f_in:
            wordlist.add(l.strip())
    wordlist_vectors = {}
    print("loading wordlist vectors")
    #read once for wordlist vectors
    for name, vec in read_word2vec():
        if len(wordlist_vectors) == len(wordlist): break
        if name in wordlist:
            wordlist_vectors[name] = [float(x) for x in vec]

    print("computing distances")
    #read second time to compute distances
    wordlist = list(wordlist)
    cnt = 0
    with open("/tmp/distances.csv", 'w') as f_out:
        writer = csv.DictWriter(f_out,fieldnames=["__word"] + wordlist)
        writer.writeheader()
        for name, vec in read_word2vec():
            cnt += 1
            if not re.findall("^\w+$",name): continue #skip punctuation, other weird words
            if cnt > dictionary_size: break
            distances = {}
            for word in wordlist:
                cosine = spatial.distance.cosine(wordlist_vectors[word], [float(x) for x in vec])
                distances[word] = round(cosine, 4)
            row = {"__word":name, **distances}
            writer.writerow(row)


    #normalize each word separately
    values = []
    stats = {} #word: {cnt, sum, sumsq}
    for word in wordlist:
        stats[word] = {"cnt":0, "sum":0, "sumsq":0}
    with open("/tmp/distances.csv") as f_in:
        reader = csv.DictReader(f_in)
        for r in reader:
            for c in r:
                if c == "__word": continue #MUST: word -> __word
                if float(r[c]) < 0.01: continue #don't include perfect matches in these stats
                stats[c]["cnt"] += 1
                stats[c]["sum"] += float(r[c])
                stats[c]["sumsq"] += float(r[c])**2
    for word in stats:
        stats[word]["mean"] = stats[word]["sum"] / stats[word]["cnt"]
        stats[word]["sd"] = ((stats[word]["sumsq"] / stats[word]["cnt"]) - stats[word]["mean"]**2) ** 0.5

    with open("/tmp/scores.csv",'w') as f_out:
        writer = csv.DictWriter(f_out,fieldnames=["__word"] + wordlist)
        writer.writeheader()
        with open("/tmp/distances.csv") as f_in:
            reader = csv.DictReader(f_in)
            for inrow in reader:
                outrow = {k:round(-1*(float(inrow[k]) - stats[k]["mean"]) / stats[k]["sd"],4) for k in inrow if k != "__word"}
                outrow["__word"] = inrow["__word"]
                writer.writerow(outrow)

def read_word2vec():
    hdr = None
    with open("/ssd/files/word2vec/wiki.en.vec") as f_in:
        for l in f_in:
            if not hdr:
                hdr = l
                continue
            splits = l.rstrip().rsplit(" ",300)
            name = splits[0]
            vec = splits[1:]
            yield (name, vec)


class Game():
    def __init__(self, p1, p2):
        self.players = {
            "p1":p1,
            "p2":p2
        }
        self.setup_board()
    def other_player(self):
        return "p2" if self.turn == "p1" else "p1"
    def unused_words(self):
        current_player_words = [w for w in self.team_words[self.turn] if w not in self.guessed_words]
        other_player_words = [w for w in self.team_words[self.other_player()] if w not in self.guessed_words]
        neutral_words = [w for w in self.neutral_words if w not in self.guessed_words]
        assassin_words = [w for w in self.assassin_words if w not in self.guessed_words]
        return current_player_words, other_player_words, neutral_words, assassin_words
    def setup_board(self):
        all_words = [l.strip() for l in open("wordlist.txt")]
        random.shuffle(all_words)

        #TODO: variable boards
        self.team_words = {
            "p1": all_words[:9], #["hollywood","screen","play","marble","dinosaur","cat","pitch","bond","greece"],
            "p2": all_words[9:17] #["deck","spike","center","vacuum","unicorn","undertaker","sock","lochness"]
        }
        self.neutral_words = all_words[17:24] #["horse","berlin","platypus","port","chest","box","compound"]
        self.assassin_words = all_words[24:25] #["ship"]
        print(self.team_words["p1"])
        print(self.team_words["p2"])
        print(self.neutral_words)
        print(self.assassin_words)
        self.full_board = self.team_words["p1"] + self.team_words["p2"] + self.neutral_words + self.assassin_words
        self.guessed_words = []
        random.shuffle(self.full_board)
        self.turn = "p1"
    def get_winner(self):
        if any(w in set(self.assassin_words) for w in self.guessed_words):
            return self.other_player()
        elif set(self.team_words["p1"]).issubset(set(self.guessed_words)):
            return "p1"
        elif set(self.team_words["p2"]).issubset(set(self.guessed_words)):
            return "p2"
        else:
            return None
    def play_game(self):
        game_over = False
        while not game_over:
            current_player = self.players[self.turn]
            print(f"Turn: {self.turn}'s turn")
            self.print_codemaster_view()
            clue_word, clue_num = current_player.give_clue(self)
            print(f'Clue: {clue_word}, {clue_num}')
            guess_cnt = 1
            while guess_cnt <= clue_num + 1:
                guess = current_player.guess(self, clue_word, clue_num, guess_cnt)
                if guess is None:
                    break
                else:
                    print(f'Guess: {guess}')
                self.guessed_words.append(guess)
                winner = self.get_winner()
                if winner:
                    print(f'{winner} wins!')
                    game_over = True
                    break
                if guess not in self.team_words[self.turn]:
                    break
                guess_cnt += 1
            self.turn = self.other_player() #switch turn
    def print_codemaster_view(self):
        self.print_info(True)
        print("-"*62)
        self.print_info(False)
    def print_info(self, codemaster=False):
        for row in range(5):
            output_row = []
            for col in range(5):
                index = 5*row + col
                word = self.full_board[index]
                render = " "*(10 - len(word)) + word
                if not word in self.guessed_words and not codemaster:
                    output_row.append(render)
                elif word in self.guessed_words and codemaster:
                    output_row.append(" "*10)
                elif word in self.team_words["p1"]:
                    output_row.append("\033[0;31m" + render + "\033[0;0m")
                elif word in self.team_words["p2"]:
                    output_row.append("\033[0;34m" + render + "\033[0;0m")
                elif word in self.neutral_words:
                    output_row.append("\033[1;30m" + render + "\033[0;0m")
                elif word in self.assassin_words:
                    output_row.append("\033[0;30m" + render + "\033[0;0m")
                else:
                    raise
            print("   ".join(output_row))



class CodenamesPlayer():
    def __init__(self, codemaster, guesser):
        self.codemaster = codemaster
        self.guesser = guesser
    def give_clue(self, game):
        return self.codemaster.give_clue(game)
    def guess(self, game, clue_word, clue_num, guess_num):
        return self.guesser.guess(game, clue_word, clue_num, guess_num)

class RobotPlayer(CodenamesPlayer):
    def __init__(self):
        self.codemaster = RobotCodemaster()
        self.guesser = RobotGuesser()

class HumanPlayer(CodenamesPlayer):
    def __init__(self):
        self.codemaster = HumanCodemaster()
        self.guesser = HumanGuesser()

class RHPlayer(CodenamesPlayer):
    def __init__(self):
        self.codemaster = RobotCodemaster()
        self.guesser = HumanGuesser()

class HRPlayer(CodenamesPlayer):
    def __init__(self):
        self.codemaster = HumanCodemaster()
        self.guesser = RobotGuesser()

class RobotCodemaster():
    def __init__(self):
        if SCORES is None:
            load_scores()
    def give_clue(self, game):
        our_words, their_words, neutral_words, assassin_words = game.unused_words()
        all_words = our_words + their_words + neutral_words + assassin_words

        best_clue = None
        best_clue_ev = None
        best_clue_cnt = None
        for word in SCORES:
            row = SCORES[word]
            #TODO: update below comments
            #compute rough value of this clue as follows:
            #when we score all words on the board, the top N will be from our_words for some N
            #(could be 0 if the top score isn't one of our words)
            #then assume that we'll clue with the number N
            #and compute the chance that they pick

            #TODO: assassin value set to -5 for now, what should it be?
            #TODO: claiming probability of guessing a word is proportional to e**score
            #      but more realistically should be e**(k*score), what's k?
            board = [{"word":w,
                       "value":1} for w in our_words] + \
                     [{"word":w,
                       "value":-1} for w in their_words] + \
                     [{"word":w,
                       "value":0} for w in neutral_words] + \
                     [{"word":w,
                       "value":-5} for w in assassin_words]
            for w in board:
                w["score"] = float(row[w["word"]])
                w["exp_score"] = math.e ** w["score"]
            board.sort(key=lambda x: x["score"], reverse=True)

            if any(word in w["word"] or w["word"] in word for w in board): continue

            clue_ev = 0
            clue_cnt = 0
            prob = 1
            # if sum([x["value"] for x in board[:4]]) == 4:
            #     print("quad")
            #     print(word)
            #     for b in board:
            #         print(b)
            while True:
                if len(board) == 0 or board[0]["value"] != 1: break
                sum_exp_scores = sum([w["exp_score"] for w in board])
                probs = [w["exp_score"] / sum_exp_scores for w in board]
                correct_prob = sum([p for p,w in zip(probs,board) if w["value"] == 1])
                guess_ev = prob * sum([p * w["value"] for p,w in zip(probs,board)])
                if guess_ev < 0:
                    break
                else:
                    clue_ev += guess_ev
                    clue_cnt += 1
                    prob *= correct_prob
                    board = board[1:]

            if best_clue_ev is None or clue_ev > best_clue_ev:
                best_clue = word
                best_clue_ev = clue_ev
                best_clue_cnt = clue_cnt
        return best_clue, best_clue_cnt

class RobotGuesser():
    def __init__(self):
        if SCORES is None:
            load_scores()
    def guess(self, game, clue_word, clue_num, guess_num):
        if guess_num > clue_num:
            return None
        row = SCORES[clue_word]
        word = clue_word
        board = [w for w in game.full_board if w not in game.guessed_words]
        board.sort(key=lambda x: row[x], reverse=True)
        print([row[w] for w in board])
        print(board)
        return board[0]

class HumanCodemaster():
    def give_clue(self, game):
        while True:
            print("****")
            print("****")
            print("****")
            print("****")
            print("Human codemaster, please give a glue")
            game.print_info(True)
            print("-"*62)
            game.print_info(False)
            print("clue word?")
            word = input()
            if word in SCORES:
                print("cnt?")
                cnt = input()
                return word, int(cnt)
            else:
                print("Sorry, computer doesn't understand")

class HumanGuesser():
    def guess(self, game, clue_word, clue_num, guess_num):
        while True:
            print(clue_word)
            print(clue_num)
            print(guess_num)
            print("board:")
            print([x for x in game.full_board if x not in game.guessed_words])
            guess = input()
            if guess in game.full_board:
                return guess
            else:
                print("invalid guess")


if __name__ == "__main__":
    args = readCL()
    if args.generate_scores:
        generate_scores(10000)
    else:
        game = Game(RobotPlayer(), RobotPlayer())
        game = Game(RobotPlayer(), HRPlayer())
        game.play_game()
