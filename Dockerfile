FROM python:3.10

WORKDIR /code
COPY . /code

RUN pip install --no-cache-dir -r requirements.txt

ENV HOST=0.0.0.0
ENV PORT=7860

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
