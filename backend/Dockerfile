FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY surpay ./surpay
ENV SURPAY_DATABASE_URL=sqlite:////data/surpay.db
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "surpay.api:app", "--host", "0.0.0.0", "--port", "8000"]
