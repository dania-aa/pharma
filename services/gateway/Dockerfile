FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

COPY src/ ./src/

ENV NODE_ENV=production

EXPOSE 3000

CMD ["node", "src/index.js"]
