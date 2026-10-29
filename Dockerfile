FROM python:3.12-slim
WORKDIR /app
COPY server.py excel_export.py ./
COPY static ./static
COPY fundraiser-settings.json ./
ENV PORT=8000 DATABASE_PATH=/data/board.db PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/board', timeout=3)"
EXPOSE 8000
CMD ["python", "-u", "server.py"]
