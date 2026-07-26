#!/bin/bash

# Server commands to execute inside your remote AWS EC2 terminal instance

# 1. Update system dependencies and install Docker engine runtime tools
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose git

# 2. Start the Docker process engine and enable auto-boot on system startup
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# 3. Clone the source repository onto the virtual cloud directory host
git clone https://github.com/palmshed/predicate.git
cd predicate

# 4. Prompt host operator to declare target secret keys manually inside shell environment
# Set your LLM provider key (OpenRouter or OpenAI)
export OPENROUTER_API_KEY="your-openrouter-api-key"
# OR
# export OPENAI_API_KEY="your-openai-api-key"

# 4.5 Install Certbot utility tools for generating free SSL certificates
sudo apt-get install -y certbot

# Request the certificate from Let's Encrypt standalone server
# (Ensure port 80 is open on your security group and your domain points to this EC2 IP)
sudo certbot certonly --standalone -d yourdomain.com --non-interactive --agree-tos -m admin@yourdomain.com

# 5. Launch the optimized multi-container cluster setup with HTTPS active
docker-compose -f docker-compose.prod.yml up -d