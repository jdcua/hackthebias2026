# Word Search Demo
# https://medium.com/@msgold/creating-a-word-search-puzzle-b499533e938

"""how to code
creates an empty 13 x 13
creates a function that passes a list of generated words and goes through it one by one
takes the first word in the ai-generated list and places it on grid
randomly decides row and column starting point of the first letter of the word
randomly decides direction (horizontal, vertical, diagonal)
it determines if its possible to place the word, if not repeats 4 and 5
if its possible it places it according to randomly selected position / orientation
when its done it fills in empty spots in grid with random letters"""


import random
import string
from PyQt5.QtWidgets import QApplication, QWidget

#places word on to the board
def place_word(board, word):
    # Randomly choose orientation: 0=horizontal, 1=vertical, 2=diagonal
    orientation = random.randint(0, 3)
    
    placed = False
    while not placed:
        if orientation == 0:  # Horizontal
            row = random.randint(0, len(board)-1)
            col = random.randint(0, len(board)-len(word))
            reverse = random.choice([True, False])
            if reverse:
                word = word[::-1]
            space_available = all(board[row][c] == '-' or 
              board[row][c] == word[i] 
                for i, c in enumerate(range(col, col+len(word))))
            if space_available:
                for i, c in enumerate(range(col, col+len(word))):
                    board[row][c] = word[i]
                placed = True

        elif orientation == 1:  # Vertical
            row = random.randint(0, len(board)-len(word))
            col = random.randint(0, len(board)-1)
            reverse = random.choice([True, False])
            if reverse:
                word = word[::-1]
            space_available = all(board[r][col] == '-' or 
                board[r][col] == word[i] 
                  for i, r in enumerate(range(row, row+len(word))))
            if space_available:
                for i, r in enumerate(range(row, row+len(word))):
                    board[r][col] = word[i]
                placed = True

        elif orientation == 2:  # Diagonal top-left to bottom right
            row = random.randint(0, len(board)-len(word))
            col = random.randint(0, len(board)-len(word))
            reverse = random.choice([True, False])
            if reverse:
                word = word[::-1]
            space_available = all(board[r][c] == '-' or 
                board[r][c] == word[i] 
                  for i, (r, c) in enumerate(zip(range(row, row+len(word)), 
                                      range(col, col+len(word)))))
            if space_available:
                for i, (r, c) in enumerate(zip(range(row, row+len(word)), 
                                      range(col, col+len(word)))):
                    board[r][c] = word[i]
                placed = True
                
        elif orientation == 3:  # Diagonal bottom-left to top-right
            row = random.randint(len(word) - 1, len(board) - 1)
            col = random.randint(0, len(board) - len(word))
            reverse = random.choice([True, False])
            if reverse:
                word = word[::-1]
            space_available = all(board[r][c] == '-' or 
                board[r][c] == word[i] 
                  for i, (r, c) in enumerate(zip(range(row, row-len(word), -1),
                                     range(col, col+len(word)))))
            if space_available:
                for i, (r, c) in enumerate(zip(range(row, row-len(word), -1), 
                      range(col, col+len(word)))):
                    board[r][c] = word[i]
                placed = True

def fill_empty(board):
    for row in range(len(board)):
        for col in range(len(board)):
            if board[row][col] == '-':
                board[row][col] = random.choice(string.ascii_uppercase)

def create_word_search(words):
    board = [['-' for _ in range(13)] for _ in range(13)]

    for word in words:
        place_word(board, word)

    fill_empty(board)

    return board

def display_board(board):
    for row in board:
        print(' '.join(row))


words = ["adventure", "destination", "passport", "explore", "tourist", 
          "journey", "flight", "cruise", "luggage", "ticket"]
    
board = create_word_search(words)
display_board(board)
