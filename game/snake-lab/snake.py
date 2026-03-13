import time, random
def play():
    h, w = 12, 30
    snake = [[5,10], [5,9], [5,8]]
    food = [random.randint(1, h-2), random.randint(1, w-2)]
    while True:
        head = snake[0]
        move = [1,0] if head[0]<food[0] else [-1,0] if head[0]>food[0] else [0,1] if head[1]<food[1] else [0,-1]
        new_head = [head[0] + move[0], head[1] + move[1]]
        snake.insert(0, new_head)
        if new_head == food:
            food = [random.randint(1, h-2), random.randint(1, w-2)]
        else: snake.pop()
        if new_head[0]<=0 or new_head[0]>=h-1 or new_head[1]<=0 or new_head[1]>=w-1: break
        board = [[" " for _ in range(w)] for _ in range(h)]
        for y, x in snake: board[y][x] = "0"
        board[food[0]][food[1]] = "*"
        out = "\033[H\033[J" + "+" + "-"*(w-2) + "+\n"
        for row in board[1:-1]: out += "|" + "".join(row[1:-1]) + "|\n"
        out += "+" + "-"*(w-2) + "+\nScore: " + str(len(snake)-3)
        print(out)
        time.sleep(0.15)
if __name__ == "__main__":
    while True: play()
