FROM python:3.9-slim

WORKDIR /Course_Project

COPY requirements.txt .

RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY . .

EXPOSE 5005

CMD ["python", "app.py"]
