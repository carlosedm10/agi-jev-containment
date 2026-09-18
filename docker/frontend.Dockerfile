FROM oven/bun:1.4.2

WORKDIR /code

COPY frontend/package.json frontend/bun.lock* ./

RUN bun install --frozen-lockfile || bun install

COPY frontend/ .

EXPOSE 5173

CMD ["bun", "run", "dev", "--", "--host", "0.0.0.0"]
