#!/bin/bash
mkdir -p snake-lab
cd snake-lab

# 1. Updated Docker Compose with Dozzle (Web Viewer)
cat <<EOF > docker-compose.yml
services:
  snake-game:
    build: .
    container_name: auto_snake_bot
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"

  web-viewer:
    image: amir20/dozzle:latest
    container_name: snake_web_ui
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8888:8080"  # Browse to http://localhost:8888
    restart: always
EOF

# 2. Dockerfile (Same as before)
cat <<EOF > Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY snake.py .
CMD ["python", "-u", "snake.py"]
EOF

# 3. Snake Script (Same logic)
cat <<EOF > snake.py
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
EOF

docker compose up -d --build
echo "-------------------------------------------------------"
echo "🎮 Game is running!"
echo "🌐 View it here: http://localhost:8888"
echo "   (Once there, click on 'auto_snake_bot' in the sidebar)"
echo "-------------------------------------------------------"