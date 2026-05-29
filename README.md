# ☁️ CloudStore — E-Commerce Platform on AWS

A full-stack e-commerce platform built to demonstrate real-world AWS cloud infrastructure. Features a live marketplace with Seller/Buyer roles, AI-generated art products, and a built-in Cloud Infrastructure Status dashboard.

---

## 🚀 Live Infrastructure

| Service | Status | Latency |
|--------|--------|---------|
| 🗄️ Amazon RDS (MySQL) | ✅ Available | ~7 ms |
| ⚡ ElastiCache (Redis) | ✅ Online | ~8 ms |
| 📨 Amazon MQ (RabbitMQ) | ✅ Running | ~44 ms |
| 🪣 Amazon S3 | ✅ Active | — |
| 🌐 Elastic Beanstalk | ✅ Deployed | — |

---

## 🏗️ Architecture

```
User Request
     │
     ▼
Elastic Beanstalk (EC2)
     │
     ├──► Amazon RDS (MySQL)       → Persistent data storage
     ├──► ElastiCache (Redis)      → Caching & session management
     ├──► Amazon MQ (RabbitMQ)     → Async order processing
     └──► Amazon S3                → Product image storage
                                        │
                                        ▼
                                  CloudWatch Dashboard
                                  (Monitoring & Metrics)
```

---

## ⚙️ Tech Stack

### Backend
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?style=flat&logo=django&logoColor=white)

### AWS Services
![AWS](https://img.shields.io/badge/AWS-232F3E?style=flat&logo=amazon-aws&logoColor=white)
![RDS](https://img.shields.io/badge/RDS_MySQL-527FFF?style=flat&logo=amazon-rds&logoColor=white)
![ElastiCache](https://img.shields.io/badge/ElastiCache_Redis-DC382D?style=flat&logo=redis&logoColor=white)
![S3](https://img.shields.io/badge/S3-569A31?style=flat&logo=amazon-s3&logoColor=white)
![MQ](https://img.shields.io/badge/Amazon_MQ-FF9900?style=flat&logo=rabbitmq&logoColor=white)
![Elastic Beanstalk](https://img.shields.io/badge/Elastic_Beanstalk-FF9900?style=flat&logo=amazon-aws&logoColor=white)
![CloudWatch](https://img.shields.io/badge/CloudWatch-FF4F8B?style=flat&logo=amazon-cloudwatch&logoColor=white)

---

## ✨ Features

### 🛍️ Marketplace
- **Buyer** — Browse products, purchase, track orders
- **Seller** — Add/manage products, view incoming orders
- Product images stored and served directly from **AWS S3**
- Category filtering & stock management

### ☁️ Cloud Infrastructure Dashboard
Built into the app — shows live connection status and performance benchmarks:
- Real-time latency for RDS, ElastiCache, Redis
- **Performance Benchmark**: MySQL direct query vs Redis cache
- Redis proved **1.6x–2.6x faster** than direct RDS queries

### 📊 Monitoring
- **CloudWatch Dashboard** tracking:
  - Request count per target
  - Database connections
  - Cache hits/misses

---

## 📸 Screenshots

### Cloud Infrastructure Status
> Live connections to all AWS services with real-time latency

![Dashboard](screenshots/web4.png)

### Available Products
> Products served from S3 with stock indicators

![Products](screenshots/web2.png)

### Seller — Incoming Orders
![Seller Orders](screenshots/web3.png)

### Buyer — My Orders
![Buyer Orders](screenshots/web.png)

### AWS RDS — Available
![RDS](screenshots/rds__2_.png)

### Amazon MQ — Running (RabbitMQ 3.13)
![MQ](screenshots/mq.png)

### Amazon S3 — 21 Product Images
![S3](screenshots/s3.png)

### MySQL — Live Data via EC2
![MySQL](screenshots/rds3.png)

### ElastiCache Redis — PING/PONG
![Redis](screenshots/rds4.png)

### CloudWatch Dashboard
![CloudWatch](screenshots/cloudwatch.png)

---

## 🗄️ Database Schema

```sql
-- 3 core tables
ecommerce_db
├── users      (id, username, email, role, ...)
├── products   (id, seller_id, name, price, quantity, image_url, category, ...)
└── orders     (id, buyer_id, product_id, quantity, total, status, ...)
```

---

## 🔧 Environment Variables

```env
AWS_REGION=us-east-1
DB_HOST=<your-rds-endpoint>
DB_NAME=ecommerce_db
DB_USER=admin
DB_PASS=<your-password>
REDIS_HOST=<your-elasticache-endpoint>
MQ_URL=amqps://<user>:<pass>@<your-mq-endpoint>:5671
S3_BUCKET=<your-bucket-name>
PYTHONPATH=/var/app/venv/staging-LQM1lest/bin
```

---

## 📈 Performance Results

```
MySQL (RDS) direct query:   ~13 ms
Redis (ElastiCache) cache:  ~5 ms
                            ──────────────────────
                            Redis is 2.6x Faster 🚀
```

---

## 🧱 AWS Services Used

| Service | Purpose |
|---------|---------|
| **EC2 / Elastic Beanstalk** | App hosting & deployment |
| **RDS MySQL (db.t3.micro)** | Relational database |
| **ElastiCache Redis** | Caching & performance |
| **Amazon MQ (mq.m7g.medium)** | Async message queue (RabbitMQ 3.13) |
| **S3** | Product image storage |
| **CloudWatch** | Monitoring & dashboards |
| **VPC / Security Groups** | Network isolation |

---

## 👤 Author

**Ahmed Salah**  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=flat&logo=linkedin&logoColor=white)](https://linkedin.com/in/your-profile)
[![GitHub](https://img.shields.io/badge/GitHub-100000?style=flat&logo=github&logoColor=white)](https://github.com/your-username)
