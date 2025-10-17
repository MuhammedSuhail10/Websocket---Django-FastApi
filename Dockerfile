ARG PYTHON_VERSION=3.13.7
FROM python:${PYTHON_VERSION}-slim as base

RUN mkdir /BagheeraLudo

RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /BagheeraLudo
 
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 
 
RUN pip install --upgrade pip 
 
COPY requirements.txt  /BagheeraLudo/
 
RUN pip install --no-cache-dir -r requirements.txt
 
COPY . /BagheeraLudo/
EXPOSE 8000

# CMD ["uvicorn", "BagheeraLudo.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
CMD ["gunicorn", "BagheeraLudo.asgi:application", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--keepalive", "5"]