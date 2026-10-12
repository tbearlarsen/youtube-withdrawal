FROM python:3.12-slim

WORKDIR /app

# deno: yt-dlp's JS runtime for YouTube's player challenges (same as TubeArchivist ships)
COPY --from=denoland/deno:bin-2.5.6 /deno /usr/local/bin/deno

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
