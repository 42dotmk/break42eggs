FROM python:3.12-alpine
WORKDIR /app
COPY break42.py .
CMD ["python", "break42.py", "server", "42424", "42.mk"]
